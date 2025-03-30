import logging
import sys
import os
import json
import time  # Added for format_duration
from datetime import datetime
from pathlib import Path
from .config import LOG_TO_FILE, LOG_FILE_PATH  # Import logging configuration
import tiktoken


def setup_logging(level=logging.INFO):
    """Configures the root logger for the application."""
    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicate logs if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if configured
    if LOG_TO_FILE:
        try:
            log_path = Path(LOG_FILE_PATH)
            # Create directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # Add timestamp to filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"{log_path.stem}_{timestamp}{log_path.suffix}"
            final_log_path = log_path.parent / log_filename

            file_handler = logging.FileHandler(final_log_path)
            file_handler.setFormatter(log_formatter)
            root_logger.addHandler(file_handler)
            root_logger.info(
                f"Logging to file: {final_log_path}"
            )  # Log the actual path used
        except PermissionError:
            root_logger.warning(
                f"Could not open log file {LOG_FILE_PATH} for writing. "
                f"File logging disabled."
            )
        except Exception as e:
            root_logger.warning(
                f"Failed to set up file logging to {LOG_FILE_PATH}: {e}. "
                f"File logging disabled."
            )

    root_logger.info("Logging configured.")
    return root_logger


def dump_debug_info(state, debug_dir="logs/debug"):
    """Dumps state information to a debug file for analysis.

    Args:
        state: The graph state to dump
        debug_dir: Directory to save debug files
    """
    # Create debug directory if it doesn't exist
    Path(debug_dir).mkdir(exist_ok=True, parents=True)

    # Create a filename with URL and timestamp
    url_part = state.get("url", "unknown").split("/")[-1].replace(".html", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_file = f"{debug_dir}/{timestamp}_{url_part}.json"

    # Create a simplified state for debugging (exclude large HTML content)
    debug_state = {
        "url": state.get("url"),
        "error": state.get("error"),
        "error_details": state.get("error_details"),
        "metrics": state.get("metrics"),
    }

    # Add extracted data if present
    if state.get("extracted_data"):
        try:
            debug_state["extracted_data"] = state["extracted_data"].model_dump()
        except Exception as e:
            debug_state["extracted_data_error"] = str(e)

    # Add validation result if present
    if state.get("validation_result"):
        try:
            debug_state["validation_result"] = state["validation_result"].model_dump()
        except Exception as e:
            debug_state["validation_result_error"] = str(e)

    # Write to file
    with open(debug_file, "w") as f:
        json.dump(debug_state, f, indent=2)

    return debug_file


# Example of how to call this at the start of your main script:
# from .utils import setup_logging
# logger = setup_logging()
# logger.info("Application started.")


# Add the new helper function at the end of the file
def format_duration(seconds: float) -> str:
    """Formats a duration in seconds into a human-readable string."""
    if seconds < 0:
        return "0s"

    total_seconds = int(seconds)
    milliseconds = int((seconds - total_seconds) * 1000)

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    if milliseconds > 0 and not parts:  # Only show ms if duration is less than 1 second
        parts.append(f"{milliseconds}ms")
    elif not parts and total_seconds == 0 and milliseconds == 0:
        return "0s"

    return " ".join(parts)


def count_tokens(text: str) -> int:
    """Count tokens in a string using tiktoken's cl100k_base encoding.

    This is a fallback for when the model doesn't provide token counts.
    Using cl100k_base as a reasonable approximation for Gemini models.
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception:
        # If encoding fails, use a rough approximation
        # Approximate 4 characters per token on average
        return len(text) // 4
