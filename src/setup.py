# Application setup functions

import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Import both the class and the instance if needed, or just the class for type hints
from .config import Settings, settings
import signal
from typing import Optional, Any

# Attempt to import langsmith, handle gracefully if not installed
try:
    from langsmith import Client
except ImportError:
    Client = None  # Set Client to None if langsmith is not installed

# Logger setup moved to main, but keep type hint for passing logger
Logger = logging.Logger


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
    if settings.LOG_TO_FILE:
        try:
            log_path = Path(settings.LOG_FILE_PATH)
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
                f"Could not open log file {settings.LOG_FILE_PATH} for writing. "
                f"File logging disabled."
            )
        except Exception as e:
            root_logger.warning(
                f"Failed to set up file logging to {settings.LOG_FILE_PATH}: {e}. "
                f"File logging disabled."
            )

    root_logger.info("Logging configured.")
    return root_logger


def setup_langsmith(settings: Settings, logger: Logger) -> Optional[Any]:
    """Initializes LangSmith client and tracing if API key is available.

    Args:
        settings_obj: The application settings object.

    Returns:
        An initialized LangSmith Client instance or None.
    """
    langsmith_client = None

    if settings.LANGSMITH_API_KEY:
        if Client is None:
            logger.warning(
                "LangSmith API Key found, but 'langsmith' package is not installed. Tracing disabled."
            )
        else:
            try:
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
                os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
                logger.info(
                    f"LangSmith tracing enabled for project: {settings.LANGSMITH_PROJECT}"
                )

                # Initialize client with auto_batch_tracing disabled
                langsmith_client = Client(
                    api_key=settings.LANGSMITH_API_KEY, auto_batch_tracing=False
                )
                logger.info(
                    "LangSmith Client initialized with auto_batch_tracing=False"
                )
            except ImportError:
                logger.warning(
                    "'langsmith' package not found, but LANGSMITH_API_KEY is set. Tracing disabled."
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize LangSmith client: {e}", exc_info=True
                )
                langsmith_client = None  # Ensure client is None on error
    else:
        logger.info("LangSmith API key not found. Tracing disabled")

    return langsmith_client


# Note: The 'traceable' decorator logic needs to be handled where it's used (e.g., main.py or processing.py)
# It can be conditionally imported based on whether langsmith_client is successfully initialized.


class ShutdownManager:
    """Manages the graceful shutdown state of the application."""

    def __init__(self):
        self._shutdown_requested = False
        self._logger = logging.getLogger(__name__)  # Use logger for messages

    def request_shutdown(self):
        """Signal that shutdown has been requested."""
        if not self._shutdown_requested:
            self._logger.info("Graceful shutdown requested.")
            self._shutdown_requested = True
        else:
            self._logger.debug("Shutdown already requested.")  # Avoid duplicate logs

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested


# Note: The signal handler needs access to the shutdown_manager instance.
# We pass it using a closure or functools.partial when registering.


def signal_handler(sig, frame, shutdown_manager: ShutdownManager, logger: Logger):
    """Handle termination signals gracefully."""
    if not shutdown_manager.is_shutdown_requested():
        logger.warning(f"Received signal {sig}. Initiating graceful shutdown...")
        shutdown_manager.request_shutdown()
    else:
        logger.warning(f"Received signal {sig} again. Shutdown already in progress.")


def register_signal_handlers(shutdown_manager: ShutdownManager, logger: Logger):
    """Register signal handlers for SIGINT and SIGTERM."""
    logger.info("Registering signal handlers...")
    # Use a lambda or partial to pass the manager and logger to the handler
    handler = lambda sig, frame: signal_handler(sig, frame, shutdown_manager, logger)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    logger.info("Signal handlers registered.")
