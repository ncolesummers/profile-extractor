import os
import time
import sys
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple

# Force LangChain daemon threads EARLY
os.environ["LANGCHAIN_HANDLER_THREAD_DAEMON"] = "true"

# Import application components
from src.config import settings, Settings  # Import Settings type hint
from src.setup import (
    setup_logging,
    setup_langsmith,
    ShutdownManager,
    register_signal_handlers,
)
from src.utils import format_duration
from src.graph import app as langgraph_app
from src.processing import run_processing_loop, load_urls
from src.cleanup import cleanup_resources
from src.reporting import calculate_metrics, save_results

# LangSmith client type hint (replace with actual type if available)
LangSmithClient = Any


class ProfileExtractorApp:
    """Encapsulates the profile extraction application state and logic."""

    def __init__(self):
        """Initialize the application."""
        self.settings: Settings = settings
        self.logger: logging.Logger = setup_logging()
        self.shutdown_manager: ShutdownManager = ShutdownManager()
        self.langsmith_client: Optional[LangSmithClient] = None
        self.results: List[Dict[str, Any]] = []
        self.interrupted: bool = False
        self.exit_code: int = 0
        self.start_time: Optional[float] = None

    def _setup_app(self) -> None:
        """Perform initial setup tasks like logging, LangSmith, and signal handling."""
        self.logger.info("Application setup started.")
        self.langsmith_client = setup_langsmith(self.settings, self.logger)
        register_signal_handlers(self.shutdown_manager, self.logger)
        self.logger.info("Application setup complete.")

    def _calculate_metrics(self) -> Dict[str, Any]:
        """Calculate metrics based on the processing results."""
        metrics = {}
        if self.interrupted:
            self.logger.warning(
                f"Processing interrupted. Calculating metrics for {len(self.results)} completed URLs."
            )
            if self.results:
                try:
                    self.logger.info("Calculating metrics for partial results...")
                    metrics = calculate_metrics(
                        self.results, self.settings, self.logger, self.langsmith_client
                    )
                    self.logger.info("Partial metrics calculation complete.")
                except Exception as e:
                    self.logger.error(
                        f"Error calculating partial metrics: {e}", exc_info=True
                    )
            else:
                self.logger.warning("No results processed, skipping metrics.")
        elif not self.results:
            self.logger.warning("No results generated. Skipping metrics calculation.")
        else:
            try:
                self.logger.info("Calculating final metrics...")
                metrics = calculate_metrics(
                    self.results, self.settings, self.logger, self.langsmith_client
                )
                self.logger.info("Metrics calculation complete.")
            except Exception as e:
                self.logger.error(
                    f"Error calculating final metrics: {e}", exc_info=True
                )
        return metrics

    def _save_results(self, metrics: Dict[str, Any]) -> None:
        """Save the processing results and metrics."""
        if self.results:
            self.logger.info("Saving results...")
            try:
                save_results(self.results, metrics, self.settings, self.logger)
                self.logger.info("Results saving process complete.")
            except Exception as e:
                self.logger.error(f"Error saving results: {e}", exc_info=True)
        else:
            self.logger.warning("No results generated, nothing to save.")

    def _cleanup(self) -> None:
        """Perform resource cleanup."""
        self.logger.info("Starting resource cleanup.")
        cleanup_resources(self.logger, self.langsmith_client)
        self.logger.info("Resource cleanup finished.")

    def run(self) -> None:
        """Run the main profile extraction process."""
        self.logger.info("Application run method started.")
        self._setup_app()  # Setup logging, LangSmith, signals

        session_id = f"extraction-session-{uuid.uuid4()}"
        self.logger.info(f"Starting extraction session: {session_id}")

        self.start_time = time.time()

        try:
            # --- Load Data ---
            urls = load_urls(self.logger)

            # --- Processing ---
            self.results, self.interrupted = run_processing_loop(
                urls, self.shutdown_manager, langgraph_app, self.settings, self.logger
            )

            # --- Metrics Calculation ---
            metrics = self._calculate_metrics()

            # --- Save Results ---
            self._save_results(metrics)

            if self.interrupted:
                self.logger.info("Processing was interrupted by user or signal.")
            else:
                self.logger.info("Profile extraction process completed successfully.")

        except FileNotFoundError as e:
            self.logger.error(f"Fatal error: {e}. Cannot load URLs.")
            self.exit_code = 1
        except Exception as e:
            self.logger.error(f"Fatal error in main process: {str(e)}", exc_info=True)
            self.exit_code = 1
            # Cleanup will happen in finally

        finally:
            if self.start_time:
                end_time = time.time()
                total_duration = end_time - self.start_time
                self.logger.info(
                    f"Total execution time: {format_duration(total_duration)}"
                )

            self._cleanup()  # Call the cleanup method

            self.logger.info(f"Exiting with code {self.exit_code}.")
            # Use sys.exit with the determined code
            sys.exit(self.exit_code)


def main():
    """Instantiates and runs the ProfileExtractorApp."""
    # Instantiate the app here, so its logger might be available
    # even if run() fails early.
    app = ProfileExtractorApp()
    app.run()  # This method now contains the sys.exit call


if __name__ == "__main__":
    app_instance = None
    try:
        # Instantiate the app *outside* the main try block
        # So that the 'except' block can potentially use its logger/cleanup
        app_instance = ProfileExtractorApp()
        # Run the application logic which includes its own try/except/finally and sys.exit
        app_instance.run()
    except SystemExit as e:
        # Catch sys.exit to prevent double logging/cleanup if run() exits normally
        pass  # Exit silently as intended by app.run()
    except Exception as e:
        # Log critical error if app instantiation or run() failed catastrophically
        # before its own logging/cleanup could handle it.
        logger = getattr(
            app_instance, "logger", logging.getLogger(__name__)
        )  # Use app logger if available
        logger.critical(f"Unhandled top-level exception: {e}", exc_info=True)

        # Attempt last-ditch cleanup using the app instance if available
        if app_instance:
            try:
                app_instance._cleanup()
            except Exception as cleanup_err:
                logger.error(
                    f"Error during final cleanup attempt: {cleanup_err}", exc_info=True
                )
        else:
            # Fallback cleanup if app couldn't even be instantiated
            try:
                cleanup_resources(logging.getLogger(__name__), None)
            except Exception as cleanup_err:
                print(
                    f"CRITICAL: Error during fallback cleanup attempt: {cleanup_err}",
                    file=sys.stderr,
                )

        sys.exit(1)  # Exit with error code after attempting log/cleanup
