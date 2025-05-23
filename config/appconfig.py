import os
import re
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Define log directory path
LOGS_DIR = Path(__file__).parent.parent / 'logs'
# Create logs directory if it doesn't exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'config.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    # Path configuration
    root_dir = Path(__file__).parent.parent.resolve()
    env_path = root_dir / '.env'

    # Check for .env existence (optional for deployment, useful locally)
    # if not env_path.exists():
    #     logger.warning(f"No .env file found at {env_path}. Relying solely on system environment variables.")
        # sys.exit(1) # DO NOT EXIT IN DEPLOYMENT IF FILE IS MISSING

    # Attempt to load .env if it exists. If not, it will do nothing.
    load_dotenv(env_path)
    logger.info(f"Loaded environment variables from {env_path}")

    # Required environment variables
    REQUIRED_VARS = [
        'OPENAI_API_KEY', 'SERPER_API_KEY', 'EXCHANGE_RATE_API_KEY', 'GOOGLE_API_KEY', 'GROQ_API_KEY'
    ]

    # Load environment variables
    config = {var: os.getenv(var) for var in REQUIRED_VARS}

    missing_vars = [var for var in REQUIRED_VARS if config[var] is None]
    if missing_vars:
        logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Export variables
    OPENAI_API_KEY = config['OPENAI_API_KEY']
    SERPER_API_KEY = config['SERPER_API_KEY']
    EXCHANGE_RATE_API_KEY = config['EXCHANGE_RATE_API_KEY']
    GOOGLE_API_KEY = config['GOOGLE_API_KEY']
    GROQ_API_KEY = config['GROQ_API_KEY']

    sensitive_vars = ['OPENAI_API_KEY', 'SERPER_API_KEY', 'EXCHANGE_RATE_API_KEY', 'GOOGLE_API_KEY', 'GROQ_API_KEY']
    for var in REQUIRED_VARS:
        value = locals().get(var, '')
        logged_value = f"{value[:2]}****{value[-2:]}" if var in sensitive_vars and len(value) > 4 else str(value)
        logger.info(f"{var}: {logged_value}")

    logger.info("Configuration loaded successfully")

except Exception as e:
    logger.critical(f"Configuration initialization failed: {str(e)}")
    sys.exit(1)

__all__ = REQUIRED_VARS
