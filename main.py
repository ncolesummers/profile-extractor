import os
import time
import sys
import uuid
import logging  # Import logging directly
from typing import List, Dict, Any

# Force LangChain daemon threads EARLY
os.environ["LANGCHAIN_HANDLER_THREAD_DAEMON"] = "true"

# Import application components
from src.config import settings
from src.setup import (
    setup_logging,  # Function to create the logger
    setup_langsmith,  # Function to setup LangSmith client
    ShutdownManager,  # Class for managing shutdown
    register_signal_handlers,  # Function to register handlers
)
from src.utils import format_duration
from src.graph import app as langgraph_app  # Import the compiled LangGraph app
from src.processing import run_processing_loop, load_urls
from src.cleanup import cleanup_resources
from src.reporting import calculate_metrics, save_results

# Remove global logger and langsmith_client setup
# logger = setup_logging()
# langsmith_client = setup_langsmith(settings, logger)

# Remove conditional traceable import - handled in processing.py
# if langsmith_client:
#     ...
# else:
#     ...


def main():
    """Main entry point for the profile extraction process."""

    # --- Initialization within main --- #
    logger = setup_logging()
    logger.info("Application started.")

    # Pass logger to LangSmith setup
    langsmith_client = setup_langsmith(settings, logger)

    shutdown_manager = ShutdownManager()

    # Pass logger to signal handler registration
    register_signal_handlers(shutdown_manager, logger)

    session_id = f"extraction-session-{uuid.uuid4()}"
    logger.info(f"Starting extraction session: {session_id}")

    start_time = time.time()
    results = []
    interrupted = False
    exit_code = 0  # Default to success

    try:
        # Pass logger to load_urls
        urls = load_urls(logger)

        # Pass logger, settings, and app to processing loop
        results, interrupted = run_processing_loop(
            urls, shutdown_manager, langgraph_app, settings, logger
        )

        # --- Metrics Calculation --- #
        metrics = {}
        if interrupted:
            logger.warning(
                f"Processing interrupted. Calculating metrics for {len(results)} completed URLs."
            )
            if results:
                try:
                    logger.info("Calculating metrics for partial results...")
                    # Pass logger, settings, and client
                    metrics = calculate_metrics(
                        results, settings, logger, langsmith_client
                    )
                    logger.info("Partial metrics calculation complete.")
                except Exception as e:
                    logger.error(
                        f"Error calculating partial metrics: {e}", exc_info=True
                    )
            else:
                logger.warning("No results processed, skipping metrics.")
        elif not results:
            logger.warning("No results generated. Skipping metrics calculation.")
        else:
            try:
                logger.info("Calculating final metrics...")
                # Pass logger, settings, and client
                metrics = calculate_metrics(results, settings, logger, langsmith_client)
                logger.info("Metrics calculation complete.")
            except Exception as e:
                logger.error(f"Error calculating final metrics: {e}", exc_info=True)

        # --- Save Results --- #
        if results:
            logger.info("Saving results...")
            try:
                # Pass logger and settings
                save_results(results, metrics, settings, logger)
                logger.info("Results saving process complete.")
            except Exception as e:
                logger.error(f"Error saving results: {e}", exc_info=True)
        else:
            logger.warning("No results generated, nothing to save.")

        if interrupted:
            logger.info("Processing was interrupted by user or signal.")
        else:
            logger.info("Profile extraction process completed successfully.")

    except FileNotFoundError as e:  # Specific catch for URL loading issues
        logger.error(f"Fatal error: {e}. Cannot load URLs.")
        exit_code = 1
    except Exception as e:
        logger.error(f"Fatal error in main process: {str(e)}", exc_info=True)
        exit_code = 1
        # Cleanup will happen in finally

    finally:
        end_time = time.time()
        total_duration = end_time - start_time
        logger.info(f"Total execution time: {format_duration(total_duration)}")

        # Pass logger and client to cleanup
        # Note: The global _cleanup_done flag inside cleanup_resources prevents double execution
        # even if called from both the except block (pre-finally) and here.
        cleanup_resources(logger, langsmith_client)

        logger.info(f"Exiting with code {exit_code}.")
        # Use sys.exit with the determined code
        # Note: If cleanup hangs, this exit might still be blocked. The cleanup refactoring aimed to prevent hangs.
        sys.exit(exit_code)


if __name__ == "__main__":
    # Keep top-level try-except for unexpected crashes before main() starts or after it exits
    # Note: logger might not be initialized if error happens *before* main()
    # Consider basic logging config here or ensure setup_logging is robust
    try:
        main()  # This now contains the sys.exit call
    except SystemExit as e:  # Catch sys.exit to prevent double logging/cleanup
        # main() already handled logging and cleanup before exiting
        pass  # Exit silently as intended
    except Exception as e:
        # Log critical error if main() failed catastrophically before its own logging/cleanup
        # It's possible logger isn't set up yet here
        try:
            logging.getLogger(__name__).critical(
                f"Unhandled top-level exception: {e}", exc_info=True
            )
        except Exception:  # Fallback if even basic logging fails
            print(f"CRITICAL UNHANDLED EXCEPTION: {e}", file=sys.stderr)

        # Attempt last-ditch cleanup, might fail if resources are badly broken
        try:
            # Attempt cleanup without logger/client if main didn't initialize them
            # This relies on cleanup_resources handling None inputs gracefully
            cleanup_resources(logging.getLogger(__name__), None)
        except Exception as cleanup_err:
            print(
                f"CRITICAL: Error during final cleanup attempt: {cleanup_err}",
                file=sys.stderr,
            )

        sys.exit(1)  # Exit with error code after attempting log/cleanup
