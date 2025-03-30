import json
import os
import time
import sys
import threading
import signal
import uuid
from typing import List, Dict, Any
import pandas as pd
from pathlib import Path
from tqdm import tqdm

# Force LangChain to use daemon threads for its handlers
os.environ["LANGCHAIN_HANDLER_THREAD_DAEMON"] = "true"

# Import our application components
from src.utils import setup_logging, format_duration
from src.graph import app  # This is our compiled LangGraph application
from src.config import OUTPUT_DIR, OUTPUT_FILENAME, LANGSMITH_API_KEY
from src.schemas import ProfileData

# Set up logging FIRST
logger = setup_logging()
logger.info("Application started.")

# Set up LangSmith tracing if API key is available
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT", "profile-extractor"
    )
    logger.info("LangSmith tracing enabled")

    # Import LangSmith client for aggregate metrics
    from langsmith import Client, traceable

    # Initialize client with auto_batch_tracing disabled
    langsmith_client = Client(api_key=LANGSMITH_API_KEY, auto_batch_tracing=False)
    logger.info("LangSmith Client initialized with auto_batch_tracing=False")

else:
    logger.info("LangSmith API key not found, tracing disabled")
    langsmith_client = None
    traceable = (
        lambda func, **kwargs: func
    )  # No-op traceable when LangSmith is disabled

# Initialize a cleanup flag to prevent duplicate cleanup
_cleanup_done = False
# Add a flag to signal graceful shutdown request
_shutdown_requested = False


def cleanup_resources():
    """Perform cleanup of all resources that might prevent clean exit."""
    global _cleanup_done

    if _cleanup_done:
        return

    logger.info("Performing cleanup of resources...")

    # Force set all non-daemon threads to daemon status
    for thread in threading.enumerate():
        if thread is not threading.current_thread() and not thread.daemon:
            try:
                thread.daemon = True
                logger.debug(f"Set thread {thread.name} to daemon status")
            except RuntimeError as e:
                logger.warning(f"Could not set thread {thread.name} to daemon: {e}")

    # Clean up LangSmith client resources if it exists
    if langsmith_client:
        try:
            # Attempt to flush pending data
            if hasattr(langsmith_client, "flush"):
                logger.debug("Flushing LangSmith client...")
                langsmith_client.flush()
                logger.debug("LangSmith client flushed.")

            # Attempt to explicitly clean up background threads/resources
            if hasattr(langsmith_client, "cleanup"):
                logger.debug("Cleaning up LangSmith client background resources...")
                langsmith_client.cleanup()
                logger.debug("LangSmith client background resources cleaned up.")

            # Close any open sessions managed explicitly by the client
            if hasattr(langsmith_client, "close"):
                langsmith_client.close()
                logger.debug("LangSmith client closed")
            elif hasattr(langsmith_client, "_session") and hasattr(
                langsmith_client._session, "close"
            ):
                langsmith_client._session.close()
                logger.debug("LangSmith session closed")

            # Try to clean up LangSmith's thread pool
            import concurrent.futures

            if hasattr(langsmith_client, "_thread_pool") and hasattr(
                langsmith_client._thread_pool, "shutdown"
            ):
                logger.debug("Shutting down LangSmith thread pool...")
                langsmith_client._thread_pool.shutdown(wait=False)
                logger.debug("LangSmith thread pool shut down.")

        except Exception as e:
            logger.warning(f"Error during LangSmith client cleanup: {e}")

    # Check for non-daemon threads remaining (after attempting to set daemon)
    non_daemon_threads = []
    for thread in threading.enumerate():
        if thread is not threading.current_thread() and not thread.daemon:
            non_daemon_threads.append(thread)
            logger.debug(f"Non-daemon thread found: {thread.name}")

    # If there are still non-daemon threads and we're in the main thread,
    # log a warning about them
    if non_daemon_threads and threading.current_thread() is threading.main_thread():
        logger.warning(
            f"Found {len(non_daemon_threads)} non-daemon threads still running after cleanup attempts"
        )
        # Log the names for debugging
        for thread in non_daemon_threads:
            logger.warning(f"  - Hanging thread: {thread.name}")

    _cleanup_done = True
    logger.info("Cleanup complete")


