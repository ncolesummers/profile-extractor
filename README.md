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

## Features

*   **Web Crawling:** Fetches HTML content from specified profile URLs.
*   **HTML Preprocessing:** Cleans and extracts relevant content from raw HTML, attempting to handle varying structures.
*   **LLM-Powered Extraction:** Uses Google Gemini models via LangChain to extract information into a predefined Pydantic schema (`ProfileData`).
*   **LLM-Powered Validation:** Employs a separate LLM judge call to evaluate the accuracy of the extracted fields against the preprocessed content (`ValidationResult`).
*   **Structured Output:** Ensures data conforms to the `ProfileData` schema using Pydantic.
*   **Error Handling:** Captures and logs errors during the fetch, preprocess, extract, and validate stages.
*   **Metric Tracking:** Records token usage, cost, latency, and error rates for each step and overall.
*   **Configurable:** Allows setting API keys, model names, and request delays via configuration.
*   **Reproducible Environment:** Uses `uv` for dependency management.

## Architecture Overview

The core logic is implemented as a [LangGraph](https://python.langchain.com/docs/langgraph/) state machine:

1.  **`fetch_page`:** Retrieves the HTML content for a given profile URL, respecting configured delays.
2.  **`preprocess_html`:** Parses the HTML using BeautifulSoup, attempts to isolate the main profile content, and extracts text or a cleaned HTML snippet. Handles basic errors and variations.
3.  **`extract_data`:** Sends the preprocessed content to a Google Gemini model (configured via `config.py`) instructed to extract information according to the `src/schemas.py:ProfileData` Pydantic schema. Uses LangChain's `with_structured_output`. Tracks tokens and cost.
4.  **`validate_data`:** Sends the preprocessed content and the extracted data (as JSON) to a Google Gemini model (potentially the same or a different one) instructed to act as a judge. The judge returns a `src/schemas.py:ValidationResult` Pydantic schema, evaluating the correctness of each field. Tracks judge tokens/cost.
5.  **`handle_error`:** A terminal node that logs any errors encountered in the preceding steps.
6.  **Conditional Edges:** The graph transitions between nodes based on success or failure (error state).

**Key Technologies:**

*   **Python:** Core programming language.
*   **uv:** Environment and package management.
*   **LangChain & LangGraph:** Orchestration of the LLM workflow.
*   **LangChain Google Generative AI:** Integration with Google Gemini models.
*   **Pydantic:** Data modeling and validation (`ProfileData`, `ValidationResult`).
*   **Requests/HTTPX:** Fetching web pages.
*   **BeautifulSoup4:** HTML parsing.
*   **Pandas & Openpyxl:** Creating the final Excel output.
*   **python-dotenv:** Loading environment variables (API keys).
*   **Ruff:** Linting and formatting (for development).

## Project Structure

```
profile-extractor/
├── .venv/                 # Managed by uv
├── data/
│   └── uidaho_urls.json   # Input list of profile URLs (example)
├── docs/
│   ├── research/          # Research documents (architecture, metrics, etc.)
│   └── prompts/           # LLM Prompts
├── output/
│   └── extracted_profiles.xlsx # Generated Excel file
├── src/
│   ├── __init__.py
│   ├── schemas.py         # Pydantic data models (ProfileData, ValidationResult)
│   ├── graph.py           # LangGraph definition and state
│   ├── nodes.py           # Functions for each node in the graph
│   ├── main.py            # Main script to load URLs, run graph, save output
│   ├── utils.py           # Utility functions (e.g., timers, logging setup)
│   └── config.py          # Configuration loading (API Key, model names, delays)
├── .env                   # Store API keys here (add to .gitignore)
├── .gitignore
├── .python-version        # Specifies Python version (used by uv)
├── pyproject.toml        # Project metadata and dependencies (used by uv)
├── uv.lock               # Locked dependencies (created by uv sync)
└── README.md              # This file
```

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd profile-extractor
    ```
2.  **Install `uv`:** Follow the official [uv installation guide](https://github.com/astral-sh/uv#installation).
3.  **Install Dependencies:** `uv` will automatically create a virtual environment and install dependencies based on `pyproject.toml` and `uv.lock`.
    ```bash
    uv sync
    ```
    *(If you need developer tools like `ruff`, install them via `uv sync --dev`)*

## Configuration

1.  Create a `.env` file in the project root directory.
2.  Add your Google Generative AI API key to the `.env` file:
    ```env
    GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```
3.  Adjust other settings like model names (`MODEL_NAME`, `JUDGE_MODEL_NAME`) and `REQUEST_DELAY_SECONDS` in `src/config.py` if needed.

## Usage

1.  **Prepare Input URLs:** Ensure the `data/uidaho_urls.json` file exists and contains a JSON list of the faculty profile URLs you want to process.
    ```json
    [
      "https://www.uidaho.edu/faculty-profile-url-1",
      "https://www.uidaho.edu/faculty-profile-url-2",
      ...
    ]
    ```
2.  **Run the Extractor:** Execute the main script. `uv` automatically manages the virtual environment.
    ```bash
    uv run python src/main.py
    ```
3.  **Check Output:** The extracted data will be saved to `output/extracted_profiles.xlsx`. Logs and metrics may be printed to the console during execution.

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

## Evaluation & Metrics

The project includes several evaluation mechanisms:

*   **LLM Judge:** The `validate_data` node uses an LLM to compare the extracted data against the source content, providing field-level correctness judgments (`Correct`, `Incorrect`, `Missing`).
*   **General Metrics:** The `main.py` script calculates and reports aggregate metrics after processing all URLs:
    *   Token Usage (Input, Output, Average)
    *   Latency (Average per Profile, Throughput)
    *   Cost (Total, Average per Profile)
    *   Error Rates (Overall, Fetch, Preprocess, Extract, Validate)
*   **Profile-Specific Metrics:** Derived from the LLM judge results:
    *   Precision, Recall, F1-Score (per field)
    *   Completeness Rate
    *   Missing Data Rate (per field)

Refer to `docs/research/metrics.md` for detailed definitions.

## Testing

A testing strategy is defined in `docs/research/testing.md`:

*   **Golden Set:** A manually curated set of diverse profile examples (`source.html` and `expected_output.json`) stored locally for regression testing.
*   **Automated Tests:** Scripts (potentially using `pytest`) compare pipeline output against the golden set.
*   **Manual Review:** Procedures for sampling and reviewing the full output dataset.
*   **Quality Gates:** Checks integrated into the pipeline (URL validity, content length, Pydantic validation, format consistency) to ensure data quality.

## Dependencies

Key dependencies are listed in `pyproject.toml` and managed by `uv`. Major ones include:

*   `langchain`
*   `langchain-google-genai`
*   `langgraph`
*   `pydantic`
*   `requests` / `httpx`
*   `beautifulsoup4`
*   `pandas`
*   `openpyxl`
*   `python-dotenv`

## Development

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

(Specify License - e.g., MIT, Apache 2.0, etc.)
