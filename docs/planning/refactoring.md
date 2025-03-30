**Refactoring Plan for `main.py` (using uv and existing dependencies)**

**1. Configuration Management (`src/config.py`)**

*   [x] **Goal:** Centralize all configuration loading and validation.
*   [x] Add Pydantic settings dependency: `uv add pydantic-settings` (This adds the capability to load settings from `.env` files easily with Pydantic v2+).
*   [x] Modify `src/config.py`:
    *   Import `BaseSettings` from `pydantic_settings`.
    *   Create a `Settings` class inheriting from `BaseSettings`.
    *   Define fields for `OUTPUT_DIR`, `OUTPUT_FILENAME`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, etc., using type hints.
    *   Configure `BaseSettings` to load from environment variables and potentially a `.env` file (using `model_config` with `env_file`).
    *   Instantiate the `Settings` class once to create a `settings` object that can be imported elsewhere.
*   [x] Update `main.py`: Remove direct `os.getenv` calls for configuration and import the `settings` object from `src/config.py`. Access settings like `settings.LANGSMITH_API_KEY`.
*   [x] Update other modules (e.g., `src/nodes.py` if it uses config) to import from `src/config.py` instead of `main.py` or `os.getenv`.
*   [x] Ensure the `pyproject.toml` file correctly lists `pydantic-settings` after running `uv add`.
*   [x] Run `uv sync` or let `uv run` handle syncing the environment if necessary.

**2. Application Setup (`src/setup.py`)**

*   [x] **Goal:** Isolate initialization logic for logging, LangSmith, and signal handling.
*   [x] Create `src/setup.py`.
*   [x] Move `setup_logging` function from `src.utils` to `src/setup.py`
*   [x] Move LangSmith initialization logic (checking `settings.LANGSMITH_API_KEY`, setting environment variables, creating `langsmith_client`) from `main.py` into a function in `src/setup.py` (e.g., `setup_langsmith(settings)`). This function should return the initialized `langsmith_client` (or `None`). *(Dependency `langsmith` already present)*.
*   [x] Move signal handling logic:
    *   Define a simple class (e.g., `ShutdownManager`) in `src/setup.py` to hold the shutdown state (`_shutdown_requested`).
    *   Move the `signal_handler` function into `src/setup.py`. It should update the state within an instance of `ShutdownManager`.
    *   Create a function `register_signal_handlers(shutdown_manager)` in `src/setup.py` that registers `SIGINT` and `SIGTERM` to call the `signal_handler`.
*   [x] Update `main.py`:
    *   Import necessary functions/classes from `src/setup.py`.
    *   Call `setup_logging()` at the beginning.
    *   Create an instance of `ShutdownManager`.
    *   Call `setup_langsmith()` to get the client.
    *   Call `register_signal_handlers()` with the shutdown manager instance.
    *   Remove the global `_shutdown_requested` flag. Pass the `shutdown_manager` instance or its state where needed.

**3. Processing Logic (`src/processing.py`)**

*   [x] **Goal:** Isolate the core task of processing URLs.
*   [x] Create `src/processing.py`.
*   [x] Move the `process_url` function from `main.py` to `src/processing.py`.
    *   Ensure it imports necessary dependencies (e.g., `logger`, `app` from `src.graph`, `traceable` if LangSmith is used). *(Dependencies `langgraph`, `langsmith` already present)*.
*   [x] Move the URL processing loop logic from `main.py`'s `try` block into a new function in `src/processing.py`, e.g., `run_processing_loop(urls, langgraph_app, shutdown_manager)`.
    *   This function should take the list of URLs, the LangGraph `app`, and the `shutdown_manager` instance as arguments.
    *   It should contain the `tqdm` progress bar. *(Dependency `tqdm` already present)*.
    *   Inside the loop, it should check `shutdown_manager.is_shutdown_requested()` before processing each URL.
    *   It should call the `process_url` function (now also in `src/processing.py`).
    *   It should handle the `KeyboardInterrupt` within the loop.
    *   It should return the list of `results` and a boolean `interrupted` flag.
*   [x] Move the `load_urls` function to `src/processing.py` (or potentially a new `src/data_loader.py`).
*   [x] Update `main.py`:
    *   Import `load_urls` and `run_processing_loop` from `src/processing.py`.
    *   Call `load_urls()`.
    *   Call `run_processing_loop()` with the loaded URLs, the LangGraph `app`, and the `shutdown_manager`.

**4. Reporting and Saving (`src/reporting.py`)**

*   [x] **Goal:** Isolate metrics calculation and results saving.
*   [x] Create `src/reporting.py`.
*   [x] Move `calculate_metrics` function from `main.py` to `src/reporting.py`.
    *   [x] This function will need the `results` list and potentially the `langsmith_client`, `settings` object, and `logger` as input.
    *   [x] Refactored LangSmith token retrieval for clarity. Fallback token estimation logic reviewed and kept.
