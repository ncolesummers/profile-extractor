import logging
import threading
import os
import concurrent.futures
from typing import (
    Union,
    Any,
)  # Import Union for older Python compatibility and Any for langsmith_client flexibility

# TODO: Import specific LangSmith client type hint if available and useful

# Global flag to prevent double cleanup (though should be called only once)
_cleanup_done = False
_cleanup_lock = threading.Lock()

# Get module logger
logger = logging.getLogger(__name__)


def cleanup_resources(
    logger: logging.Logger, langsmith_client: Union[Any, None] = None
):
    """Perform cleanup of resources, primarily focusing on the LangSmith client."""
    global _cleanup_done
    with _cleanup_lock:
        if _cleanup_done:
            logger.debug("Cleanup already performed, skipping.")
            return

        logger.info("Starting resource cleanup...")

        # --- Attempt to clean up LangSmith client resources --- #
        if langsmith_client:
            logger.info("Attempting LangSmith client cleanup...")
            try:
                # Attempt to flush pending data (standard method)
                flushed_ok = False
                if hasattr(langsmith_client, "flush") and callable(
                    langsmith_client.flush
                ):
                    logger.debug("Flushing LangSmith client (standard)...")
                    langsmith_client.flush()
                    logger.debug("LangSmith client flushed (standard).")
                    flushed_ok = True
                else:
                    logger.debug(
                        "LangSmith client does not have a standard 'flush' method."
                    )

                # Attempt to flush compressed traces as a secondary measure
                if hasattr(langsmith_client, "flush_compressed_traces") and callable(
                    langsmith_client.flush_compressed_traces
                ):
                    logger.debug("Flushing LangSmith client (compressed traces)...")
                    try:
                        langsmith_client.flush_compressed_traces()  # Default attempts=3
                        logger.debug("LangSmith client flushed (compressed traces).")
                        flushed_ok = True  # Mark as flushed if either method worked
                    except Exception as flush_comp_err:
                        logger.warning(
                            f"Error during flush_compressed_traces: {flush_comp_err}",
                            exc_info=True,
                        )
                else:
                    logger.debug(
                        "LangSmith client does not have 'flush_compressed_traces' method."
                    )

                if not flushed_ok:
                    logger.debug("No flush methods were successfully called.")

                # Attempt to explicitly clean up background threads/resources
                # Note: Langchain's background cleanup can be complex. This might need review.
                if hasattr(langsmith_client, "cleanup") and callable(
                    langsmith_client.cleanup
                ):
                    logger.debug("Cleaning up LangSmith client background resources...")
                    langsmith_client.cleanup()
                    logger.debug("LangSmith client background resources cleaned up.")
                elif (
                    hasattr(langsmith_client, "_runner")
                    and hasattr(langsmith_client._runner, "_stop_event")
                    and hasattr(langsmith_client._runner._stop_event, "set")
                ):
                    logger.debug("Attempting to signal LangSmith runner to stop...")
                    langsmith_client._runner._stop_event.set()
                else:
                    logger.debug(
                        "LangSmith client does not have a 'cleanup' method or known runner stop event."
                    )

                # Try to clean up LangSmith's internal thread pool (if it exists and follows common patterns)
                # This is speculative and depends on langsmith client implementation details.
                thread_pool_shutdown = False
                if (
                    hasattr(langsmith_client, "_thread_pool")
                    and hasattr(langsmith_client._thread_pool, "shutdown")
                    and callable(langsmith_client._thread_pool.shutdown)
                ):
                    logger.debug("Shutting down LangSmith internal thread pool...")
                    langsmith_client._thread_pool.shutdown(
                        wait=False
                    )  # Don't wait indefinitely
                    thread_pool_shutdown = True
                    logger.debug("LangSmith internal thread pool shutdown initiated.")
                elif (
                    hasattr(langsmith_client, "_client")
                    and hasattr(langsmith_client._client, "_thread_pool")
                    and hasattr(langsmith_client._client._thread_pool, "shutdown")
                    and callable(langsmith_client._client._thread_pool.shutdown)
                ):
                    # Handle cases where the pool might be on an inner client object
                    logger.debug("Shutting down nested LangSmith client thread pool...")
                    langsmith_client._client._thread_pool.shutdown(wait=False)
                    thread_pool_shutdown = True
                    logger.debug(
                        "Nested LangSmith client thread pool shutdown initiated."
                    )

                if not thread_pool_shutdown:
                    logger.debug(
                        "No identifiable LangSmith thread pool found to shut down."
                    )

                # Close any open sessions managed explicitly by the client
                if hasattr(langsmith_client, "close") and callable(
                    langsmith_client.close
                ):
                    logger.debug("Closing LangSmith client...")
                    langsmith_client.close()
                    logger.debug("LangSmith client closed.")
                elif (
                    hasattr(langsmith_client, "_session")
                    and hasattr(langsmith_client._session, "close")
                    and callable(langsmith_client._session.close)
                ):
                    logger.debug("Closing LangSmith session...")
                    langsmith_client._session.close()
                    logger.debug("LangSmith session closed.")
                else:
                    logger.debug(
                        "LangSmith client does not have a standard 'close' method or '_session.close()'."
                    )

                logger.info("LangSmith client cleanup attempts finished.")
            except Exception as e:
                logger.warning(
                    f"Error during LangSmith client cleanup: {e}", exc_info=True
                )
        else:
            logger.info("No LangSmith client provided, skipping its cleanup.")

        # --- Clean up LangGraph App --- #
        # Based on documentation review, CompiledGraph does not have an explicit
        # close/shutdown method. Cleanup relies on Python's garbage collection.
        logger.debug("Skipping explicit LangGraph cleanup (handled by GC).")

        # --- Commented out: Forced Daemonization and Exit Logic --- #
        # The goal is to remove the *need* for this by ensuring resources clean up properly.
        # logger.debug("Checking for non-daemon threads before declaring cleanup complete.")
        # non_daemon_threads = []
        # for thread in threading.enumerate():
        #     # Note: In Python 3.10+, isDaemon() is deprecated for daemon
        #     if thread is not threading.current_thread() and not thread.daemon:
        #         # Attempting to force daemon status is often a sign of an underlying issue
        #         # logger.warning(f"Setting potentially hanging thread {thread.name} to daemon status during final cleanup.")
        #         # try:
        #         #     thread.daemon = True
        #         # except RuntimeError as e:
        #         #     logger.warning(f"Could not set thread {thread.name} to daemon: {e}")
        #         non_daemon_threads.append(thread)
        #         logger.debug(f"Non-daemon thread still active: {thread.name}")
        #
        # if non_daemon_threads:
        #     logger.warning(
        #         f"Found {len(non_daemon_threads)} non-daemon threads still running after cleanup attempts:"
        #     )
        #     for thread in non_daemon_threads:
        #         logger.warning(f"  - Potentially hanging thread: {thread.name}")
        #     # The presence of these threads often requires os._exit(0) if they block sys.exit()
        #     # logger.warning("These threads might prevent graceful exit.")
        # else:
        #     logger.debug("No non-daemon threads detected after cleanup.")

        logger.info("Resource cleanup function finished.")
        _cleanup_done = True  # Mark cleanup as done inside the lock


# --- Potentially add specific cleanup functions for other resources if needed ---
# e.g., def cleanup_database_connections(): ...
