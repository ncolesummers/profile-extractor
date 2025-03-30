import logging
import sys
from .config import LOG_TO_FILE, LOG_FILE_PATH  # Import logging configuration


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
            file_handler = logging.FileHandler(LOG_FILE_PATH)
            file_handler.setFormatter(log_formatter)
            root_logger.addHandler(file_handler)
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


# Example of how to call this at the start of your main script:
# from .utils import setup_logging
# logger = setup_logging()
# logger.info("Application started.")
