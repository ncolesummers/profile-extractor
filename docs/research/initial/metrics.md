# Project Metrics

This document details the metrics used to evaluate the performance, quality, and cost of the profile extraction process.

## Phase 4: Metrics Calculation (`main.py`)

1.  **Process Results & Calculate Metrics:**
    *   Filter results: Separate successful runs (`final_state['extracted_data'] is not None`) from errors.
    *   Create lists/dictionaries to hold metric values extracted from `final_state['metrics']` for each profile.
    *   **Calculate General Metrics (11-23):**
        *   **Token Usage:**
            - `Total Input Tokens`: Sum of `input_tokens` across all profiles.
            - `Total Output Tokens`: Sum of `output_tokens` across all profiles.
            - `Average Input Tokens per Profile`: Average `input_tokens`.
            - `Average Output Tokens per Profile`: Average `output_tokens`.
            - `Token Efficiency Ratio`: (Total Output Tokens / Total Input Tokens) - *Lower might indicate concise extraction relative to input size.*
        *   **Latency/Throughput:**
            - `Average Latency Per Profile (ms)`: Average sum of (`fetch_time_ms` + `preprocess_time_ms` + `extraction_time_ms` + `validation_time_ms`) for successful profiles.
            - `Throughput (Profiles per Second)`: (Total successful profiles / Total processing time in seconds).
        *   **Cost:**
            - `Total Cost`: Sum of `cost_per_profile` across all profiles (including judge costs if tracked separately).
            - `Average Cost Per Profile`: Average `cost_per_profile`.
        *   **Error Rate:**
            - `Overall Error Rate (%)`: (Number of final states with `error` / Total URLs processed) * 100.
            - `Fetch Error Rate (%)`: (Number of fetch errors / Total URLs) * 100.
            - `Preprocess Error Rate (%)`: (Number of preprocess errors / Total successful fetches) * 100.
            - `Extraction Error Rate (%)`: (Number of extraction errors / Total successful preprocesses) * 100.
            - `Validation Error Rate (%)`: (Number of validation errors / Total successful extractions) * 100.
        *   *Note:* Memory Usage, Inference Time vs Prep, Confidence Scores, Coverage, Context Window Use, Rate Limit Impact might require more advanced profiling tools (like `memory-profiler`), deeper LLM response inspection (if available), or specific experimental setups (e.g., varying request rates). Focus on the directly measurable ones first.
    *   **Calculate Profile-Specific Metrics (1-10 - Based on LLM Judge):**
        *   Use `validation_result` from the judge. Iterate through fields for each profile.
        *   **Precision (per field):** TP / (TP + FP)
            - TP (True Positive): `status` is 'Correct'.
            - FP (False Positive): `status` is 'Incorrect'.
        *   **Recall (per field):** TP / (TP + FN)
            - TP (True Positive): `status` is 'Correct'.
            - FN (False Negative): `status` is 'Incorrect' OR 'Missing'.
        *   **F1-Score (per field):** 2 * (Precision * Recall) / (Precision + Recall)
        *   **Completeness Rate (per profile):** (Number of non-null fields successfully extracted in `extracted_data` / Total fields defined in `ProfileData`) per profile. Average across profiles.
        *   **Entity Recognition Accuracy:** Subset of Precision/Recall/F1 focusing specifically on named entities (Names, Locations, Organizations) if validation distinguishes these.
        *   **Structural Accuracy (overall):** Percentage of profiles where `extracted_data` is not `None` and passed Pydantic validation (inherent in successful runs). Can track specific Pydantic validation failures if they occur before the judge.
        *   **Data Type Validation Accuracy (per field):** Percentage of 'Correct' statuses where the data type matches the Pydantic schema (Pydantic handles initial validation; judge confirms semantic correctness). Track judge reasons pointing to type issues (e.g., 'Expected email, got plain text').
        *   **Deduplication Accuracy:** Not directly applicable per profile unless list fields (degrees, research areas) contain duplicates that should have been merged. Can measure as (1 - (Duplicate Items / Total Items)) within lists, averaged across profiles.
        *   **Consistency Score:** Harder to automate. Requires defining rules (e.g., phone number format) and checking adherence across profiles. Could be a manual spot-check metric initially.
        *   **Missing Data Rate (per field):** (Number of 'Missing' statuses from judge / Total profiles judged) for that field.
        *   **False Positive Rate (per field):** (Number of 'Incorrect' statuses from judge / Total profiles judged) for that field.
    *   Print or log calculated metrics. 