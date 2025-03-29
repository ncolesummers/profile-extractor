# Testing and Validation

This document outlines the strategy for testing the extraction pipeline, validating the quality of the extracted data, and monitoring performance over time.

## Phase 5: Testing & Validation

1. **Test Data Management:**
   * Create a "golden set" of 10-20 manually verified profiles representing diverse cases.
   * Include various edge cases:
     - Different page layouts/templates observed.
     - Profiles with missing or partial information (e.g., no photo, no phone).
     - Names/titles with special characters or unusual formatting.
     - Multiple degrees, titles, or research areas.
     - Long research descriptions or degree lists.
   * Store this golden set, including the source HTML and the expected `ProfileData` JSON, in a structured format (e.g., `data/golden_set/profile_X/source.html`, `data/golden_set/profile_X/expected_output.json`). This allows for automated comparison.

2. **Validation Pipeline:**
   * **Automated Testing:**
     - Create a test script (e.g., using `pytest`) that:
       - Runs each profile from the golden set through the full extraction pipeline (potentially mocking the `fetch_page` node to use the stored HTML).
       - Compares the actual `extracted_data` against the `expected_output.json` for that profile.
       - Generates a detailed report showing discrepancies field-by-field.
       - Calculates key accuracy metrics (Precision, Recall, F1) specifically against the golden set.
     - Integrate this test script into a CI/CD workflow if applicable.
   * **Manual Review Process:**
     - Define a sampling strategy (e.g., random sampling of 5-10% of the *full* extracted dataset after a large run, stratified by department or college if possible).
     - Develop a review checklist focusing on critical fields (name, title, email, college, department) and common error patterns observed during testing.
     - Use a simple tool or spreadsheet to track manual review findings, documenting discrepancies, patterns, and potential root causes (e.g., HTML change, LLM misinterpretation).

3. **Quality Gates:**
   * **Pre-Processing Checks:**
     - **URL Validation:** Ensure URLs are valid and accessible before fetching.
     - **HTML Structure Verification:** Basic checks (e.g., presence of `<body>` tag) after fetch, log warnings for unexpected minimal content.
     - **Content Length Checks:** Flag pages with unusually small or large amounts of `preprocessed_content` as potential issues for investigation.
   * **Post-Processing Checks:**
     - **Pydantic Validation:** Already handled by the schema and `with_structured_output`.
     - **Format Consistency Checks:** Add checks in the `main.py` processing step for common formatting issues (e.g., inconsistent phone number formats, leading/trailing whitespace) and attempt normalization.
     - **Duplicate Detection:** Check for duplicate `source_url` entries being processed. After extraction, check for highly similar profiles (e.g., based on name and department) that might indicate duplicate source pages were included in the input list.
   * **Release Criteria (Example):**
     - Golden Set Accuracy: > 95% F1-score average across critical fields.
     - Full Dataset Spot Check: < 5% error rate on critical fields during manual review.
     - No critical data type errors causing processing failures.
     - Processing time within acceptable limits (e.g., average < 30s/profile).
     - Estimated cost per profile within budget.

4. **Continuous Monitoring:**
   *(Details potentially moved to a separate deployment/monitoring document)*
   * **Extraction Accuracy Tracking:** Regularly re-run the golden set tests (e.g., daily or weekly) to quickly catch regressions or impacts from website changes.
   * **LLM Judge Metrics:** Monitor the aggregate `ValidationResult` statuses ('Correct', 'Incorrect', 'Missing') per field over time to identify degrading performance.
   * **Error Rate Monitoring:** Track the different error rates (fetch, preprocess, extract, validate) to pinpoint recurring issues.
   * **Website Change Detection:** Implement basic checks (e.g., comparing page structure or content length hashes) for known profile URLs to detect potential breaking changes proactively. 