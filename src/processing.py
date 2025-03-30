# Core URL processing logic

import logging
import uuid
import os
import time
import json  # Import json
from pathlib import Path  # Import Path
from typing import Dict, Any, List, Tuple
from tqdm import tqdm
import traceback  # For formatting exceptions

# Import necessary components from the project
from .graph import app as langgraph_app  # Import the app
from .config import settings  # For potential config access if needed later
from .setup import ShutdownManager  # Import type hint
from langgraph.graph.state import StateGraph  # For type hint if needed
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.base import Checkpoint  # For type hint
from langgraph.prebuilt import tools_condition

from .config import Settings
from .schemas import ProfileData

# from .utils import logger as utils_logger # Remove or keep if needed, prefer passed logger
# Restore specific imports from nodes needed here
# Remove LANGSMITH_API_KEY_SET as it's determined from settings now
from .nodes import GEMINI_FLASH_PRICING

# Setup logger for this module
logger = logging.getLogger(__name__)

# --- Conditional LangSmith Import --- #
# We need the langsmith client to determine if tracing is active,
# but setup_langsmith is in src.setup, which might import this module,
# potentially causing a circular import if we import setup_langsmith here.
# Instead, we rely on the environment variables set by setup_langsmith
# or check the settings directly.

LANGSMITH_API_KEY_SET = bool(settings.LANGSMITH_API_KEY)

if LANGSMITH_API_KEY_SET:
    try:
        from langsmith import traceable

        logger.debug("LangSmith traceable decorator imported.")
    except ImportError:
        logger.warning(
            "LangSmith API key set, but 'langsmith' pkg not installed. Traceable disabled."
        )
        traceable = lambda func=None, **kwargs: (func if func else lambda f: f)
else:
    logger.debug("LangSmith tracing disabled, using no-op traceable.")
    traceable = lambda func=None, **kwargs: (func if func else lambda f: f)


# --- Data Loading --- #
def load_urls(logger: logging.Logger) -> List[str]:
    """Load URLs from the data directory (e.g., data/uidaho_urls.json)."""
    # Determine path relative to this file or project root
    # Assuming this file is in src/ and data/ is at the project root
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    data_dir = project_root / "data"
    # TODO: Make the filename configurable via settings?
    urls_filename = "uidaho_urls.json"
    urls_file = data_dir / urls_filename

    logger.info(f"Attempting to load URLs from: {urls_file}")

    if not urls_file.exists():
        logger.error(f"URLs file not found at {urls_file}")
        raise FileNotFoundError(f"URLs file not found at {urls_file}")

    try:
        with open(urls_file, "r") as f:
            urls = json.load(f)

        if not isinstance(urls, list):
            logger.error(f"Invalid format in {urls_file}. Expected a JSON list.")
            raise ValueError(f"Invalid format in {urls_file}. Expected a JSON list.")

        logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
        return urls
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {urls_file}: {e}")
        raise ValueError(f"Error decoding JSON from {urls_file}: {e}") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred loading URLs from {urls_file}: {e}",
            exc_info=True,
        )
        raise


# --- Processing Function --- #


