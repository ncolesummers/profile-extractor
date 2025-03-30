import logging
from typing import List, Dict, Any, Union
import pandas as pd
from pathlib import Path
import datetime  # Needed for LangSmith date filtering

# Import necessary components from other src modules
from .config import Settings  # Assuming Settings is the class in config.py
from .utils import format_duration
from .nodes import GEMINI_FLASH_PRICING  # For token cost estimation fallback

# Module-level logger (will be overwritten by passed logger in functions)
logger = logging.getLogger(__name__)

# Note: langsmith_client is passed as an argument where needed


def calculate_metrics(
    results: List[Dict[str, Any]],
    settings: Settings,
    logger: logging.Logger,
    langsmith_client: Union[Any, None] = None,
) -> Dict[str, Any]:
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
    if langsmith_client and settings.LANGSMITH_PROJECT:
        try:
            # Calculate the timestamp for runs from the start of today
            start_time_dt = datetime.datetime.combine(
                datetime.date.today(), datetime.time.min
            )

            logger.debug(
                f"Fetching LangSmith runs for project '{settings.LANGSMITH_PROJECT}' since {start_time_dt}..."
            )
            # Get token counts from LangSmith traces
            runs_iterator = langsmith_client.list_runs(
                project_name=settings.LANGSMITH_PROJECT,
                start_time=start_time_dt,  # Use datetime object
                execution_order="1",  # Ensure descending order to get recent runs first potentially? Check API docs. Default might be fine.
                run_type="llm",  # Filter for LLM runs only if possible/desired
            )

            # Group runs by thread_id to analyze per-profile metrics
            thread_metrics = {}
            processed_run_ids = (
                set()
            )  # Keep track of runs processed to avoid double counting if list_runs yields duplicates somehow

            # Convert iterator to list to allow multiple passes if needed, handle potential API limits implicitly?
            # Be mindful of memory if there are huge numbers of runs.
            # runs = list(runs_iterator) # Alternative: process iterator directly

            logger.info(f"Processing LangSmith runs for token counts...")
            run_count = 0
            for run in runs_iterator:
                run_count += 1
                if run.id in processed_run_ids:
                    continue
                processed_run_ids.add(run.id)

                # Extract thread_id from metadata
                thread_id = None
                if run.extra and run.extra.get("metadata"):
                    metadata = run.extra["metadata"]
                    thread_id = metadata.get("thread_id")

                # Initialize thread metrics if this is first time seeing thread
                if thread_id and thread_id not in thread_metrics:
                    thread_metrics[thread_id] = {"total_tokens": 0, "runs": []}

                # Add run to thread collection
                if thread_id:
                    thread_metrics[thread_id]["runs"].append(run.id)

                # Count tokens from usage metadata (newer field)
                run_tokens = 0
                if hasattr(run, "total_tokens") and run.total_tokens is not None:
                    run_tokens = run.total_tokens
                elif hasattr(run, "prompt_tokens") and hasattr(
                    run, "completion_tokens"
                ):
                    run_tokens = (run.prompt_tokens or 0) + (run.completion_tokens or 0)
                # Fallback to older usage_metadata if necessary (adjust based on actual Run object structure)
                elif hasattr(run, "usage_metadata") and run.usage_metadata:
                    usage_meta = run.usage_metadata
                    if "total_tokens" in usage_meta:
                        run_tokens = usage_meta["total_tokens"]
                    else:
                        prompt_tokens = usage_meta.get("prompt_tokens", 0)
                        completion_tokens = usage_meta.get("completion_tokens", 0)
                        run_tokens = prompt_tokens + completion_tokens

                langsmith_token_count += run_tokens
                if thread_id:
                    thread_metrics[thread_id]["total_tokens"] += run_tokens

                # Also check feedback for token usage updates we manually added (if still relevant)
                # Consider if this feedback loop is still used or needed.
                # feedbacks = langsmith_client.list_feedback(
                #     run_ids=[run.id], feedback_key="token_usage"
                # )
                # for feedback in feedbacks:
                #     # ... (rest of feedback processing logic if needed) ...
                #     pass

            logger.info(f"Processed {run_count} LangSmith runs.")

            # Log thread metrics summary if available
            if thread_metrics:
                logger.info(
                    f"Found {len(thread_metrics)} profile threads in LangSmith runs."
                )
                thread_token_counts = [
                    tm["total_tokens"] for tm in thread_metrics.values()
                ]
                if thread_token_counts:  # Avoid division by zero
                    avg_tokens_per_thread = sum(thread_token_counts) / len(
                        thread_token_counts
                    )
                    logger.info(
                        f"Average tokens per profile thread: {avg_tokens_per_thread:.0f}"
                    )
                else:
                    logger.info("No tokens recorded in thread metrics.")

            if langsmith_token_count > 0:
                logger.info(
                    f"Total tokens calculated from LangSmith runs: {langsmith_token_count}"
                )
                metrics["total_tokens"] = langsmith_token_count
                metrics["tokens_source"] = "langsmith_runs_total"
            else:
                logger.info("No tokens found in LangSmith runs.")

        except Exception as e:
            logger.warning(
                f"Could not retrieve or process LangSmith token counts: {e}",
                exc_info=True,
            )
            # We'll fall back to manual counting below if langsmith_token_count is 0

    # Continue with regular metrics calculation from results list
    successful_count_from_results = 0
    for result in results:
        # Count successes/failures based on presence of 'extracted_data'
        if result.get("extracted_data"):
            successful_count_from_results += 1
        # Note: We don't explicitly count failures here, calculate at the end

        # Sum up costs from individual result metrics
        result_metrics = result.get("metrics", {})
        metrics["total_cost"] += result_metrics.get("cost_per_profile_extraction", 0.0)
        metrics["total_cost"] += result_metrics.get("cost_per_profile_validation", 0.0)

        # Sum token counts from result metrics ONLY if we failed to get them from LangSmith
        if langsmith_token_count == 0:
            metrics["tokens_source"] = "estimated_from_results"  # Mark source
            extraction_input = result_metrics.get("extraction_input_tokens", 0)
            extraction_output = result_metrics.get("extraction_output_tokens", 0)
            validation_input = result_metrics.get("validation_input_tokens", 0)
            validation_output = result_metrics.get("validation_output_tokens", 0)
            metrics["total_tokens"] += (
                extraction_input
                + extraction_output
                + validation_input
                + validation_output
            )

        # Sum up processing time from result metrics
        url_processing_time = 0.0
        for time_key in [
            "fetch_time_ms",
            "preprocess_time_ms",
            "extraction_time_ms",
            "validation_time_ms",
        ]:
            url_processing_time += result_metrics.get(time_key, 0.0)
        metrics["total_processing_time_ms"] += url_processing_time

    # Finalize success/failure counts
    metrics["successful_extractions"] = successful_count_from_results
    metrics["failed_extractions"] = (
        metrics["total_urls"] - successful_count_from_results
    )

    # Calculate averages, avoiding division by zero
    actual_success_count = metrics[
        "successful_extractions"
    ]  # Use the count based on 'extracted_data'
    if actual_success_count > 0:
        metrics["average_cost_per_successful_profile"] = (
            metrics["total_cost"] / actual_success_count
        )
        metrics["average_tokens_per_successful_profile"] = (
            metrics["total_tokens"] / actual_success_count
        )
        metrics["average_processing_time_ms_per_successful_profile"] = (
            metrics["total_processing_time_ms"] / actual_success_count
        )
    else:
        metrics["average_cost_per_successful_profile"] = 0.0
        metrics["average_tokens_per_successful_profile"] = 0.0
        metrics["average_processing_time_ms_per_successful_profile"] = 0.0

    # If we still have zero tokens but have cost (and used fallback method), estimate tokens based on cost
    if (
        metrics.get("tokens_source") == "estimated_from_results"
        and metrics["total_tokens"] == 0
        and metrics["total_cost"] > 0
    ):
        # Rough estimate based on Gemini pricing
        avg_price_per_token = (
            GEMINI_FLASH_PRICING["input"] + GEMINI_FLASH_PRICING["output"]
        ) / 2
        if avg_price_per_token > 0:  # Avoid division by zero
            estimated_tokens = int(metrics["total_cost"] / avg_price_per_token)
            if estimated_tokens > 0:
                metrics["total_tokens"] = estimated_tokens
                metrics["tokens_source"] = "estimated_from_cost_fallback"
                logger.info(
                    f"Estimated {estimated_tokens} tokens based on cost (fallback)."
                )
        else:
            logger.warning(
                "Cannot estimate tokens from cost: Average price per token is zero."
            )

    return metrics


