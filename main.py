import json
import os
import time
from typing import List, Dict, Any
import pandas as pd
from pathlib import Path

# Import our application components
from src.utils import setup_logging
from src.graph import app  # This is our compiled LangGraph application
from src.config import OUTPUT_DIR, OUTPUT_FILENAME
from src.schemas import ProfileData

# Set up logging
logger = setup_logging()
logger.info("Application started.")


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


def process_url(url: str) -> Dict[str, Any]:
    """Process a single URL through the graph workflow."""
    logger.info(f"Processing URL: {url}")

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
    }

    try:
        # Process the URL through our graph
        final_state = app.invoke(initial_state)
        logger.info(f"Completed processing {url}")
        return final_state
    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
        return {
            "url": url,
            "error": str(e),
            "error_details": {"exception": type(e).__name__},
            "metrics": {},
        }


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics from the results."""
    metrics = {
        "total_urls": len(results),
        "successful_extractions": 0,
        "failed_extractions": 0,
        "total_cost": 0.0,
        "total_tokens": 0,
        "total_processing_time": 0.0,
    }

    for result in results:
        # Count successes/failures
        if result.get("error"):
            metrics["failed_extractions"] += 1
        elif result.get("extracted_data"):
            metrics["successful_extractions"] += 1

        # Sum up costs and tokens
        result_metrics = result.get("metrics", {})
        metrics["total_cost"] += result_metrics.get("cost_per_profile_extraction", 0.0)
        metrics["total_cost"] += result_metrics.get("cost_per_profile_validation", 0.0)

        # Sum up processing time
        for time_key in [
            "fetch_time_ms",
            "preprocess_time_ms",
            "extraction_time_ms",
            "validation_time_ms",
        ]:
            metrics["total_processing_time"] += result_metrics.get(time_key, 0.0)

    # Calculate averages
    if metrics["successful_extractions"] > 0:
        metrics["average_cost_per_profile"] = (
            metrics["total_cost"] / metrics["successful_extractions"]
        )
        metrics["average_processing_time_ms"] = (
            metrics["total_processing_time"] / metrics["successful_extractions"]
        )

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
        if result.get("extracted_data")
    ]

    if successful_profiles:
        # Convert to DataFrame and save to Excel
        df = pd.DataFrame(successful_profiles)
        output_file = output_dir / OUTPUT_FILENAME
        df.to_excel(output_file, index=False)
        logger.info(f"Saved {len(successful_profiles)} profiles to {output_file}")

    # Log metrics
    logger.info("\nProcessing Metrics:")
    logger.info(f"Total URLs processed: {metrics['total_urls']}")
    logger.info(f"Successful extractions: {metrics['successful_extractions']}")
    logger.info(f"Failed extractions: {metrics['failed_extractions']}")
    logger.info(
        f"Success rate: {(metrics['successful_extractions'] / metrics['total_urls'] * 100):.2f}%"
    )
    logger.info(f"Total cost: ${metrics['total_cost']:.4f}")
    if metrics.get("average_cost_per_profile"):
        logger.info(
            f"Average cost per profile: ${metrics['average_cost_per_profile']:.4f}"
        )
    if metrics.get("average_processing_time_ms"):
        logger.info(
            f"Average processing time: {metrics['average_processing_time_ms']:.2f} ms"
        )


def main():
    """Main entry point for the profile extraction process."""
    try:
        # Load URLs to process
        urls = load_urls()

        # Process each URL
        results = []
        for url in urls:
            result = process_url(url)
            results.append(result)
            # Optional: Add a small delay between processing URLs
            time.sleep(0.5)

        # Calculate and save results
        metrics = calculate_metrics(results)
        save_results(results, metrics)

        logger.info("Profile extraction process completed successfully")

    except Exception as e:
        logger.error(f"Fatal error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main()