@traceable(name="Process URL")  # Apply the decorator
def process_url(
    url: str,
    langgraph_app: Any,  # Replace Any with actual CompiledGraph type if known
    settings: Settings,
    logger: logging.Logger,
    thread_id: str = None,
) -> Dict[str, Any]:
    """Process a single URL through the graph workflow.

    Args:
        url: The URL to process
        langgraph_app: The compiled LangGraph application instance
        settings: The application settings object
        logger: The logger instance
        thread_id: Optional thread ID for LangSmith tracing

    Returns:
        The final state dictionary after processing
    """
    logger.info(f"Processing URL: {url}")

    # Generate thread_id if not provided (for tracing)
    if thread_id is None:
        # Use the prefix from settings if available
        prefix = (
            settings.THREAD_ID_PREFIX
            if hasattr(settings, "THREAD_ID_PREFIX")
            else "profile"
        )
        thread_id = f"{prefix}-{uuid.uuid4()}"
        logger.debug(f"Generated thread_id: {thread_id}")

    # Initialize state for this URL
    # This matches the expected input structure for the LangGraph app
    initial_state = {
        "url": url,
        "metrics": {},
        "error": None,
        "error_details": None,
        "html_content": None,
        "preprocessed_content": None,
        "extracted_data": None,
        "validation_result": None,
        "thread_id": thread_id,  # Pass thread_id into the initial state
    }

    try:
        # Process the URL through our graph
        # Set metadata for LangSmith if traceable is active
        langsmith_config = {}
        if settings.LANGSMITH_API_KEY and settings.LANGSMITH_PROJECT:
            # Pass thread_id and other relevant info for LangSmith UI
            langsmith_config["metadata"] = {
                "thread_id": thread_id,
                "url": url,
                **settings.SESSION_METADATA,  # Include session metadata
            }
            # If you need configurable tags:
            # langsmith_config["tags"] = ["profile_extraction", settings.ENVIRONMENT]
            logger.debug(
                f"Setting LangSmith metadata for {url}: {langsmith_config['metadata']}"
            )
        else:
            logger.debug("LangSmith not configured, skipping metadata.")

        # Add thread_id to config for LangSmith run identification
        langsmith_config["configurable"] = {"thread_id": thread_id}

        # Force sequential execution within the graph for stability
        # Combine LangSmith config with execution config
        final_config = {"max_concurrency": 1, **langsmith_config}

        logger.debug(f"Invoking LangGraph app for {url} with config: {final_config}")
        final_state = langgraph_app.invoke(initial_state, config=final_config)
        logger.info(f"Completed processing {url}")

        # Ensure metrics dictionary exists and add thread_id if not already present by a node
        if "metrics" not in final_state:
            final_state["metrics"] = {}
        if "thread_id" not in final_state["metrics"]:
            final_state["metrics"]["thread_id"] = thread_id

        # Ensure thread_id is in the top-level state for consistency
        if "thread_id" not in final_state:
            final_state["thread_id"] = thread_id

        return final_state

    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}", exc_info=True)
        # Return a consistent error state structure
        return {
            "url": url,
            "thread_id": thread_id,
            "error": str(e),
            "error_details": {
                "exception": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
            "metrics": {
                "thread_id": thread_id
            },  # Ensure thread_id is in metrics on error
            # Include other state keys as None or default values if needed downstream
            "html_content": None,
            "preprocessed_content": None,
            "extracted_data": None,
            "validation_result": None,
        }


# --- Processing Loop --- #


def run_processing_loop(
    urls: List[str],
    shutdown_manager: ShutdownManager,
    langgraph_app: Any,  # Replace Any with actual CompiledGraph type if known
    settings: Settings,
    logger: logging.Logger,
    # Add traceable wrapper if needed, or handle in main
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Iterates through URLs, processes them using the LangGraph app, and handles interruptions.

    Args:
        urls: A list of URLs to process.
        shutdown_manager: An instance of ShutdownManager to check for shutdown requests.
        langgraph_app: The compiled LangGraph application instance.
        settings: The application settings object.
        logger: The logger instance.

    Returns:
        A tuple containing:
            - A list of result dictionaries from processing each URL.
            - A boolean flag indicating if the loop was interrupted.
    """
    results = []
    interrupted = False
    logger.info(f"Starting processing loop for {len(urls)} URLs...")

    # Determine if traceable should be used based on settings
    use_traceable = False
    if settings.LANGSMITH_API_KEY and settings.LANGSMITH_PROJECT:
        try:
            from langsmith import traceable as langsmith_traceable

            use_traceable = True
            logger.debug("LangSmith traceable is available.")
        except ImportError:
            logger.warning(
                "'langsmith' package not installed, tracing disabled within loop."
            )
            langsmith_traceable = lambda func=None, **kwargs: (
                func if func else lambda f: f
            )
    else:
        logger.debug("LangSmith not configured, tracing disabled within loop.")
        langsmith_traceable = lambda func=None, **kwargs: (
            func if func else lambda f: f
        )

    # Wrapper for process_url to apply traceable conditionally
    def potentially_traced_process_url(*args, **kwargs):
        _url = kwargs.get("url") or (args[0] if args else "unknown")
        if use_traceable:

            @langsmith_traceable(name=f"Process URL: {_url[:50]}...")
            def traced_call():
                return process_url(*args, **kwargs)

            return traced_call()
        else:
            return process_url(*args, **kwargs)

    try:
        with tqdm(
            total=len(urls),
            desc="Processing URLs",
            unit="profile",
            position=0,
            leave=True,
        ) as pbar:
            for url in urls:
                # Check for shutdown signal before processing next URL
                if shutdown_manager.is_shutdown_requested():
                    logger.warning("Shutdown requested, stopping URL processing loop.")
                    interrupted = True
                    break  # Exit the loop gracefully

                # process_url now generates its own thread_id if needed
                try:
                    # Call process_url through the wrapper, passing necessary args
                    result = potentially_traced_process_url(
                        url=url,
                        langgraph_app=langgraph_app,
                        settings=settings,
                        logger=logger,
                        thread_id=None,  # process_url handles thread_id generation
                    )
                    results.append(result)
                except Exception as e:
                    # Log error during process_url call itself (should be rare if process_url catches its own errors)
                    logger.error(
                        f"Unexpected error calling process_url wrapper for {url}: {e}",
                        exc_info=True,
                    )
                    # Append an error result to maintain consistency
                    results.append(
                        {
                            "url": url,
                            "error": f"Outer loop error: {e}",
                            "error_details": {
                                "exception": type(e).__name__,
                                "traceback": traceback.format_exc(),
                            },
                            "metrics": {},  # Add basic metrics structure if needed downstream
                            # Ensure other fields expected downstream are present, e.g., as None
                            "thread_id": "unknown-error",
                            "html_content": None,
                            "preprocessed_content": None,
                            "extracted_data": None,
                            "validation_result": None,
                        }
                    )

                # Optional: Original sleep logic - consider if still needed
                # time.sleep(0.5) # This might be better handled within node logic (e.g., fetch)

                pbar.update(1)  # Update progress bar

    except KeyboardInterrupt:
        # This handles Ctrl+C *during* the tqdm loop setup or iteration logic
        logger.warning(
            "Keyboard interrupt detected during processing loop. Stopping gracefully..."
        )
        interrupted = True
    except Exception as e:
        # Catch any other unexpected errors during the loop itself
        logger.error(f"Fatal error during processing loop: {e}", exc_info=True)
        interrupted = True  # Treat as interruption/failure
        return results, interrupted

    if interrupted:
        logger.info(f"Processing loop interrupted. Processed {len(results)} URLs.")
    else:
        logger.info(f"Processing loop completed. Processed {len(results)} URLs.")

    return results, interrupted
