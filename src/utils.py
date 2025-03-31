import logging
import sys
import os
import json
import time  # Added for format_duration
from datetime import datetime
from pathlib import Path
import tiktoken


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