def save_results(
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    settings: Settings,
    logger: logging.Logger,
):
    """Save extracted profiles to Excel and log metrics."""
    if not settings.OUTPUT_DIR or not settings.OUTPUT_FILENAME:
        logger.error(
            "Output directory or filename not configured in settings. Cannot save results."
        )
        return

    # Create output directory if it doesn't exist
    output_dir = Path(settings.OUTPUT_DIR)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)  # Use parents=True
    except OSError as e:
        logger.error(
            f"Failed to create output directory {output_dir}: {e}", exc_info=True
        )
        return

    # Extract successful profiles (those with extracted_data)
    successful_profiles_data = []
    for result in results:
        if result.get("extracted_data"):
            # Assuming extracted_data is a Pydantic model, use .model_dump()
            if hasattr(result["extracted_data"], "model_dump"):
                successful_profiles_data.append(result["extracted_data"].model_dump())
            else:
                # Fallback if it's not a Pydantic model (e.g., a dict)
                successful_profiles_data.append(result["extracted_data"])

    # Collect unsuccessful profiles for reporting
    unsuccessful_profiles = [
        {
            "url": result.get("url", "Unknown URL"),
            "error": result.get("error", "Unknown error"),
            "error_details": str(
                result.get("error_details", {})
            ),  # Ensure details are stringified
            "thread_id": result.get("thread_id", "Unknown"),
        }
        for result in results
        if not result.get(
            "extracted_data"
        )  # Changed to 'not extracted_data' for clarity
    ]

    # --- Saving Successful Profiles ---
    if successful_profiles_data:
        try:
            df = pd.DataFrame(successful_profiles_data)
            output_file = output_dir / settings.OUTPUT_FILENAME
            df.to_excel(
                output_file, index=False, engine="openpyxl"
            )  # Specify engine if needed
            logger.info(
                f"Saved {len(successful_profiles_data)} profiles to {output_file}"
            )
        except ImportError:
            logger.error(
                "`pandas` or `openpyxl` missing. Cannot save profiles to Excel. Install with `uv pip install pandas openpyxl`"
            )
        except Exception as e:
            logger.error(
                f"Failed to save successful profiles to {output_file}: {e}",
                exc_info=True,
            )
    else:
        logger.info("No successful profiles with data found to save.")

    # --- Saving Unsuccessful/Error Profiles ---
    if unsuccessful_profiles:
        try:
            error_df = pd.DataFrame(unsuccessful_profiles)
            # Ensure filename is different from success file
            base, ext = (
                settings.OUTPUT_FILENAME.rsplit(".", 1)
                if "." in settings.OUTPUT_FILENAME
                else (settings.OUTPUT_FILENAME, "")
            )
            error_filename = (
                f"{base}_errors.{ext}"
                if ext
                else f"{settings.OUTPUT_FILENAME}_errors.xlsx"
            )
            error_file = output_dir / error_filename
            error_df.to_excel(error_file, index=False, engine="openpyxl")
            logger.info(
                f"Saved {len(unsuccessful_profiles)} error reports to {error_file}"
            )
        except ImportError:
            logger.error(
                "`pandas` or `openpyxl` missing. Cannot save error reports to Excel. Install with `uv pip install pandas openpyxl`"
            )
        except Exception as e:
            logger.error(
                f"Failed to save error reports to {error_file}: {e}", exc_info=True
            )
    else:
        logger.info("No unsuccessful profiles/errors found to save.")

    # --- Logging Metrics ---
    logger.info("\n--- Processing Metrics Summary ---")
    total_urls = metrics.get("total_urls", 0)
    successful_extractions = metrics.get("successful_extractions", 0)
    failed_extractions = metrics.get("failed_extractions", 0)

    logger.info(f"Total URLs processed: {total_urls}")
    logger.info(f"Successful extractions: {successful_extractions}")
    logger.info(f"Failed extractions: {failed_extractions}")

    if total_urls > 0:
        success_rate = (
            (successful_extractions / total_urls * 100) if total_urls > 0 else 0
        )
        logger.info(f"Success rate: {success_rate:.2f}%")
    else:
        logger.info("Success rate: N/A (no URLs processed)")

    logger.info(f"Total estimated cost: ${metrics.get('total_cost', 0.0):.4f}")
    logger.info(
        f"Total tokens used: {metrics.get('total_tokens', 0)} (Source: {metrics.get('tokens_source', 'N/A')})"
    )

    if successful_extractions > 0:
        avg_cost = metrics.get("average_cost_per_successful_profile", 0.0)
        avg_tokens = metrics.get("average_tokens_per_successful_profile", 0.0)
        avg_time_ms = metrics.get(
            "average_processing_time_ms_per_successful_profile", 0.0
        )
        avg_time_s = avg_time_ms / 1000
        avg_time_str = format_duration(avg_time_s) if avg_time_s > 0 else "N/A"

        logger.info(f"Average cost per successful profile: ${avg_cost:.4f}")
        logger.info(f"Average tokens per successful profile: {avg_tokens:.0f}")
        logger.info(
            f"Average processing time per successful profile: {avg_time_str} ({avg_time_ms:.2f} ms)"
        )
    else:
        logger.info(
            "Average metrics per successful profile: N/A (no successful extractions)"
        )

    total_proc_time_s = metrics.get("total_processing_time_ms", 0.0) / 1000
    total_proc_time_str = (
        format_duration(total_proc_time_s) if total_proc_time_s > 0 else "0s"
    )
    logger.info(f"Total processing time (sum of steps): {total_proc_time_str}")
    logger.info("--- End Metrics Summary ---")