*   [x] Move `save_results` function from `main.py` to `src/reporting.py`.
    *   [x] This function will need the `results` list, the calculated `metrics`, the `settings` object (for `OUTPUT_DIR`, `OUTPUT_FILENAME`), and `logger` as input. *(Dependencies `pandas`, `openpyxl` handled within reporting.py)*.
*   [x] Move `format_duration` from `src.utils` if it's only used here, or keep it in `utils`. *(Decision: Kept in `utils.py`)*.
*   [x] Update `main.py`:
    *   [x] Import `calculate_metrics` and `save_results` from `src/reporting.py`.
    *   [x] Call these functions after `run_processing_loop` completes, passing required arguments.
    *   [x] Removed the complex metrics threading logic from `main.py`. Sequential calculation is now used.

**5. Resource Cleanup (`src/cleanup.py`)**

*   [x] **Goal:** Centralize cleanup logic and address root causes of forced cleanup.
*   [x] Create `src/cleanup.py`.
*   [x] Move the `cleanup_resources` function from `main.py` to `src/cleanup.py`.
    *   [x] Remove the global `_cleanup_done` flag logic. The function can be called once from `main.py`'s `finally` block.
*   [x] **Investigate Cleanup Issues:**
    *   [x] LangSmith: Consulted documentation/refined `flush` calls.
    *   [x] LangGraph: Confirmed no explicit cleanup needed; relies on GC.
    *   [x] Threading: Root cause addressed by removing metrics threading; forced daemonization/exit removed.
*   [x] **Refactor `cleanup_resources`:** Removed need for forced daemonization and `os._exit(0)`. *(Refactoring and investigation complete)*.
*   [x] Update `main.py`:
    *   [x] Import `cleanup_resources` from `src/cleanup.py`.
    *   [x] Call it within the main `finally` block.
    *   [x] Remove the `_cleanup_done` global flag.
    *   [x] Remove the explicit LangGraph `app.close()` / `app.shutdown()` calls from the `finally` block.
    *   [x] Remove the final thread monitoring loop and `os._exit(0)` call in the `finally` block. Goal of clean `sys.exit(0)` achieved.

**6. Refactor `main.py` Orchestration**

*   [x] **Goal:** Simplify `main.py` to only coordinate the application flow.
*   [x] Remove all functions and logic that were moved to other modules (`process_url`, `calculate_metrics`, `save_results`, `cleanup_resources`, `load_urls`, signal handlers, setup logic, global flags).
*   [x] Keep the main execution block (`if __name__ == "__main__":`) and the `main()` function.
*   [x] Inside `main()`:
    *   Perform imports from the new modules (`src.config`, `src.setup`, `src.processing`, `src.reporting`, `src.cleanup`, `src.graph`).
    *   Initialize: Call setup functions (`setup_logging`, create `shutdown_manager`, `setup_langsmith`, `register_signal_handlers`), create logger, LangSmith client.
    *   Get LangGraph App: `from src.graph import app as langgraph_app`.
    *   Wrap the core logic in a `try...except...finally` block.
    *   **Try Block:**
        *   Record `start_time`.
        *   Load URLs (`urls = load_urls(logger)`).
        *   Run processing (`results, interrupted = run_processing_loop(urls, langgraph_app, shutdown_manager, settings, logger)`).
        *   Check if results exist and `not interrupted`.
        *   Calculate metrics (`metrics = calculate_metrics(results, settings, logger, langsmith_client)`).
        *   Save results (`save_results(results, metrics, settings, logger)`).
        *   Log success/interruption messages.
    *   **Except Block:** Catch top-level exceptions (including `FileNotFoundError`), log them, set exit code.
    *   **Finally Block:**
        *   Calculate and log `total_duration`.
        *   Call the main cleanup function (`cleanup_resources(logger, langsmith_client)`).
        *   Log final "exiting" message with exit code.
        *   Use `sys.exit(exit_code)`.
*   [x] Review all imports in `main.py` to ensure only necessary ones remain.
*   [x] Added top-level `if __name__ == "__main__":` exception handling for catastrophic failures before/after `main()`.

**7. Introduce Application Class**

*   [ ] **Goal:** Encapsulate state and lifecycle management.
*   [ ] Define an `App` class (e.g., in `main.py` or `src/app_class.py`).
*   [ ] Move state variables (e.g., `settings`, `langsmith_client`, `shutdown_manager`, `results`) to instance attributes (`self.settings`, etc.).
*   [ ] Convert functions like `setup_logging`, `setup_langsmith`, `run_processing_loop`, `calculate_metrics`, `save_results`, `cleanup_resources` into methods of the class.
*   [ ] The `main()` function would then instantiate the `App` class and call its main execution method (e.g., `app.run()`).
