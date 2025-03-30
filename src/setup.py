# Application setup functions

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from .config import settings  # Import the settings object
import signal

# Attempt to import langsmith, handle gracefully if not installed
try:
    from langsmith import Client
except ImportError:
    Client = None  # Set Client to None if langsmith is not installed


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


def setup_langsmith(settings_obj):
    """Initializes LangSmith client and tracing if API key is available.

    Args:
        settings_obj: The application settings object.

    Returns:
        An initialized LangSmith Client instance or None.
    """
    logger = logging.getLogger(__name__)  # Get logger for this module
    langsmith_client = None

    if settings_obj.LANGSMITH_API_KEY:
        if Client is None:
            logger.warning(
                "LangSmith API Key found, but 'langsmith' package is not installed. Tracing disabled."
            )
        else:
            try:
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = settings_obj.LANGSMITH_API_KEY
                os.environ["LANGSMITH_PROJECT"] = settings_obj.LANGSMITH_PROJECT
                logger.info("LangSmith tracing enabled")

                # Initialize client with auto_batch_tracing disabled
                langsmith_client = Client(
                    api_key=settings_obj.LANGSMITH_API_KEY, auto_batch_tracing=False
                )
                logger.info(
                    "LangSmith Client initialized with auto_batch_tracing=False"
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize LangSmith client: {e}", exc_info=True
                )
                langsmith_client = None  # Ensure client is None on error
    else:
        logger.info("LangSmith API key not found, tracing disabled")

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


def _signal_handler_func(signum, frame, manager: ShutdownManager):
    """Internal signal handler function that calls request_shutdown on the manager."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signal.Signals(signum).name} ({signum}).")
    manager.request_shutdown()


def register_signal_handlers(manager: ShutdownManager):
    """Registers signal handlers for SIGINT and SIGTERM."""
    logger = logging.getLogger(__name__)
    try:
        # Use functools.partial to pass the manager instance to the handler
        from functools import partial

        handler = partial(_signal_handler_func, manager=manager)

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        logger.info("Registered signal handlers for SIGINT and SIGTERM.")
    except Exception as e:
        logger.error(f"Failed to register signal handlers: {e}", exc_info=True)
