import os
from typing import Dict, Any, Optional
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine the base directory of the project
# This assumes config.py is in src/ and .env is in the root
# Adjust if your structure is different
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables and .env file."""

    # --- API Keys ---
    GOOGLE_API_KEY: str = Field(..., description="Google API Key for Gemini models.")

    # --- LangSmith Configuration ---
    LANGSMITH_API_KEY: Optional[str] = Field(
        None, description="API Key for LangSmith tracing."
    )
    LANGSMITH_PROJECT: str = Field(
        "profile-extractor", description="LangSmith project name."
    )
    # LangSmith tracing V2 is enabled automatically when LANGSMITH_API_KEY is set

    # --- Thread Tracking Configuration ---
    ENABLE_THREAD_TRACKING: bool = Field(
        True, description="Enable thread tracking for organizing related LLM calls."
    )
    THREAD_ID_PREFIX: str = Field(
        "profile-thread", description="Prefix for thread IDs."
    )
    SESSION_METADATA: Dict[str, Any] = Field(
        default_factory=lambda: {
            "app_version": "0.1.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
        },
        description="Session metadata to include with every run.",
    )

    # --- Model Configuration ---
    MODEL_NAME: str = Field(
        "gemini-2.0-flash", description="Model name for primary LLM tasks."
    )
    LLM_TEMPERATURE: float = Field(
        0.1, description="Temperature for primary LLM tasks."
    )

    # --- Judge Model Configuration ---
    JUDGE_MODEL_NAME: str = Field(
        "gemini-2.0-flash", description="Model name for validation/judging tasks."
    )
    JUDGE_TEMPERATURE: float = Field(
        0.1, description="Temperature for validation/judging tasks."
    )

    # --- Crawling Configuration ---
    REQUEST_DELAY_SECONDS: float = Field(
        2.0, description="Delay between web requests in seconds."
    )

    # --- Output Configuration ---
    OUTPUT_DIR: str = Field("output", description="Directory for output files.")
    OUTPUT_FILENAME: str = Field(
        "extracted_profiles.xlsx", description="Filename for the output Excel file."
    )

    # --- Logging Configuration ---
    LOG_TO_FILE: bool = Field(True, description="Enable logging to a file.")
    LOG_FILE_PATH: str = Field("logs/app.log", description="Path to the log file.")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,  # Load from .env file
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields from environment/env file
    )


# Instantiate the settings
try:
    settings = Settings()
    # You could add a print statement here for debugging if needed,
    # but avoid printing sensitive keys like API keys in production logs.
    # print("Settings loaded successfully:")
    # print(settings.model_dump(exclude={'GOOGLE_API_KEY', 'LANGSMITH_API_KEY'}))
except ValidationError as e:
    print(f"Error loading configuration: {e}")
    # Decide how to handle validation errors, e.g., exit the application
    import sys

    sys.exit(1)


# --- Example Usage (Optional - for direct execution testing) ---
if __name__ == "__main__":
    print("Configuration loaded:")
    # Be careful about printing sensitive keys
    print(f"  Google API Key: {'Set' if settings.GOOGLE_API_KEY else 'Not Set'}")
    print(f"  LangSmith API Key: {'Set' if settings.LANGSMITH_API_KEY else 'Not Set'}")
    print(f"  LangSmith Project: {settings.LANGSMITH_PROJECT}")
    print(f"  Output Directory: {settings.OUTPUT_DIR}")
    print(f"  Log File Path: {settings.LOG_FILE_PATH}")
    # Add more prints as needed for testing
