import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found in environment variables. Please set it in the .env file."
    )

# --- Model Configuration ---
# Use gemini-2.0-flash-latest for a balance of speed and capability
MODEL_NAME = "gemini-2.0-flash-latest"
LLM_TEMPERATURE = 0.1  # Low temperature for deterministic extraction

# --- Judge Model Configuration ---
# Can use the same model or a different one (e.g., a more powerful model if needed)
JUDGE_MODEL_NAME = "gemini-2.0-flash-latest"
JUDGE_TEMPERATURE = 0.1  # Low temperature for consistent validation

# --- Crawling Configuration ---
REQUEST_DELAY_SECONDS = 2.0  # Respectful delay between requests

# --- Output Configuration ---
OUTPUT_DIR = "output"
OUTPUT_FILENAME = "extracted_profiles.xlsx"

# --- Logging Configuration ---
LOG_TO_FILE = True  # Whether to log to a file in addition to console
LOG_FILE_PATH = "logs/app.log"  # Path to the log file

# You can add other configurations here as needed, e.g., logging settings
