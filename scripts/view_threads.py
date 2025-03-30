#!/usr/bin/env python
"""
LangSmith Thread Viewer Utility

This script connects to LangSmith API and retrieves thread information
for the profile extraction process. It allows viewing extraction threads,
their runs, and relevant metrics.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
from tabulate import tabulate

# Add the project root to the path so we can import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import project config
from src.config import LANGSMITH_API_KEY, LANGSMITH_PROJECT

# Set up LangSmith client
if not LANGSMITH_API_KEY:
    print("Error: LANGSMITH_API_KEY not set in environment or config")
    sys.exit(1)

from langsmith import Client

langsmith_client = Client(api_key=LANGSMITH_API_KEY)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="View LangSmith thread information")
    parser.add_argument(
        "--project",
        default=LANGSMITH_PROJECT,
        help=f"LangSmith project name (default: {LANGSMITH_PROJECT})",
    )
    parser.add_argument(
        "--days", type=int, default=1, help="Number of days to look back (default: 1)"
    )
    parser.add_argument(
        "--thread-id",
        help="Specific thread ID to analyze",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "excel"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (for csv/excel formats)",
    )

    return parser.parse_args()


def get_thread_runs(
    project_name: str, days_back: int = 1, thread_id: Optional[str] = None
) -> Dict[str, List[Any]]:
    """Retrieve runs organized by thread from LangSmith."""
    # Calculate start time based on days_back
    start_time = datetime.now() - timedelta(days=days_back)

    # Build the filter
    if thread_id:
        filter_string = (
            f'and(in(metadata_key, ["thread_id"]), eq(metadata_value, "{thread_id}"))'
        )
    else:
        filter_string = 'in(metadata_key, ["thread_id"])'

    # Get runs that have thread_id in metadata
    runs = list(
        langsmith_client.list_runs(
            project_name=project_name, start_time=start_time, filter=filter_string
        )
    )

    # Group runs by thread_id
    threads = {}
    for run in runs:
        if hasattr(run, "metadata") and run.metadata and "thread_id" in run.metadata:
            thread_id = run.metadata["thread_id"]
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(run)

    # Sort runs within each thread by start_time
    for thread_id in threads:
        threads[thread_id] = sorted(threads[thread_id], key=lambda run: run.start_time)

    return threads


def calculate_thread_metrics(threads: Dict[str, List[Any]]) -> pd.DataFrame:
    """Calculate metrics for each thread."""
    thread_metrics = []

    for thread_id, runs in threads.items():
        # Initialize metrics for this thread
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0
        num_llm_calls = 0
        url = None
        errors = []

        # Calculate earliest start and latest end time
        start_times = [run.start_time for run in runs if hasattr(run, "start_time")]
        end_times = [run.end_time for run in runs if hasattr(run, "end_time")]

        earliest_start = min(start_times) if start_times else None
        latest_end = max(end_times) if end_times else None

        # Calculate duration
        duration_seconds = None
        if earliest_start and latest_end:
            duration_seconds = (latest_end - earliest_start).total_seconds()

        # Process each run
        for run in runs:
            # Get URL if available
            if hasattr(run, "metadata") and run.metadata and "url" in run.metadata:
                url = run.metadata["url"]

            # Count tokens and cost from usage_metadata
            if hasattr(run, "usage_metadata") and run.usage_metadata:
                if "total_tokens" in run.usage_metadata:
                    total_tokens += run.usage_metadata["total_tokens"]
                else:
                    # Some models split input/output
                    prompt_tokens = run.usage_metadata.get("prompt_tokens", 0)
                    completion_tokens = run.usage_metadata.get("completion_tokens", 0)
                    total_prompt_tokens += prompt_tokens
                    total_completion_tokens += completion_tokens
                    total_tokens += prompt_tokens + completion_tokens

            # Count LLM calls
            if hasattr(run, "run_type") and run.run_type == "llm":
                num_llm_calls += 1

            # Check for errors
            if hasattr(run, "error") and run.error:
                errors.append(run.error)

        # Create a row for this thread
        thread_data = {
            "thread_id": thread_id,
            "url": url,
            "num_runs": len(runs),
            "num_llm_calls": num_llm_calls,
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "has_errors": len(errors) > 0,
            "start_time": earliest_start,
            "end_time": latest_end,
            "duration_seconds": duration_seconds,
        }

        thread_metrics.append(thread_data)

    # Convert to DataFrame
    df = pd.DataFrame(thread_metrics)

    # Add formatted duration column
    if "duration_seconds" in df.columns:
        df["duration"] = df["duration_seconds"].apply(
            lambda s: f"{int(s // 60)}m {int(s % 60)}s" if pd.notnull(s) else ""
        )

    return df


def main():
    """Main entry point."""
    args = parse_args()

    print(f"Retrieving thread information from project: {args.project}")
    print(f"Looking back {args.days} days")

    # Get thread runs
    threads = get_thread_runs(args.project, args.days, args.thread_id)

    if not threads:
        print("No threads found with the specified criteria.")
        return

    print(f"Found {len(threads)} threads with LLM calls")

    # Calculate metrics
    thread_df = calculate_thread_metrics(threads)

    # Display results based on format
    if args.format == "table":
        print("\nThread Metrics:")
        display_cols = [
            "thread_id",
            "url",
            "num_runs",
            "num_llm_calls",
            "total_tokens",
            "duration",
            "has_errors",
        ]
        print(tabulate(thread_df[display_cols], headers="keys", tablefmt="grid"))

    elif args.format == "csv":
        output_path = args.output or "langsmith_threads.csv"
        thread_df.to_csv(output_path, index=False)
        print(f"Thread metrics saved to {output_path}")

    elif args.format == "excel":
        output_path = args.output or "langsmith_threads.xlsx"
        thread_df.to_excel(output_path, index=False)
        print(f"Thread metrics saved to {output_path}")


if __name__ == "__main__":
    main()
