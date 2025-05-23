import os
import sys
import json
from pathlib import Path
from typing import Type, Dict, Any, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from litellm import completion, ServiceUnavailableError as LiteLLMServiceUnavailableError
import litellm

# Setup project root for module imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    if (project_root / ".env").exists():
        load_dotenv(dotenv_path=(project_root / ".env"))
        print("Loaded environment variables from .env file")
    else:
        print(".env file not found at project root. Please ensure it exists.")
except Exception as e:
    print(f"Error loading .env file: {e}")

try:
    from config.appconfig import (
        OPENAI_API_KEY,
        SERPER_API_KEY,
        EXCHANGE_RATE_API_KEY,
        GOOGLE_API_KEY,
        GROQ_API_KEY
    )
    print("Successfully imported API keys from config.appconfig")
except ImportError:
    print("Could not import from config.appconfig. Falling back to os.getenv.")
    EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not EXCHANGE_RATE_API_KEY:
    sys.exit("Error: EXCHANGE_RATE_API_KEY not found. Please set it in .env or config/appconfig.py")
if not GROQ_API_KEY:
    sys.exit("Error: GROQ_API_KEY not found. Please set it in .env or config/appconfig.py")

################ Class for input schema ######################

class CurrencyConverterInput(BaseModel):
    """
    Input schema for the CurrencyConverter tool.
    """
    amount: float = Field(..., description="The amount of money to convert.")
    from_currency: str = Field(..., description="The currency to convert from (e.g., 'USD').")
    to_currency: str = Field(..., description="The currency to convert to (e.g., 'EUR').")

################## Class for actual tool ######################

class CurrencyConverterTool(BaseTool):
    name: str = "Currency Converter Tool"
    description: str = "Converts an amount from one currency to another using the ExchangeRate API."
    args_schema: Type[BaseModel] = CurrencyConverterInput
    api_key: str = EXCHANGE_RATE_API_KEY

    def _run(self, amount: float, from_currency: str, to_currency: str) -> str:
        """
        Converts an amount from one currency to another using the ExchangeRate API.
        """
        if not self.api_key:
            return "Error: ExchangeRate API key is not configured."

        # Construct the API URL
        url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/latest/{from_currency.upper()}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return f"Failed to fetch exchange rates: {e}"

        data = response.json()
        if data.get("result") == "error":
            error_type = data.get("error-type", "Unknown error")
            if error_type == "unsupported-code":
                return f"Invalid or unsupported currency code provided for 'from_currency': {from_currency}"
            return f"API error when fetching rates for {from_currency}: {error_type}"

        if "conversion_rates" not in data or to_currency.upper() not in data["conversion_rates"]:
            return f"Invalid or unsupported currency code for 'to_currency': {to_currency}"

        rate = data["conversion_rates"][to_currency.upper()]
        converted_amount = amount * rate
        return f"{amount} {from_currency.upper()} is equal to {converted_amount:.2f} {to_currency.upper()}."

################ LLM Query Parser Function ######################

GROQ_PARSER_MODEL = "groq/llama3-8b-8192"

