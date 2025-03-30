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

# --- LangSmith Configuration ---
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "profile-extractor")
LANGSMITH_TRACING_V2 = os.getenv("LANGSMITH_TRACING_V2", "true")

# --- Thread Tracking Configuration ---
# Enable thread tracking for organizing related LLM calls
ENABLE_THREAD_TRACKING = True
# The prefix used for thread IDs to make them easily identifiable
THREAD_ID_PREFIX = "profile-thread"
# Session metadata to include with every run
SESSION_METADATA = {
    "app_version": "0.1.0",
    "environment": os.getenv("ENVIRONMENT", "development"),
}

# --- Model Configuration ---
# Use gemini-2.0-flash-latest for a balance of speed and capability
MODEL_NAME = "gemini-2.0-flash"
LLM_TEMPERATURE = 0.1  # Low temperature for deterministic extraction

# --- Judge Model Configuration ---
# Can use the same model or a different one (e.g., a more powerful model if needed)
JUDGE_MODEL_NAME = "gemini-2.0-flash"
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
