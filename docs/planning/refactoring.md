
**Refactoring Plan for `main.py` (using uv and existing dependencies)**

**1. Configuration Management (`src/config.py`)**

*   [ ] **Goal:** Centralize all configuration loading and validation.
*   [ ] Add Pydantic settings dependency: `uv add pydantic-settings` (This adds the capability to load settings from `.env` files easily with Pydantic v2+).
*   [ ] Modify `src/config.py`:
    *   Import `BaseSettings` from `pydantic_settings`.
    *   Create a `Settings` class inheriting from `BaseSettings`.
    *   Define fields for `OUTPUT_DIR`, `OUTPUT_FILENAME`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, etc., using type hints.
    *   Configure `BaseSettings` to load from environment variables and potentially a `.env` file (using `model_config` with `env_file`).
    *   Instantiate the `Settings` class once to create a `settings` object that can be imported elsewhere.
*   [ ] Update `main.py`: Remove direct `os.getenv` calls for configuration and import the `settings` object from `src/config.py`. Access settings like `settings.LANGSMITH_API_KEY`.
*   [ ] Update other modules (e.g., `src/nodes.py` if it uses config) to import from `src/config.py` instead of `main.py` or `os.getenv`.
*   [ ] Ensure the `pyproject.toml` file correctly lists `pydantic-settings` after running `uv add`.
*   [ ] Run `uv sync` or let `uv run` handle syncing the environment if necessary.

**2. Application Setup (`src/setup.py`)**

*   [ ] **Goal:** Isolate initialization logic for logging, LangSmith, and signal handling.
*   [ ] Create `src/setup.py`.
*   [ ] Move `setup_logging` function from `src.utils` to `src/setup.py`
*   [ ] Move LangSmith initialization logic (checking `settings.LANGSMITH_API_KEY`, setting environment variables, creating `langsmith_client`) from `main.py` into a function in `src/setup.py` (e.g., `setup_langsmith(settings)`). This function should return the initialized `langsmith_client` (or `None`). *(Dependency `langsmith` already present)*.
*   [ ] Move signal handling logic:
    *   Define a simple class (e.g., `ShutdownManager`) in `src/setup.py` to hold the shutdown state (`_shutdown_requested`).
    *   Move the `signal_handler` function into `src/setup.py`. It should update the state within an instance of `ShutdownManager`.
    *   Create a function `register_signal_handlers(shutdown_manager)` in `src/setup.py` that registers `SIGINT` and `SIGTERM` to call the `signal_handler`.
*   [ ] Update `main.py`:
    *   Import necessary functions/classes from `src/setup.py`.
    *   Call `setup_logging()` at the beginning.
    *   Create an instance of `ShutdownManager`.
    *   Call `setup_langsmith()` to get the client.
    *   Call `register_signal_handlers()` with the shutdown manager instance.
    *   Remove the global `_shutdown_requested` flag. Pass the `shutdown_manager` instance or its state where needed.

**3. Processing Logic (`src/processing.py`)**

*   [ ] **Goal:** Isolate the core task of processing URLs.
*   [ ] Create `src/processing.py`.
*   [ ] Move the `process_url` function from `main.py` to `src/processing.py`.
    *   Ensure it imports necessary dependencies (e.g., `logger`, `app` from `src.graph`, `traceable` if LangSmith is used). *(Dependencies `langgraph`, `langsmith` already present)*.
*   [ ] Move the URL processing loop logic from `main.py`'s `try` block into a new function in `src/processing.py`, e.g., `run_processing_loop(urls, langgraph_app, shutdown_manager)`.
    *   This function should take the list of URLs, the LangGraph `app`, and the `shutdown_manager` instance as arguments.
    *   It should contain the `tqdm` progress bar. *(Dependency `tqdm` already present)*.
    *   Inside the loop, it should check `shutdown_manager.is_shutdown_requested()` before processing each URL.
    *   It should call the `process_url` function (now also in `src/processing.py`).
    *   It should handle the `KeyboardInterrupt` within the loop.
    *   It should return the list of `results` and a boolean `interrupted` flag.
*   [ ] Move the `load_urls` function to `src/processing.py` (or potentially a new `src/data_loader.py`).
*   [ ] Update `main.py`:
    *   Import `load_urls` and `run_processing_loop` from `src/processing.py`.
    *   Call `load_urls()`.
    *   Call `run_processing_loop()` with the loaded URLs, the LangGraph `app`, and the `shutdown_manager`.

**4. Reporting and Saving (`src/reporting.py`)**

*   [ ] **Goal:** Isolate metrics calculation and results saving.
*   [ ] Create `src/reporting.py`.
*   [ ] Move `calculate_metrics` function from `main.py` to `src/reporting.py`.
    *   This function will need the `results` list and potentially the `langsmith_client` and `settings` object as input.
    *   Refactor the LangSmith token retrieval part for clarity if possible. Review if the fallback token estimation logic is still desired.
*   [ ] Move `save_results` function from `main.py` to `src/reporting.py`.
    *   This function will need the `results` list, the calculated `metrics`, and the `settings` object (for `OUTPUT_DIR`, `OUTPUT_FILENAME`) as input. *(Dependencies `pandas`, `openpyxl` already present)*.
