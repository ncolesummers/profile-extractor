import os
import time
import sys
import threading
import signal
import uuid
from typing import List, Dict, Any
import pandas as pd
from pathlib import Path

# Force LangChain to use daemon threads for its handlers
os.environ["LANGCHAIN_HANDLER_THREAD_DAEMON"] = "true"

# Import our application components
from src.setup import (
    setup_logging,
    setup_langsmith,
    ShutdownManager,
    register_signal_handlers,
)
from src.utils import format_duration
from src.graph import app  # This is our compiled LangGraph application
from src.config import settings  # Import the settings object
from src.schemas import ProfileData
from src.processing import run_processing_loop, load_urls  # Import load_urls
from src.cleanup import cleanup_resources  # Import the new cleanup function

# Import reporting functions
from src.reporting import calculate_metrics, save_results

# Set up logging FIRST
logger = setup_logging()
logger.info("Application started.")

# Set up LangSmith
langsmith_client = setup_langsmith(settings)

# Conditionally import traceable based on langsmith_client initialization
if langsmith_client:
    try:
        from langsmith import traceable

        # You might need to explicitly patch or configure traceable further depending on usage
    except ImportError:
        logger.warning("'langsmith' package is not installed, tracing disabled.")
        traceable = lambda func=None, **kwargs: (func if func else lambda f: f)
    except Exception as e:
        logger.error(f"Failed to import or setup traceable: {e}")
        traceable = lambda func=None, **kwargs: (func if func else lambda f: f)
else:
    traceable = lambda func=None, **kwargs: (
        func if func else lambda f: f
    )  # No-op traceable


def main():
    """Main entry point for the profile extraction process."""
    start_time = time.time()  # Record start time

    # Initialize Shutdown Manager
    shutdown_manager = ShutdownManager()

    # Register Signal Handlers
    register_signal_handlers(shutdown_manager)

    # Create a session_id for this run to group all profiles in LangSmith
    session_id = f"extraction-session-{uuid.uuid4()}"
    logger.info(f"Starting extraction session: {session_id}")

    results = []  # Initialize results list
    interrupted = False  # Initialize interrupted flag

    try:
        # Load URLs to process
        urls = load_urls()

        # Run the main processing loop
        results, interrupted = run_processing_loop(urls, shutdown_manager)

        # --- Metrics Calculation (Sequential) ---
        metrics = {}
        if interrupted:
            logger.warning(
                f"Processing interrupted. Calculating metrics for {len(results)} completed URLs."
            )
            if (
                results
            ):  # Calculate metrics only if some results were actually processed
                try:
                    logger.info("Calculating metrics for partial results...")
                    # Pass settings and langsmith_client
                    metrics = calculate_metrics(results, settings, langsmith_client)
                    logger.info("Partial metrics calculation complete.")
                except Exception as e:
                    logger.error(
                        f"Error calculating metrics for partial results: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "No results processed before interruption, skipping metrics."
                )

        elif not results:
            logger.warning("No results were generated. Skipping metrics calculation.")
        else:  # Processing finished normally or was interrupted after completion
            try:
                logger.info("Calculating final metrics...")
                # Pass settings and langsmith_client
                metrics = calculate_metrics(results, settings, langsmith_client)
                logger.info("Metrics calculation complete.")
            except Exception as e:
                logger.error(f"Error calculating final metrics: {e}", exc_info=True)
                # Continue with saving results even if metrics failed

        # --- Save Results --- #
        if results:
            logger.info("Saving results...")
            try:
                # Pass settings
                save_results(results, metrics, settings)
                logger.info("Results saving process complete.")
            except Exception as e:
                logger.error(f"Error saving results: {e}", exc_info=True)
        else:
            logger.warning("No results generated, nothing to save.")

        if interrupted:
            logger.info("Processing was interrupted.")
        else:
            logger.info("Profile extraction process completed successfully.")

    except Exception as e:
        # Catch other potential errors during loading or setup
        logger.error(f"Fatal error in main process: {str(e)}", exc_info=True)
        # Ensure cleanup happens even on unexpected errors before the finally block might
        cleanup_resources(langsmith_client)
        sys.exit(1)  # Exit with error code

    finally:
        end_time = time.time()
        total_duration = end_time - start_time
        logger.info(f"Total execution time: {format_duration(total_duration)}")

        # Clean up other resources (LangSmith, requests, etc.)
        cleanup_resources(langsmith_client)

        # Standard exit after cleanup
        logger.info("Exiting gracefully via sys.exit(0).")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        cleanup_resources(langsmith_client)
        sys.exit(1)
