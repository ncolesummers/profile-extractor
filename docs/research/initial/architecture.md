# Project Architecture

This document outlines the technical architecture, including project setup, environment configuration, and the LangGraph implementation details.

## Phase 1: Project Setup & Environment

1.  **Environment Management (uv):**
    *   Install `uv` (no need for pipx, follow official installation guide)
    *   Initialize project: `uv init`
    *   This will create:
        *   `pyproject.toml` for project metadata and dependencies
        *   `.python-version` for specifying Python version
        *   A virtual environment will be created automatically on first command

2.  **Dependency Installation (uv):**
    *   Update `pyproject.toml` dependencies section:
    ```toml
    [project]
    name = "profile-extractor"
    version = "0.1.0"
    description = "Extract faculty profiles using LLMs"
    readme = "README.md"
    dependencies = [
        "langchain",
        "langchain-google-genai",
        "langgraph",
        "pydantic",
        "requests",
        "beautifulsoup4",
        "pandas",
        "openpyxl",
        "python-dotenv",
        "httpx"
    ]

    [project.optional-dependencies]
    dev = [
        "ruff",
        "ipython"
    ]
    ```
    *   Install dependencies: `uv sync`
    *   This will create/update `uv.lock` for reproducible installations

3.  **Project Structure:**
    ```
    profile-extractor/
    ├── .venv/                 # Created automatically by uv
    ├── data/
    │   └── uidaho_urls.json
    ├── output/
    │   └── extracted_profiles.xlsx
    ├── src/
    │   ├── __init__.py
    │   ├── schemas.py
    │   ├── graph.py
    │   ├── nodes.py
    │   ├── main.py
    │   ├── utils.py
    │   └── config.py
    ├── .env                   # Add to .gitignore
    ├── .python-version        # Created by uv init
    ├── pyproject.toml        # Created by uv init
    ├── uv.lock               # Created by uv sync
    └── README.md
    ```

4.  **Configuration (`.env`, `config.py`):**
    *   Store `GOOGLE_API_KEY` in `.env`.
    *   Use `python-dotenv` in `config.py` to load the key.
    *   Define constants in `config.py`: `MODEL_NAME` ("gemini-2.0-flash-latest"), `REQUEST_DELAY_SECONDS` (e.g., 2.0), `LLM_TEMPERATURE` (e.g., 0.1 for extraction), `JUDGE_MODEL_NAME`, `JUDGE_TEMPERATURE`.

## Phase 3: LangGraph Implementation (`graph.py`, `nodes.py`)

1.  **Define Graph State (`graph.py`):**
    *   Use `typing.TypedDict` for the state passed between nodes.
    ```python
    from typing import TypedDict, Optional, Dict, Any
    from .schemas import ProfileData, ValidationResult

    class GraphState(TypedDict):
        url: str
        html_content: Optional[str]
        preprocessed_content: Optional[str] # Text or HTML snippet
        extracted_data: Optional[ProfileData]
        validation_result: Optional[ValidationResult]
        metrics: Dict[str, Any] # Store timings, tokens, etc.
        error: Optional[str]
        error_details: Optional[Dict[str, Any]] # Store exception info if needed
    ```

2.  **Implement Node Functions (`nodes.py`):**
    *   **`fetch_page(state: GraphState) -> GraphState`:**
        *   Imports: `requests`, `time`, `config`.
        *   Get `url` from state.
        *   Start timer.
        *   `time.sleep(config.REQUEST_DELAY_SECONDS)` **before** making the request.
        *   Use `requests.get()` with a timeout and appropriate headers (e.g., User-Agent).
        *   Error Handling: `try...except requests.exceptions.RequestException as e:` -> update `error`, `error_details`. Check `response.raise_for_status()`.
        *   Update state: `html_content`, `metrics['fetch_time_ms']`, `error`.
        *   End timer.
        *   Return updated state.
    *   **`preprocess_html(state: GraphState) -> GraphState`:**
        *   Imports: `BeautifulSoup`.
        *   Get `html_content`. Handle case where it's `None`.
        *   Start timer.
        *   Parse with `BeautifulSoup(html_content, 'html.parser')`.
        *   *Strategy for variable structure:*
            *   Attempt 1: Find a specific common container ID or class (e.g., `#profile-main`, `.content-area`).
            *   Attempt 2 (Fallback): If not found, extract text from `soup.body` or `soup.main`.
            *   Consider removing boilerplate (headers, footers, navs) using `decompose()`.
        *   Extract relevant text: `container.get_text(separator=' ', strip=True)`. Or pass a cleaned HTML snippet if needed.
        *   Error Handling: `try...except Exception as e:` -> update `error`.
        *   Update state: `preprocessed_content`, `metrics['preprocess_time_ms']`, `error`.
        *   End timer.
        *   Return updated state.
    *   **`extract_data(state: GraphState) -> GraphState`:**
        *   Imports: `ChatGoogleGenerativeAI`, `ChatPromptTemplate`, `config`, `schemas`.
        *   Get `preprocessed_content`. Handle `None`.
        *   Start timer.
        *   Instantiate LLM: `llm = ChatGoogleGenerativeAI(model=config.MODEL_NAME, temperature=config.LLM_TEMPERATURE, convert_system_message_to_human=True)` (Check API for latest recommended setup).
        *   Define prompt instructing extraction based on `ProfileData` schema.
        *   Use structured output: `structured_llm = llm.with_structured_output(schemas.ProfileData)`.
        *   Create chain: `chain = prompt | structured_llm`.
        *   Invoke: `try: result = chain.invoke({"page_content": preprocessed_content}) except Exception as e: ...`. Capture LLM API errors, validation errors from Pydantic if `with_structured_output` fails.
        *   *Token/Cost Tracking:* Use LangChain Callbacks (`get_openai_callback` is for OpenAI, need equivalent for Google or inspect response metadata if available) or LangSmith. Store `input_tokens`, `output_tokens`. Calculate `cost` based on Gemini pricing.
        *   Update state: `extracted_data` (as `ProfileData` instance), `metrics['extraction_time_ms']`, `metrics['input_tokens']`, `metrics['output_tokens']`, `metrics['cost_per_profile']`, `error`.
        *   End timer.
        *   Return updated state.
    *   **`validate_data(state: GraphState) -> GraphState`:** (LLM Judge)
        *   Imports: `ChatGoogleGenerativeAI`, `ChatPromptTemplate`, `config`, `schemas`.
        *   Get `preprocessed_content`, `extracted_data`. Handle `None`.
        *   Start timer.
        *   Instantiate Judge LLM (can be same model/config or different).
        *   Define judge prompt: Instruct it to compare `preprocessed_content` and `extracted_data` (serialized to JSON string) and output JSON matching `ValidationResult` schema.
        *   Use structured output: `judge_structured_llm = judge_llm.with_structured_output(schemas.ValidationResult)`.
        *   Create judge chain.
        *   Invoke judge chain. Handle errors.
        *   *Token/Cost Tracking:* Track judge tokens/cost separately if needed.
        *   Update state: `validation_result`, `metrics['validation_time_ms']`, `metrics['judge_input_tokens']`, `metrics['judge_output_tokens']`, `error`.
        *   End timer.
        *   Return updated state.
    *   **`handle_error(state: GraphState) -> GraphState`:**
        *   Logs the error message and details stored in the state.
        *   Could potentially add retry logic here based on error type.
        *   Return state.