*   [ ] Move `format_duration` from `src.utils` if it's only used here, or keep it in `utils`.
*   [ ] Update `main.py`:
    *   Import `calculate_metrics` and `save_results` from `src/reporting.py`.
    *   Call these functions after `run_processing_loop` completes.
    *   Remove the complex metrics threading logic from `main.py`. Evaluate if sequential calculation is acceptable. If threading *is* essential, implement it within `src/reporting.py` or potentially use `concurrent.futures`.

**5. Resource Cleanup (`src/cleanup.py`)**

*   [ ] **Goal:** Centralize cleanup logic and address root causes of forced cleanup.
*   [ ] Create `src/cleanup.py`.
*   [ ] Move the `cleanup_resources` function from `main.py` to `src/cleanup.py`.
    *   Remove the global `_cleanup_done` flag logic. The function can be called once from `main.py`'s `finally` block.
*   [ ] **Investigate Cleanup Issues:**
    *   **LangSmith:** Consult LangSmith client documentation for the recommended way to shut down and ensure all background tasks/threads are properly terminated. Does `client.close()` suffice? Is `auto_batch_tracing=False` contributing?
    *   **LangGraph:** Review how the `app` object (`app.close()`, `app.shutdown()`) is intended to be cleaned up. Ensure the graph itself doesn't have long-running or blocking operations that prevent graceful shutdown. Check if `config={"max_concurrency": 1}` in `process_url` truly prevents all internal concurrency issues.
    *   **Threading:** Identify *which* specific threads are not exiting cleanly by adding more detailed logging in the original `cleanup_resources` *before* moving it (e.g., log thread names and states). Address the root cause in the relevant component (LangSmith, LangGraph, custom threads).
*   [ ] **Refactor `cleanup_resources`:** Aim to remove the need to force threads to daemon status (`thread.daemon = True`) and eliminate the call to `os._exit(0)`. Proper resource management (e.g., using context managers `with ...:`) and fixing underlying blocking calls should be prioritized.
*   [ ] Update `main.py`:
    *   Import `cleanup_resources` from `src/cleanup.py`.
    *   Call it within the main `finally` block.
    *   Remove the `_cleanup_done` global flag.
    *   Remove the explicit LangGraph `app.close()` / `app.shutdown()` calls from the `finally` block if this cleanup is now handled reliably within `cleanup_resources` or via context managers.
    *   Remove the final thread monitoring loop and `os._exit(0)` call in the `finally` block. The goal is a clean `sys.exit(0)`.

**6. Refactor `main.py` Orchestration**

*   [ ] **Goal:** Simplify `main.py` to only coordinate the application flow.
*   [ ] Remove all functions and logic that were moved to other modules (`process_url`, `calculate_metrics`, `save_results`, `cleanup_resources`, `load_urls`, signal handlers, setup logic, global flags).
*   [ ] Keep the main execution block (`if __name__ == "__main__":`) and the `main()` function.
*   [ ] Inside `main()`:
    *   Perform imports from the new modules (`src.config`, `src.setup`, `src.processing`, `src.reporting`, `src.cleanup`, `src.graph`).
    *   Initialize: Call setup functions (`setup_logging`, create `shutdown_manager`, `setup_langsmith`, `register_signal_handlers`).
    *   Get LangGraph App: `from src.graph import app` (or pass it around if necessary).
    *   Wrap the core logic in a `try...finally` block.
    *   **Try Block:**
        *   Record `start_time`.
        *   Load URLs (`urls = load_urls()`).
        *   Run processing (`results, interrupted = run_processing_loop(urls, app, shutdown_manager)`).
        *   Check if results exist and `not interrupted` (or based on desired logic).
        *   Calculate metrics (`metrics = calculate_metrics(results, langsmith_client, settings)`).
        *   Save results (`save_results(results, metrics, settings)`).
        *   Log success messages.
    *   **Except Block:** Catch top-level exceptions, log them.
    *   **Finally Block:**
        *   Calculate and log `total_duration`.
        *   Call the main cleanup function (`cleanup_resources(langsmith_client, app)` - pass necessary resources if they aren't accessible globally or via context managers).
        *   Log final "exiting" message.
        *   Use `sys.exit(0)` for success or `sys.exit(1)` for errors caught in the `except` block.
*   [ ] Review all imports in `main.py` to ensure only necessary ones remain.

**7. Introduce Application Class**

*   [ ] **Goal:** Encapsulate state and lifecycle management.
*   [ ] Define an `App` class (e.g., in `main.py` or `src/app_class.py`).
*   [ ] Move state variables (e.g., `settings`, `langsmith_client`, `shutdown_manager`, `results`) to instance attributes (`self.settings`, etc.).
*   [ ] Convert functions like `setup_logging`, `setup_langsmith`, `run_processing_loop`, `calculate_metrics`, `save_results`, `cleanup_resources` into methods of the class.
*   [ ] The `main()` function would then instantiate the `App` class and call its main execution method (e.g., `app.run()`).
