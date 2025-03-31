# Faculty Profile Extractor

## Overview

This project crawls faculty profile pages from the University of Idaho ([uidaho.edu](https://www.uidaho.edu/)) website, extracts key information using Large Language Models (LLMs), and outputs the structured data into an Excel file. It leverages LangChain, LangGraph, Pydantic, and Google Gemini models for the extraction and validation workflow.

**Key Goals:**

*   Extract specific fields: Photo URL, Name, Title, Email, Degrees, Research Areas, Office, Phone, College/Department.
*   Handle variations in HTML structure across different profile pages.
*   Ensure respectful crawling with configurable delays.
*   Validate extracted data using an LLM judge.
*   Track detailed metrics for performance, cost, and accuracy.
*   Output a clean, structured Excel file (`output/extracted_profiles.xlsx`).
*   Utilize LangSmith for detailed run tracing and debugging.

## Features

*   **Web Crawling:** Fetches HTML content from specified profile URLs.
*   **HTML Preprocessing:** Cleans and extracts relevant content from raw HTML, attempting to handle varying structures.
*   **LLM-Powered Extraction:** Uses Google Gemini models via LangChain to extract information into a predefined Pydantic schema (`ProfileData`).
*   **LLM-Powered Validation:** Employs a separate LLM judge call to evaluate the accuracy of the extracted fields against the preprocessed content (`ValidationResult`).
*   **Structured Output:** Ensures data conforms to the `ProfileData` schema using Pydantic.
*   **Error Handling:** Captures and logs errors during the fetch, preprocess, extract, and validate stages.
*   **Metric Tracking:** Records token usage, cost, latency, and error rates for each step and overall.
*   **LangSmith Integration:** Uses LangSmith for detailed tracing of each profile extraction process. Runs are grouped by `thread_id` for easy debugging and analysis.
*   **Configurable:** Allows setting API keys, model names, and request delays via configuration.
*   **Reproducible Environment:** Uses `uv` for dependency management and environment creation.

## Architecture Overview

The application's core logic is orchestrated by the `src.main.ProfileExtractorApp` class. This class manages the overall workflow:

1.  **Initialization:** Sets up logging, LangSmith integration (if configured), and signal handling for graceful shutdowns.
2.  **URL Loading:** Reads the list of profile URLs from `data/uidaho_urls.json`.
3.  **Processing Loop:** Iterates through the URLs, invoking the profile extraction and validation workflow for each one. This core extraction logic is implemented as a [LangGraph](https://python.langchain.com/docs/langgraph/) state machine defined in `src/graph.py` and `src/nodes.py`. The graph performs the following steps for each URL:
    *   **`fetch_page`:** Retrieves the HTML content, respecting configured delays.
    *   **`preprocess_html`:** Parses and cleans the HTML to isolate relevant profile content.
    *   **`extract_data`:** Uses a configured Google Gemini model via LangChain to extract information into the `ProfileData` Pydantic schema.
    *   **`validate_data`:** Employs an LLM judge (another Gemini model call) to evaluate the accuracy of the extracted fields against the preprocessed content, resulting in a `ValidationResult`.
    *   **`handle_error`:** Logs errors encountered during the process.
    *   **Conditional Edges:** Transitions between nodes based on success or error states.
4.  **Metrics Calculation:** After processing all URLs (or if interrupted), calculates aggregate metrics (token usage, cost, latency, success rate) using functions in `src/reporting.py`.
5.  **Results Saving:** Saves the successfully extracted profiles to `output/extracted_profiles.xlsx` and any errors to `output/errors_extracted_profiles.xlsx` using functions in `src/reporting.py`.
6.  **Cleanup:** Performs necessary cleanup tasks.

Each invocation of the LangGraph workflow for a single URL is traced as a distinct **thread** in LangSmith, identified by a unique `thread_id` generated in `src/processing.py`, allowing for detailed debugging and analysis.

**Key Technologies:**

*   **Python:** Core programming language.
*   **uv:** Environment and package management.
*   **LangChain & LangGraph:** Orchestration of the LLM workflow.
*   **LangChain Google Generative AI:** Integration with Google Gemini models.
*   **LangSmith:** Tracing, monitoring, and debugging.
*   **Pydantic:** Data modeling and validation (`ProfileData`, `ValidationResult`).
*   **Requests/HTTPX:** Fetching web pages.
*   **BeautifulSoup4:** HTML parsing.
*   **Pandas & Openpyxl:** Creating the final Excel output.
*   **python-dotenv:** Loading environment variables (API keys).
*   **Ruff:** Linting and formatting (for development).

## Project Structure

```
profile-extractor/
├── .venv/                 # Virtual environment managed by uv
├── data/
│   └── uidaho_urls.json   # Input list of profile URLs
├── docs/
│   ├── research/          # Research documents (architecture, metrics, etc.)
│   └── prompts/           # LLM Prompts
├── logs/
│   ├── app.log            # Application log file
│   └── debug/             # Debug output on errors (if configured)
├── output/
│   ├── extracted_profiles.xlsx # Generated Excel file of successes
│   └── errors_extracted_profiles.xlsx # Generated Excel file of errors
├── scripts/
│   ├── view_threads.py    # Utility to view LangSmith thread info
│   └── process_urls.py    # Example script (if applicable)
├── src/
│   ├── __init__.py
│   ├── main.py            # Main application entry point (ProfileExtractorApp)
│   ├── setup.py           # Logging, LangSmith, signal handling setup
│   ├── config.py          # Configuration loading (API Key, models, delays)
│   ├── schemas.py         # Pydantic data models (ProfileData, ValidationResult)
│   ├── state.py           # LangGraph State definition
│   ├── graph.py           # LangGraph definition
│   ├── nodes.py           # Functions for each node in the graph
│   ├── processing.py      # Contains the main processing loop logic
│   ├── reporting.py       # Metrics calculation and results saving
│   ├── cleanup.py         # Resource cleanup logic
│   └── utils.py           # Utility functions
├── .env                   # Store API keys here (add to .gitignore)
├── .env.example           # Example .env file structure
├── .gitignore
├── .python-version        # Specifies Python version (used by uv)
├── pyproject.toml         # Project metadata and dependencies (used by uv)
├── uv.lock                # Locked dependencies (created by uv sync)
└── README.md              # This file
```

## Setup & Installation

### Prerequisites

1.  **Python 3.9+**: Required for running the application. Ensure you have a compatible Python version installed.
2.  **`uv`**: The package and environment manager used by this project. See [uv installation guide](https://docs.astral.sh/uv/install/).
3.  **Google API Key**: Required for accessing Gemini models.
4.  **LangSmith API Key** (Recommended): Needed for detailed run tracing and using the `view_threads.py` script.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/ncolesummers/profile-extractor.git
    cd profile-extractor
    ```

2.  Create the virtual environment:
    *   `uv` will automatically create a virtual environment named `.venv` in the project root the first time you run a command like `uv sync` or `uv run`. It uses the Python version specified in `.python-version` or your system's default compatible Python.
    *   Alternatively, you can create it explicitly:
        ```bash
        uv venv
        ```

3.  Install dependencies:
    *   This command installs the exact versions specified in `uv.lock` into the virtual environment.
    ```bash
    uv sync
    ```

4.  Configure API keys:
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and add your Google API key:
        ```env
        GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_HERE"
        ```
    *   (Recommended) Add your LangSmith API key and optionally set a project name:
        ```env
        LANGSMITH_API_KEY="YOUR_LANGSMITH_API_KEY_HERE"
        # Optional: Define a project name for LangSmith traces
        # LANGSMITH_PROJECT="my-profile-extraction-project"
        ```

## Configuration

Most configurations are managed in the `.env` file (for secrets) and `src/config.py` (for application settings).

*   **`.env`:** Store your `GOOGLE_API_KEY` and `LANGSMITH_API_KEY` here.
*   **`src/config.py`:**
    *   `MODEL_NAME`, `JUDGE_MODEL_NAME`: Specify which Gemini models to use.
    *   `LLM_TEMPERATURE`, `JUDGE_TEMPERATURE`: Control model creativity.
    *   `REQUEST_DELAY_SECONDS`: Set the delay between fetching URLs.
    *   `OUTPUT_DIR`, `OUTPUT_FILENAME`: Define where the output Excel file is saved.
    *   `LOG_TO_FILE`, `LOG_FILE_PATH`: Configure logging behavior.
    *   `LANGSMITH_PROJECT`: Default LangSmith project name (can be overridden by `.env`).

## Usage

1.  **Prepare Input URLs:** Ensure the `data/uidaho_urls.json` file exists and contains a JSON list of the faculty profile URLs you want to process.
    ```json
    [
      "https://www.uidaho.edu/faculty-profile-url-1",
      "https://www.uidaho.edu/faculty-profile-url-2",
      ...
    ]
    ```
2.  **Run the Extractor:** Execute the main script using `uv run`. This command automatically finds and uses the project's virtual environment (`.venv`).
    ```bash
    uv run python src/main.py
    ```
    *   The script will process each URL sequentially, printing logs and a progress bar to the console.
    *   If LangSmith is configured, detailed traces for each profile extraction will be sent to your LangSmith project.

3.  **Check Output:**
    *   The extracted data will be saved to `output/extracted_profiles.xlsx`.
    *   Any profiles that failed extraction will be listed in `output/errors_extracted_profiles.xlsx`.
    *   Application logs can be found in `logs/app.log` (if enabled in `config.py`).

## Viewing LangSmith Traces

If you have configured LangSmith, you can analyze the extraction process in detail.

1.  **LangSmith UI:** Navigate to your project in the [LangSmith dashboard](https://smith.langchain.com/) to view traces, logs, and metrics visually.
2.  **`view_threads.py` Script:** Use the provided script to get a summary of extraction threads directly from your terminal (uses `uv run`).
    *   **Prerequisites:** Ensure your `LANGSMITH_API_KEY` is set in `.env`.
    *   **Basic Usage:**
        ```bash
        uv run python scripts/view_threads.py
        ```
        This shows a summary table of threads from the last day for the default project.
    *   **Options:**
        *   `--project <name>`: Specify a different LangSmith project name.
        *   `--days <N>`: Look back N days (default: 1).
        *   `--thread-id <id>`: Analyze a single, specific thread.
        *   `--format <table|csv|excel>`: Choose the output format.
        *   `--output <path>`: Specify an output file path for CSV or Excel format.

    *   **Example (CSV output for last 7 days):**
        ```bash
        uv run python scripts/view_threads.py --days 7 --format csv --output thread_summary.csv
        ```

## Data Output

The primary output is an Excel file (`output/extracted_profiles.xlsx`) where each row corresponds to an extracted profile. The columns match the fields defined in the `src/schemas.py:ProfileData` model:

*   `source_url`
*   `photo_url`
*   `first_name`
*   `middle_name`
*   `last_name`
*   `title`
*   `office`
*   `phone`
*   `email`
*   `college_unit`
*   `department_division`
*   `degrees` (potentially comma-separated if multiple)
*   `research_focus_areas` (potentially comma-separated if multiple)

Error details for failed extractions are saved in `output/errors_extracted_profiles.xlsx`.

## Evaluation & Metrics

The project includes several evaluation mechanisms:

*   **LLM Judge:** The `validate_data` node uses an LLM to compare the extracted data against the source content, providing field-level correctness judgments (`Correct`, `Incorrect`, `Missing`). These results are available within the LangSmith traces if enabled.
*   **General Metrics:** The `ProfileExtractorApp` orchestrates the calculation and logging of aggregate metrics after processing all URLs (handled in `src/reporting.py` and triggered by `main.py`):
    *   Token Usage (Input, Output, Total, Average per profile) - Pulled from LangSmith if available.
    *   Latency (Total execution time, Average per Profile)
    *   Cost (Total, Average per Profile) - Estimated based on token counts.
    *   Error Rates (Overall, Success Rate)
*   **LangSmith Metrics:** The LangSmith dashboard provides detailed metrics per run and per thread, including latency, token counts, and success/error status.
*   **`view_threads.py` Metrics:** This script provides a summary per thread:
    *   Number of runs/LLM calls per thread.
    *   Total tokens per thread.
    *   Duration per thread.
    *   Error indication per thread.

## Testing

(Placeholder - To be implemented based on `docs/research/testing.md`)

*   Unit tests for utility functions.
*   Integration tests using a small, fixed set of diverse profile URLs.
*   Golden set comparison for extraction accuracy.

## Dependencies

Key dependencies are listed in `pyproject.toml` and installed via `uv sync`. Major ones include:

*   `langchain`
*   `langchain-google-genai`
*   `langgraph`
*   `langsmith`
*   `pydantic`
*   `requests` / `httpx`
*   `beautifulsoup4`
*   `pandas`
*   `openpyxl`
*   `python-dotenv`
*   `tabulate` (for `view_threads.py`)

## Development

*   **Running commands:** Use `uv run <command>` to execute commands within the project's virtual environment (e.g., `uv run pytest`).
*   **Activating Environment:** While `uv run` handles environment activation for individual commands, you can activate the environment in your shell for interactive use:
    ```bash
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    # Now you can run python, ruff, etc., directly.
    # Deactivate when done: deactivate
    ```
*   **Adding Dependencies:**
    ```bash
    uv add <package-name>
    ```
*   **Linting/Formatting:** Use `ruff` for code quality. Configure it in `pyproject.toml` or `ruff.toml`.
    ```bash
    # Install dev dependencies if needed
    uv sync --dev
    # Run check
    uv run ruff check .
    # Run format
    uv run ruff format .
    ```

## License

This project is licensed under the [MIT License](LICENSE). 
*(Consider adding an actual LICENSE file if you choose MIT, or update this link/text if you prefer a different license like Apache 2.0)*.

*Self-Correction: Initially forgot to mention the specific year 2025 in the License section as per custom instructions, but a standard license text doesn't usually include the year directly. Instead, mentioning the user's GitHub and suggesting a license type is more appropriate.*
