import os
from flask import Flask, render_template, request, jsonify
import sys

# Ensure the src directory is in the Python path to import currency_converter_app
# This assumes web_app.py is in the src directory, and currency_converter_app.py is also in src
# If your project structure is different, this path adjustment might need to change.
# For a typical structure where web_app.py is at the root or in an 'app' folder,
# and currency_converter_app is in 'src', adjustments would be needed.
# Given both are in 'src' as per current plan:
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Attempt to import the core processing function
    from currency_converter_app import get_currency_conversion_response
except ImportError as e:
    print(f"Error importing currency_converter_app: {e}")
    # Fallback or alternative if direct import fails due to path issues in some environments
    # This can happen if the currency_converter_app itself has path issues when imported.
    # For now, we'll rely on the sys.path.append above.
    # A more robust solution might involve packaging your app or using a project runner that handles PYTHONPATH.
    def get_currency_conversion_response(query):
        return "Error: Could not load the currency conversion module. Please check server logs."

app = Flask(__name__, template_folder='../templates', static_folder='../static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if request.method == 'POST':
        try:
            data = request.get_json()
            natural_language_query = data.get('query')

            if not natural_language_query or not natural_language_query.strip():
                return jsonify({'error': 'Query cannot be empty.'}), 400

            print(f"Received query for /convert: {natural_language_query}")
            # Call the refactored function from your currency_converter_app
            response_message = get_currency_conversion_response(natural_language_query)

            # Basic check if the response indicates an error from the backend processing
            # You might want to refine this based on how get_currency_conversion_response signals errors
            if "error" in response_message.lower() or "could not parse" in response_message.lower():
                 print(f"Conversion process returned an error: {response_message}")
                 return jsonify({'error': response_message}), 500 # Internal Server Error or a more specific one

            print(f"Conversion successful: {response_message}")
            return jsonify({'response': response_message})

        except Exception as e:
            print(f"Exception in /convert: {e}")
            import traceback
            traceback.print_exc()
            # A more generic error for unexpected issues
            return jsonify({'error': 'An unexpected error occurred on the server.'}), 500
    else:
        # Method Not Allowed
        return jsonify({'error': 'Only POST requests are accepted for this endpoint.'}), 405

if __name__ == '__main__':
    # Make sure to set FLASK_ENV=development for debug mode if running with `flask run`
    # For `python src/web_app.py`, debug=True is fine for development.
    app.run(debug=True, port=5000) # Runs on http://127.0.0.1:5000/
