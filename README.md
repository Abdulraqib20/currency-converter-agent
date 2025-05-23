# Real-Time AI Currency Converter

This project is a real-time currency conversion tool powered by AI. It uses CrewAI to manage an AI agent that can parse natural language queries, fetch live exchange rates using a custom tool, and provide currency conversions along with relevant financial context. The application features both a command-line interface (CLI) and a web interface built with Flask.

## Features

*   **Natural Language Query Processing**: Understands queries like "How much is 100 USD in EUR today?" or "Convert 5000 Japanese Yen to British Pounds."
*   **Real-Time Exchange Rates**: Integrates with the ExchangeRate-API to fetch up-to-date currency values.
*   **AI-Powered Responses**: An AI agent (powered by Groq's Llama 3 models via LiteLLM) provides not just the converted amount but also brief financial insights if applicable.
*   **Dual Interface**:
    *   **Web Application**: A user-friendly web interface built with Flask for easy interaction.
    *   **Command-Line Interface (CLI)**: For users who prefer terminal-based operations.
*   **Modular Design**: Core conversion logic is separated, allowing for easy integration and maintenance.

## Project Structure

```
currency-conversion-tool/
|-- src/                            # Source code
|   |-- currency_converter_app.py   # Core logic for AI agent, tools, query parsing, and CLI
|   |-- web_app.py                  # Flask web application
|-- templates/                      # HTML templates for Flask app
|   |-- index.html
|-- static/                         # Static files (CSS, JS) for Flask app
|   |-- style.css
|-- config/                         # Configuration files
|   |-- appconfig.py                # Loads and manages API keys and other configs
|-- .env                            # Environment variables (API keys)
|-- requirements.txt                # Python dependencies
|-- README.md                       # This file
```

## Prerequisites

*   Python 3.9 or higher
*   Access to API keys for:
    *   ExchangeRate-API (for currency exchange rates)
    *   Groq (for LLM access)

## Setup and Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/Abdulraqib20/currency-converter-agent
    cd currency-conversion-tool
    ```

2.  **Create a Virtual Environment** (recommended):
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If `requirements.txt` is not provided, you'll need to install the necessary packages manually (see `src/currency_converter_app.py` and `src/web_app.py` for imports like `flask`, `crewai`, `litellm`, `python-dotenv`, `requests`, `pydantic`).*

4.  **Set Up Environment Variables**:
    *   Create a `.env` file in the project root directory.
    *   Add your API keys to this file:
        ```env
        EXCHANGE_RATE_API_KEY=your_exchangerate_api_key_here
        GROQ_API_KEY=your_groq_api_key_here
        GOOGLE_API_KEY=your_google_key_if_needed
        ```

## Running the Application

You have two ways to use the currency converter:

### 1. Web Application (Flask)

*   Navigate to the project's root directory in your terminal.
*   Run the Flask app:
    ```bash
    python src/web_app.py
    ```
*   Open your web browser and go to `http://127.0.0.1:5000/`.
*   Enter your currency conversion query in the input field and click "Convert".

### 2. Command-Line Interface (CLI)

*   Navigate to the project's root directory.
*   Run the CLI script:
    ```bash
    python src/currency_converter_app.py
    ```
*   You will be prompted to enter your currency conversion query. Type your query and press Enter.
*   Type `exit` to quit the CLI.

## How It Works

1.  **Query Input**: The user provides a natural language query (e.g., "How much is 100 euros in Canadian dollars?").
2.  **LLM Parsing**: The query is sent to a Groq Llama 3 model (via LiteLLM) which is prompted to parse it into a structured JSON format: `{"amount": float, "from_currency": "ISO_CODE", "to_currency": "ISO_CODE"}`.
3.  **CrewAI Agent**:
    *   A CrewAI agent (`Currency Analyst`) is tasked with the conversion.
    *   This agent uses the `CurrencyConverterTool`.
4.  **CurrencyConverterTool**:
    *   This custom tool takes the structured input (amount, from_currency, to_currency).
    *   It calls the ExchangeRate-API to get the latest conversion rates for the `from_currency`.
    *   It calculates the converted amount.
    *   It returns a string with the conversion result (e.g., "100.0 EUR is equal to 146.50 CAD.").
5.  **Agent Response**: The `Currency Analyst` agent receives the tool's output. It then formulates a final response, potentially adding brief financial context if deemed relevant by its underlying LLM (Groq Llama 3 70b model).
6.  **Output**: The final response is displayed to the user, either on the web page or in the CLI.

## Code Overview

*   **`src/currency_converter_app.py`**:
    *   `CurrencyConverterInput`: Pydantic model for the structured query input.
    *   `CurrencyConverterTool`: Custom CrewAI tool that uses ExchangeRate-API.
    *   `parse_query_with_llm()`: Function to interact with Groq LLM for query parsing.
    *   `get_currency_conversion_response()`: Core function that orchestrates parsing, agent setup, task execution, and crew kickoff. This is imported by the Flask app.
    *   `main()`: Provides the CLI functionality.
*   **`src/web_app.py`**:
    *   Standard Flask application setup.
    *   `/` route: Renders the main `index.html` page.
    *   `/convert` route (POST): Receives the query from the web UI, calls `get_currency_conversion_response()`, and returns the result as JSON.
*   **`templates/index.html`**: Frontend HTML structure with a form and JavaScript for AJAX interaction with the `/convert` endpoint.
*   **`static/style.css`**: CSS for styling the web application.
*   **`config/appconfig.py`**: Handles loading of environment variables (API keys). This provides a centralized way to manage configuration, although the scripts also have a direct fallback to `os.getenv` if `appconfig` import fails or doesn't provide the keys.

## Customization and Extension

*   **LLM Models**: You can change the Groq models used for parsing or by the agent by modifying the `GROQ_PARSER_MODEL` and `GROQ_AGENT_MODEL` variables in `src/currency_converter_app.py`.
*   **Tool Enhancement**: The `CurrencyConverterTool` can be extended to provide more detailed information (e.g., historical rates, rate fluctuations) by modifying its `_run` method and the data it fetches.
*   **Agent Capabilities**: The agent's role, goal, and backstory can be tweaked to change its behavior or the type of financial context it provides.
*   **Frontend**: The web interface in `templates/index.html` and `static/style.css` can be further enhanced for a richer user experience.

## Troubleshooting

*   **API Key Errors**:
    *   Ensure your `.env` file is correctly formatted and contains valid API keys for ExchangeRate-API and Groq.
    *   Verify that `config/appconfig.py` is loading these keys as expected if you are relying on it. The scripts print messages about whether keys are loaded from `appconfig` or via fallback to `os.getenv`.
*   **`ModuleNotFoundError`**: If Flask or other scripts can't find `currency_converter_app`, ensure your `PYTHONPATH` is set up correctly or that you are running scripts from the project root where relative imports can be resolved. The `sys.path.append` in `src/web_app.py` attempts to handle this for co-located `src` files.
*   **LLM Errors (e.g., `ServiceUnavailableError`, `BadRequestError`)**:
    *   These can be transient issues with the LLM provider (Groq). Try again after a few minutes.
    *   `BadRequestError` from LiteLLM often indicates an issue with how the model or provider is specified. The current setup for the agent (`llm=GROQ_AGENT_MODEL` string) and parser (`model="groq/model-name"` in `litellm.completion`) is based on common working configurations.
*   **`Failed to get supported params: argument of type 'NoneType' is not iterable`**: This is an internal LiteLLM log message that might appear. If the application is otherwise working, it can sometimes be ignored. If it correlates with failures, it might indicate a version incompatibility or deeper configuration issue with LiteLLM or CrewAI.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit pull requests.