# Register signal handlers for graceful shutdown
def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum}, requesting graceful shutdown...")
    _shutdown_requested = True
    # Do not exit here; let the main loop handle it


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_urls() -> List[str]:
    """Load URLs from the data directory."""
    data_dir = Path("data")
    urls_file = data_dir / "uidaho_urls.json"

    if not urls_file.exists():
        raise FileNotFoundError(f"URLs file not found at {urls_file}")

    with open(urls_file, "r") as f:
        urls = json.load(f)

    logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
    return urls


@traceable(name="Process URL")
def process_url(url: str, thread_id: str = None) -> Dict[str, Any]:
    """Process a single URL through the graph workflow.

    Args:
        url: The URL to process
        thread_id: Optional thread ID for LangSmith tracing

    Returns:
        The final state after processing
    """
    logger.info(f"Processing URL: {url}")

    # Generate thread_id if not provided (for tracing)
    if thread_id is None:
        thread_id = f"profile-{uuid.uuid4()}"

    # Set up metadata for LangSmith tracing
    langsmith_extra = {"metadata": {"thread_id": thread_id, "url": url}}

    # Initialize state for this URL
    initial_state = {
        "url": url,
        "metrics": {},
        "error": None,
        "error_details": None,
        "html_content": None,
        "preprocessed_content": None,
        "extracted_data": None,
        "validation_result": None,
        "thread_id": thread_id,  # Include thread_id in state for nodes to access
    }

    try:
        # Process the URL through our graph
        # The traceable decorator will ensure this is traced as part of the thread
        # Force sequential execution within the graph to avoid hanging thread pools
        final_state = app.invoke(initial_state, config={"max_concurrency": 1})
        logger.info(f"Completed processing {url}")

        # Add thread info to metrics for reporting
        final_state["metrics"]["thread_id"] = thread_id

        return final_state
    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
        return {
            "url": url,
            "thread_id": thread_id,
            "error": str(e),
            "error_details": {"exception": type(e).__name__},
            "metrics": {"thread_id": thread_id},
        }


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics from the results."""
    metrics = {
        "total_urls": len(results),
        "successful_extractions": 0,
        "failed_extractions": 0,
        "total_cost": 0.0,
        "total_tokens": 0,
        "total_processing_time_ms": 0.0,
    }

    # Get token counts from LangSmith if available
    langsmith_token_count = 0
    if langsmith_client:
        try:
            # Calculate the timestamp for runs from the start of today
            import datetime

            start_time = datetime.datetime.combine(
                datetime.date.today(), datetime.time.min
            )

            # Get token counts from LangSmith traces
            runs = langsmith_client.list_runs(
                project_name=os.getenv("LANGSMITH_PROJECT", "profile-extractor"),
                start_time=start_time,
            )

            # Group runs by thread_id to analyze per-profile metrics
            thread_metrics = {}

            for run in runs:
                # Extract thread_id from metadata
                thread_id = None
                if hasattr(run, "metadata") and run.metadata:
                    thread_id = run.metadata.get("thread_id")

                # Initialize thread metrics if this is first time seeing thread
                if thread_id and thread_id not in thread_metrics:
                    thread_metrics[thread_id] = {"total_tokens": 0, "runs": []}

                # Add run to thread collection
                if thread_id:
                    thread_metrics[thread_id]["runs"].append(run.id)

                # Count tokens from usage metadata
                if hasattr(run, "usage_metadata") and run.usage_metadata:
                    if "total_tokens" in run.usage_metadata:
                        token_count = run.usage_metadata["total_tokens"]
                        langsmith_token_count += token_count
                        if thread_id:
                            thread_metrics[thread_id]["total_tokens"] += token_count
                    else:
                        # Some models split input/output
                        prompt_tokens = run.usage_metadata.get("prompt_tokens", 0)
                        completion_tokens = run.usage_metadata.get(
                            "completion_tokens", 0
                        )
                        thread_tokens = prompt_tokens + completion_tokens
                        langsmith_token_count += thread_tokens
                        if thread_id:
                            thread_metrics[thread_id]["total_tokens"] += thread_tokens

                # Also check feedback for token usage updates we manually added
                feedbacks = langsmith_client.list_feedback(
                    run_ids=[run.id], feedback_key="token_usage"
                )
                for feedback in feedbacks:
                    if hasattr(feedback, "value") and feedback.value:
                        if (
                            isinstance(feedback.value, dict)
                            and "total_tokens" in feedback.value
                        ):
                            token_count = feedback.value["total_tokens"]
                            langsmith_token_count += token_count
                            if thread_id:
                                thread_metrics[thread_id]["total_tokens"] += token_count

            # Log thread metrics summary if available
            if thread_metrics:
                logger.info(f"Found {len(thread_metrics)} profile threads in LangSmith")

                # Calculate average tokens per thread (profile)
                if thread_metrics:
                    thread_token_counts = [
                        tm["total_tokens"] for tm in thread_metrics.values()
                    ]
                    avg_tokens_per_thread = sum(thread_token_counts) / len(
                        thread_token_counts
                    )
                    logger.info(
                        f"Average tokens per profile thread: {avg_tokens_per_thread:.0f}"
                    )

            if langsmith_token_count > 0:
                print(f"Found {langsmith_token_count} tokens from LangSmith traces")
                metrics["total_tokens"] = langsmith_token_count
        except Exception as e:
            print(f"Error getting LangSmith token counts: {e}")
            # We'll fall back to manual counting below

    # Continue with regular metrics calculation from results
    for result in results:
        # Count successes/failures
        if result.get("error"):
            metrics["failed_extractions"] += 1
        elif result.get(
            "extracted_data"
        ):  # Count any extraction as successful, even if validation failed
            metrics["successful_extractions"] += 1

        # Sum up costs
        result_metrics = result.get("metrics", {})
        metrics["total_cost"] += result_metrics.get("cost_per_profile_extraction", 0.0)
        metrics["total_cost"] += result_metrics.get("cost_per_profile_validation", 0.0)

        # Sum token counts if we didn't get them from LangSmith
        if langsmith_token_count == 0:
            # Sum token counts from both extraction and validation
            extraction_input = result_metrics.get("extraction_input_tokens", 0)
            extraction_output = result_metrics.get("extraction_output_tokens", 0)
            validation_input = result_metrics.get("validation_input_tokens", 0)
            validation_output = result_metrics.get("validation_output_tokens", 0)

            # Add all token counts to the total
            metrics["total_tokens"] += (
                extraction_input
                + extraction_output
                + validation_input
                + validation_output
            )

        # Sum up processing time
        url_processing_time = 0.0
        for time_key in [
            "fetch_time_ms",
            "preprocess_time_ms",
            "extraction_time_ms",
            "validation_time_ms",
        ]:
            url_processing_time += result_metrics.get(time_key, 0.0)
        metrics["total_processing_time_ms"] += url_processing_time

    # Calculate averages
    if metrics["successful_extractions"] > 0:
        metrics["average_cost_per_profile"] = (
            metrics["total_cost"] / metrics["successful_extractions"]
        )
        metrics["average_tokens_per_profile"] = (
            metrics["total_tokens"] / metrics["successful_extractions"]
        )
        metrics["average_processing_time_s"] = (
            metrics["total_processing_time_ms"] / 1000
        ) / metrics["successful_extractions"]

    # If we still have zero tokens but have cost, estimate tokens based on cost
    if metrics["total_tokens"] == 0 and metrics["total_cost"] > 0:
        # Rough estimate based on Gemini pricing
        from src.nodes import GEMINI_FLASH_PRICING

        avg_price_per_token = (
            GEMINI_FLASH_PRICING["input"] + GEMINI_FLASH_PRICING["output"]
        ) / 2
        estimated_tokens = int(metrics["total_cost"] / avg_price_per_token)
        if estimated_tokens > 0:
            metrics["total_tokens"] = estimated_tokens
            metrics["tokens_source"] = "estimated_from_cost"
            print(f"Estimated {estimated_tokens} tokens based on cost")

    return metrics


def save_results(results: List[Dict[str, Any]], metrics: Dict[str, Any]):
    """Save extracted profiles to Excel and log metrics."""
    # Create output directory if it doesn't exist
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    # Extract successful profiles
    successful_profiles = [
        result["extracted_data"].model_dump()
        for result in results
        if result.get(
            "extracted_data"
        )  # Changed to count any extraction as successful, regardless of validation
    ]

    # Collect unsuccessful profiles for reporting
    unsuccessful_profiles = [
        {
            "url": result.get("url", "Unknown URL"),
            "error": result.get("error", "Unknown error"),
            "error_details": result.get("error_details", {}),
            "thread_id": result.get("thread_id", "Unknown"),
        }
        for result in results
        if not result.get("extracted_data")
    ]

    if successful_profiles:
        # Convert to DataFrame and save to Excel
        df = pd.DataFrame(successful_profiles)
        output_file = output_dir / OUTPUT_FILENAME
        df.to_excel(output_file, index=False)
        logger.info(f"Saved {len(successful_profiles)} profiles to {output_file}")

        # Save unsuccessful profiles if any
        if unsuccessful_profiles:
            error_df = pd.DataFrame(unsuccessful_profiles)
            error_file = output_dir / f"errors_{OUTPUT_FILENAME}"
            error_df.to_excel(error_file, index=False)
            logger.info(
                f"Saved {len(unsuccessful_profiles)} error reports to {error_file}"
            )

        # Update metrics with the actual count of successful profiles
        metrics["successful_extractions"] = len(successful_profiles)
        metrics["failed_extractions"] = metrics["total_urls"] - len(successful_profiles)
    else:
        logger.warning("No successful profiles to save!")
        if unsuccessful_profiles:
            error_df = pd.DataFrame(unsuccessful_profiles)
            error_file = output_dir / f"errors_{OUTPUT_FILENAME}"
            error_df.to_excel(error_file, index=False)
            logger.info(
                f"Saved {len(unsuccessful_profiles)} error reports to {error_file}"
            )

    # Log metrics
    logger.info("\nProcessing Metrics:")
    logger.info(f"Total URLs processed: {metrics['total_urls']}")
    logger.info(f"Successful extractions: {metrics['successful_extractions']}")
    logger.info(f"Failed extractions: {metrics['failed_extractions']}")
    logger.info(
        f"Success rate: {(metrics['successful_extractions'] / metrics['total_urls'] * 100):.2f}%"
    )
    logger.info(f"Total cost: ${metrics['total_cost']:.4f}")
    logger.info(f"Total tokens used: {metrics.get('total_tokens', 0)}")
    if metrics.get("average_tokens_per_profile"):
        logger.info(
            f"Average tokens per profile: {metrics['average_tokens_per_profile']:.0f}"
        )
    if metrics.get("average_cost_per_profile"):
        logger.info(
            f"Average cost per profile: ${metrics['average_cost_per_profile']:.4f}"
        )
    if metrics.get("average_processing_time_s"):
        avg_time_str = format_duration(metrics["average_processing_time_s"])
        logger.info(f"Average processing time: {avg_time_str}")


@traceable(name="Profile Extraction Process")
def main():
    """Main entry point for the profile extraction process."""
    start_time = time.time()  # Record start time

    # Create a session_id for this run to group all profiles in LangSmith
    session_id = f"extraction-session-{uuid.uuid4()}"
    logger.info(f"Starting extraction session: {session_id}")

    try:
        # Load URLs to process
        urls = load_urls()

        # Process each URL with a progress bar
        results = []
        interrupted = False  # Flag to track if loop was interrupted
        try:
            for url in tqdm(
                urls, desc="Processing URLs", unit="profile", position=0, leave=True
            ):
                # Check for shutdown signal before processing next URL
                if _shutdown_requested:
                    logger.warning("Shutdown requested, stopping URL processing...")
                    interrupted = True
                    break  # Exit the loop gracefully

                # Generate a unique thread_id for each profile's extraction process
                profile_thread_id = f"profile-{uuid.uuid4()}"

                # Process with thread tracking
                result = process_url(url, thread_id=profile_thread_id)
                results.append(result)
                # Optional: Add a small delay between processing URLs
                time.sleep(0.5)
        except KeyboardInterrupt:
            # This handles Ctrl+C *during* the tqdm loop or process_url call
            logger.warning(
                "Keyboard interrupt detected during processing loop. Stopping gracefully..."
            )
            interrupted = True

        # --- Saving Logic (runs after loop, even if interrupted) ---
        metrics = {}  # Initialize metrics dictionary
        if interrupted:
            logger.info(
                f"Processed {len(results)} out of {len(urls)} URLs before interruption."
            )

        # Calculate metrics in a separate thread only if not interrupted and we have results
        if not _shutdown_requested and results:
            metrics_thread = None
            thread_metrics_result = [{}]  # Use list/dict to allow thread modification

            def _calc_metrics_target(results_list, output_list):
                try:
                    calculated_metrics = calculate_metrics(results_list)
                    output_list[0] = calculated_metrics
                    logger.debug("Metrics calculation thread completed successfully.")
                except Exception as e:
                    logger.error(
                        f"Error within metrics calculation thread: {e}", exc_info=True
                    )
                    # Leave output_list[0] as default {}

            try:
                metrics_thread = threading.Thread(
                    target=_calc_metrics_target,
                    args=(results, thread_metrics_result),
                    daemon=True,  # Set as daemon so it doesn't block exit
                )
                logger.info("Starting metrics calculation thread...")
                metrics_thread.start()

                # Wait for the thread, but make the wait interruptible
                while metrics_thread.is_alive():
                    if _shutdown_requested:
                        logger.warning(
                            "Shutdown requested during metrics calculation. Proceeding without waiting for full metrics."
                        )
                        break  # Exit the waiting loop
                    metrics_thread.join(timeout=0.5)  # Check flag every 0.5s
                else:  # Loop finished because thread completed (no break)
                    if not _shutdown_requested:
                        metrics = thread_metrics_result[0]  # Get results from thread
                        logger.info("Metrics calculation thread finished.")
                    else:
                        # Shutdown requested near the end, use potentially incomplete results
                        metrics = thread_metrics_result[0]
                        logger.warning(
                            "Metrics thread finished, but shutdown was requested during wait. Using potentially incomplete metrics."
                        )

            except Exception as e:
                logger.error(f"Error managing metrics thread: {e}", exc_info=True)
                if metrics_thread and metrics_thread.is_alive():
                    logger.warning(
                        "Metrics thread might still be running in background after error."
                    )

        elif _shutdown_requested:
            logger.warning(
                "Skipping metrics calculation due to pending shutdown request."
            )

        # Save results if any were collected
        if results:
            logger.info("Saving results...")
            save_results(results, metrics)  # Pass calculated or empty metrics
            logger.info("Profile extraction process results saved.")
            if interrupted:
                logger.info(
                    f"Note: Processing was interrupted. Results for {len(results)} URLs were saved."
                )
        elif interrupted:
            logger.warning(
                "Processing interrupted before any results could be generated. No data to save."
            )
        else:
            logger.warning(
                "No results were generated (e.g., all URLs failed). No data to save."
            )

    except Exception as e:
        # Catch other potential errors during loading or setup
        logger.error(f"Fatal error in main process: {str(e)}", exc_info=True)
        # Ensure cleanup happens even on unexpected errors before the finally block might
        cleanup_resources()
        sys.exit(1)  # Exit with error code

    finally:
        end_time = time.time()
        total_duration = end_time - start_time
        logger.info(f"Total execution time: {format_duration(total_duration)}")

        # --- Explicitly clean up LangGraph app if possible ---
        try:
            if hasattr(app, "close") and callable(app.close):
                logger.info("Closing LangGraph application resources...")
                app.close()
                logger.info("LangGraph application resources closed.")
            # Add checks for other potential cleanup methods if needed (e.g., shutdown)
            elif hasattr(app, "shutdown") and callable(app.shutdown):
                logger.info("Shutting down LangGraph application resources...")
                app.shutdown()
                logger.info("LangGraph application resources shut down.")
        except Exception as e:
            logger.warning(f"Error during LangGraph app cleanup: {e}")
        # ------------------------------------------------------

        # Monitor and force daemonization of non-daemon threads
        for thread in threading.enumerate():
            if not thread.daemon and thread is not threading.current_thread():
                logger.warning(f"Setting non-daemon thread to daemon: {thread.name}")
                thread.daemon = True

        # Clean up other resources (LangSmith, requests, etc.)
        cleanup_resources()

        # Log running threads before attempting to exit
        if threading.current_thread() is threading.main_thread():
            logger.info("Threads still running before final exit attempt:")
            for thread in threading.enumerate():
                logger.info(
                    f"  - Name: {thread.name}, Daemon: {thread.daemon}, Alive: {thread.is_alive()}"
                )

            logger.info("All tasks completed. Attempting graceful exit.")
            # Give threads a moment to potentially finish cleanup
            time.sleep(1.0)

            # Check one last time for non-daemon threads
            remaining_non_daemon = [
                t
                for t in threading.enumerate()
                if t is not threading.current_thread() and not t.daemon
            ]

            if remaining_non_daemon:
                logger.warning(
                    f"Force exiting with {len(remaining_non_daemon)} non-daemon threads still running: {[t.name for t in remaining_non_daemon]}"
                )
                os._exit(0)  # Force exit only as a last resort
            else:
                logger.info("Exiting gracefully via sys.exit(0).")
                sys.exit(0)  # Standard graceful exit


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        cleanup_resources()
        sys.exit(1)
