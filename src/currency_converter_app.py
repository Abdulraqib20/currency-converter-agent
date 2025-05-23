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

# Initialize API keys to None, then populate them
EXCHANGE_RATE_API_KEY = None
GROQ_API_KEY = None
OPENAI_API_KEY = None # Included for completeness if config has it
SERPER_API_KEY = None # Included for completeness
GOOGLE_API_KEY = None # Included for completeness

try:
    from config.appconfig import (
        OPENAI_API_KEY as APP_OPENAI_API_KEY,
        SERPER_API_KEY as APP_SERPER_API_KEY,
        EXCHANGE_RATE_API_KEY as APP_EXCHANGE_RATE_API_KEY,
        GOOGLE_API_KEY as APP_GOOGLE_API_KEY,
        GROQ_API_KEY as APP_GROQ_API_KEY
    )
    OPENAI_API_KEY = APP_OPENAI_API_KEY
    SERPER_API_KEY = APP_SERPER_API_KEY
    EXCHANGE_RATE_API_KEY = APP_EXCHANGE_RATE_API_KEY
    GOOGLE_API_KEY = APP_GOOGLE_API_KEY
    GROQ_API_KEY = APP_GROQ_API_KEY
    print("Successfully imported API keys from config.appconfig")
except ImportError:
    print("Could not import from config.appconfig. Falling back to os.getenv for required keys.")
    EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    # Load others if needed by other parts of a larger system
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not EXCHANGE_RATE_API_KEY:
    sys.exit("Critical Error: EXCHANGE_RATE_API_KEY is not set. Please check .env or config/appconfig.py")
if not GROQ_API_KEY:
    sys.exit("Critical Error: GROQ_API_KEY is not set. Please check .env or config/appconfig.py")

# litellm.set_verbose = False # Keep false for cleaner output, true for debugging LiteLLM

################ Class for input schema ######################
class CurrencyConverterInput(BaseModel):
    amount: float = Field(..., description="The amount of money to convert.")
    from_currency: str = Field(..., description="The currency to convert from (e.g., 'USD').")
    to_currency: str = Field(..., description="The currency to convert to (e.g., 'EUR').")

################## Class for actual tool ######################
class CurrencyConverterTool(BaseTool):
    name: str = "Currency Converter Tool"
    description: str = "Converts an amount from one currency to another using the ExchangeRate API."
    args_schema: Type[BaseModel] = CurrencyConverterInput
    # The api_key for this tool will use the globally loaded EXCHANGE_RATE_API_KEY

    def _run(self, amount: float, from_currency: str, to_currency: str) -> str:
        if not EXCHANGE_RATE_API_KEY:
            return "Error: ExchangeRate API key is not configured or loaded."

        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/{from_currency.upper()}"

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
    prompt = f"""
You are an expert at parsing financial queries for currency conversion.
Your task is to extract the amount, the source currency, and the target currency from the user's query.
Provide the output in a valid JSON object with the following keys: "amount", "from_currency", "to_currency".
- "amount": Should be a numerical value (float or int).
- "from_currency": Should be the 3-letter ISO currency code (e.g., USD, EUR, JPY).
- "to_currency": Should be the 3-letter ISO currency code.
If any information is crucial and cannot be reasonably inferred, return null for that specific field or an error structure.
Common currency names like 'dollars', 'euros', 'yen', 'pounds' should be mapped to their ISO codes.
'Dollars' usually means USD unless specified otherwise (e.g., 'Canadian dollars' -> CAD).
'Euros' -> EUR. 'Pounds' -> GBP.
User query: "{query}"
JSON Output:
"""
    content = None
    parsed_json = None
    try:
        print(f"Attempting to parse query: '{query}' with model {GROQ_PARSER_MODEL}")
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
        print(f"LLM Raw JSON response for parsing: {content}")
        parsed_json = json.loads(content)
        validated_data = CurrencyConverterInput(**parsed_json)
        return validated_data.model_dump()
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}. LLM Raw output was: {content}")
        return None
    except ValidationError as e:
        print(f"Validation error for LLM output: {e}. Parsed JSON was: {parsed_json}")
        return None
    except LiteLLMServiceUnavailableError as e:
        print(f"LLM service (Groq) for query parsing is currently unavailable: {e}. Please try again later.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during LLM query parsing: {e}")
        import traceback
        traceback.print_exc()
        return None

################ Agent and Crew Logic (Callable Function) ######################
GROQ_AGENT_MODEL = "groq/llama3-70b-8192"

def get_currency_conversion_response(natural_language_query: str) -> str:
    """
    Parses a natural language query, runs the currency conversion crew, and returns the result.
    This function encapsulates the agent, task, and crew logic.
    """
    if not GROQ_API_KEY: # Redundant check, but good for a self-contained function perspective
        return "Error: GROQ_API_KEY is not configured for the agent."

    parsed_inputs = parse_query_with_llm(natural_language_query)
    if not parsed_inputs:
        return "Could not parse your query. Please try rephrasing it, check connectivity, or ensure all details (amount, currencies) are clear."

    print(f"Parsed inputs for crew: {parsed_inputs}")

    # Define agent (core logic as per user's working version)
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
        llm=GROQ_AGENT_MODEL, # Using the model string directly as it was working for the user
        allow_delegation=False,
        max_iter=5
    )

    # Define task
    currency_conversion_task_template = (
        "Convert {amount} {from_currency} to {to_currency} using the latest exchange rates. "
        "Provide the equivalent amount in the target currency. "
        "If possible, briefly explain any highly relevant financial context or recent significant changes "
        "related to these currencies if it directly impacts the conversion, but keep it concise. "
        "Focus primarily on delivering the conversion result accurately."
    )
    task_description = currency_conversion_task_template.format(**parsed_inputs)
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

    # Define and run crew
    crew = Crew(
        agents=[currency_analyst],
        tasks=[dynamic_task],
        process=Process.sequential,
        verbose=True
    )

    print("Kicking off the crew for conversion...")
    try:
        response = crew.kickoff(inputs=parsed_inputs)
        return str(response) # Ensure the final output is a string
    except LiteLLMServiceUnavailableError as e:
        return f"LLM service (Groq) for the agent is currently unavailable: {e}. Please try again later."
    except Exception as e:
        print(f"An error occurred while running the crew: {e}")
        import traceback
        traceback.print_exc()
        return "An unexpected error occurred during currency conversion. Please check logs."

###################### Main Execution (for CLI) ######################
def main(): # Renamed from main_cli for conventional Python
    print("Welcome to the Real-Time Currency Conversion Tool (CLI)!")
    while True:
        user_query = input("\nEnter your currency conversion query (e.g., 'How much is 100 dollars in euros today?') or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            break
        if not user_query.strip():
            print("Please enter a valid query.")
            continue

        final_result = get_currency_conversion_response(user_query)

        print("\n############################")
        print("## Final Response:")
        print("############################")
        print(final_result)

if __name__ == "__main__":
    main()