def parse_query_with_llm(query: str) -> Optional[Dict[str, Any]]:
    """
    Parses a natural language query to extract currency conversion details using an LLM.
    Returns a dictionary with 'amount', 'from_currency', and 'to_currency'.
    """
    prompt = f"""
You are an expert at parsing financial queries for currency conversion.
Your task is to extract the amount, the source currency, and the target currency from the user's query.
Provide the output in a valid JSON object with the following keys: "amount", "from_currency", "to_currency".

- "amount": Should be a numerical value (float or int).
- "from_currency": Should be the 3-letter ISO currency code (e.g., USD, EUR, JPY).
- "to_currency": Should be the 3-letter ISO currency code.

If any information is crucial and cannot be reasonably inferred (e.g. one of the currencies or the amount),
you can return null for that specific field or an error structure if that seems more appropriate, but try your best to complete the structure.
Common currency names like 'dollars', 'euros', 'yen', 'pounds' should be mapped to their ISO codes.
'Dollars' usually means USD unless specified otherwise (e.g., 'Canadian dollars' -> CAD).
'Euros' -> EUR. 'Pounds' -> GBP.

User query: "{query}"

JSON Output:
"""
    content = None
    parsed_json = None
    try:
        print(f"\nAttempting to parse query: '{query}' with model {GROQ_PARSER_MODEL}")
        response = completion(
            model=GROQ_PARSER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=GROQ_API_KEY,
            response_format={"type": "json_object"},
            timeout=30
        )

        content = response.choices[0].message.content
        if not content:
            print("Error: LLM returned empty content for query parsing.")
            return None

        print(f"LLM Raw JSON response: {content}")

        parsed_json = json.loads(content)
        validated_data = CurrencyConverterInput(**parsed_json)
        return validated_data.model_dump()

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}\nLLM Raw output was: {content}")
        return None
    except ValidationError as e:
        print(f"Validation error for LLM output: {e}\nParsed JSON was: {parsed_json}")
        return None
    except LiteLLMServiceUnavailableError as e:
        print(f"LLM service (Groq) is currently unavailable: {e}. Please try again later.")
        return None
    except Exception as e:
        print(f"Error during LLM query parsing: {e}")
        import traceback
        traceback.print_exc()
        return None

################### Build the agent ######################

GROQ_AGENT_MODEL = "groq/llama3-70b-8192" # "groq/llama-3.3-70b-versatile" # "llama-3.1-8b-instant"

currency_analyst = Agent(
    role="Currency Analyst",
    goal="Provide real-time currency conversion rates and financial insights based on the user's query.",
    backstory=(
        "You are a meticulous financial analyst specializing in currency conversion. "
        "You use precise, real-time data to perform conversions and offer brief, relevant financial context if appropriate. "
        "You stick to the task of conversion and providing the result clearly."
    ),
    tools=[CurrencyConverterTool()],
    verbose=True,
    llm=GROQ_AGENT_MODEL,
    allow_delegation=False,
    max_iter=5
)

############## Define the task for the agent ##############

currency_conversion_task_template = (
    "Convert {amount} {from_currency} to {to_currency} using the latest exchange rates. "
    "Provide the equivalent amount in the target currency. "
    "If possible, briefly explain any highly relevant financial context or recent significant changes "
    "related to these currencies if it directly impacts the conversion, but keep it concise. "
    "Focus primarily on delivering the conversion result accurately."
)

###################### Main Execution ######################

def main():
    print("Welcome to the Real-Time Currency Conversion Tool!")

    while True:
        natural_language_query = input("\nEnter your currency conversion query (e.g., 'How much is 100 dollars in euros today?') or type 'exit' to quit: ")
        if natural_language_query.lower() == 'exit':
            break
        if not natural_language_query.strip():
            print("Please enter a valid query.")
            continue

        parsed_inputs = parse_query_with_llm(natural_language_query)

        if parsed_inputs:
            print(f"\nParsed inputs: {parsed_inputs}")

            task_description = currency_conversion_task_template.format(
                amount=parsed_inputs['amount'],
                from_currency=parsed_inputs['from_currency'],
                to_currency=parsed_inputs['to_currency']
            )

            expected_output_description = (
                f"A detailed response including the converted amount of {parsed_inputs['amount']} "
                f"{parsed_inputs['from_currency']} to {parsed_inputs['to_currency']}, "
                "and brief, relevant financial insights if applicable."
            )

            dynamic_task = Task(
                description=task_description,
                expected_output=expected_output_description,
                agent=currency_analyst,
            )

            crew = Crew(
                agents=[currency_analyst],
                tasks=[dynamic_task],
                process=Process.sequential,
                verbose=True
            )

            print("\nKicking off the crew...")
            try:
                response = crew.kickoff(inputs=parsed_inputs)

                print("\n############################")
                print("## Crew Final Response:")
                print("############################")
                print(response)
            except LiteLLMServiceUnavailableError as e:
                print(f"LLM service (Groq) for the agent is currently unavailable: {e}. Please try again later.")
            except Exception as e:
                print(f"An error occurred while running the crew: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Could not parse your query. Please try rephrasing it or be more specific, or check connectivity.")

if __name__ == "__main__":
    main()