3.  **Define Graph Logic (`graph.py`):**
    *   Imports: `StateGraph`, `GraphState`, functions from `nodes.py`.
    *   Instantiate `graph = StateGraph(GraphState)`.
    *   Add nodes: `graph.add_node("fetch", nodes.fetch_page)`, `graph.add_node("preprocess", nodes.preprocess_html)`, etc.
    *   Set entry point: `graph.set_entry_point("fetch")`.
    *   Define conditional edges:
        ```python
        from langgraph.graph import END # Ensure END is imported

        def should_continue(state: GraphState) -> str:
            return "error" if state.get("error") else "continue"

        graph.add_conditional_edges(
            "fetch",
            lambda state: "preprocess" if not state.get("error") else "handle_error",
        )
        graph.add_conditional_edges(
            "preprocess",
            lambda state: "extract" if not state.get("error") else "handle_error",
         )
        graph.add_conditional_edges(
            "extract",
             lambda state: "validate" if state.get("extracted_data") and not state.get("error") else "handle_error",
        )
        graph.add_edge("validate", END) # Or add more steps
        graph.add_edge("handle_error", END) # Or potentially a retry node
        ```
    *   Compile the graph: `app = graph.compile()`.

## Phase 4: Execution & Output (`main.py` - Core Logic)

*(Note: Metric calculation details are in [metrics.md](./metrics.md))*

1.  **Load URLs:**
    *   Imports: `json`, `pandas as pd`, `config`, `graph.app`.
    *   Load URLs from `data/uidaho_urls.json`.
    *   Select a subset for initial testing.

2.  **Run Graph Iteratively:**
    *   Initialize an empty list `all_results = []`.
    *   Loop through the selected URLs:
        ```python
        import time # Ensure time is imported if used for delays

        # Assuming 'app' is the compiled LangGraph application
        # url_subset = [...] # Load your URLs here

        for url in url_subset:
            print(f"Processing: {url}")
            initial_state = {"url": url, "metrics": {}, "error": None}
            # Use stream for better observability during run
            final_state = None
            try:
                # Set a recursion limit to prevent infinite loops
                for event in app.stream(initial_state, {"recursion_limit": 10}):
                    # print(event) # Log intermediate steps/state changes
                    # The final state is available in the event keyed by the graph's end node name
                    # or often accessible via the last event before END
                    if list(event.keys())[0] == END: # Check if it's the end node event
                         final_state = event[END]
                    else:
                         # Keep track of the latest state update
                         pass # Or store the latest full state if needed

                # Fallback if END node structure is different or state needs explicit fetching
                if final_state is None:
                     # You might need to inspect the last event differently
                     # or use invoke to get the final state directly if streaming isn't essential for final result
                     final_state = app.invoke(initial_state, {"recursion_limit": 10})

            except Exception as e:
                print(f"Error processing {url}: {e}")
                # Handle graph execution errors, potentially store error state
                final_state = {"url": url, "metrics": {}, "error": str(e), "error_details": {}}

            if final_state:
                 all_results.append(final_state)
            # Optional: Add a small extra delay between processing URLs
            # time.sleep(0.5)
        ```

3.  **Generate Excel Output:**
    *   Create a list of dictionaries from successful `extracted_data` Pydantic objects: `data_to_export = [res['extracted_data'].dict() for res in all_results if res.get('extracted_data')]`.
    *   Convert to DataFrame: `df = pd.DataFrame(data_to_export)`.
    *   Handle list columns (like `degrees`, `research_focus_areas`) if needed (e.g., convert list to comma-separated string: `df['degrees'] = df['degrees'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)`).
    *   Save to Excel: `df.to_excel("output/extracted_profiles.xlsx", index=False, engine='openpyxl')`. 