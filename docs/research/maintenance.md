# Maintenance and Future Improvements

This document outlines the plan for maintaining the extraction process after the initial launch and potential areas for future enhancements.

## Continuous Monitoring & Maintenance Plan

*(This section overlaps with testing/monitoring but focuses on ongoing activities post-initial validation)*

1.  **Pre-Launch Monitoring Activities (If applicable before a specific website launch):**
    *   **Frequency:** Define frequency for running full extractions (e.g., weekly) to catch new profiles or content changes.
    *   **Validation:** Regularly run automated tests against the golden set and perform smaller manual spot checks.
    *   **Reporting:** Establish a cadence for reporting accuracy, completeness, and cost metrics to stakeholders.
    *   **Change Tracking:** Monitor source website for structural changes (manual checks or automated detection).

2.  **Data Migration Support (If applicable):**
    *   **Tracking:** Maintain logs of profiles successfully extracted and formatted for migration.
    *   **Issue Documentation:** Document any data transformation challenges or edge cases encountered.
    *   **Mapping:** If migrating from an old system, maintain mapping between old and new identifiers if possible.
    *   **Verification:** Support testing of the data import process into the target system.

3.  **Launch Support (If applicable):**
    *   Monitor the initial large-scale extraction run closely.
    *   Track data quality issues identified post-import.
    *   Provide support for verifying imported profiles.
    *   Document any problems encountered during the migration/launch.

4.  **Post-Launch Maintenance:**
    *   **Archiving:** Archive the extraction code version, dependencies (`uv.lock`), configuration, and the final extracted dataset (`.xlsx` and potentially intermediate `all_results` data) for each major run.
    *   **Documentation:** Update documentation with lessons learned, final metrics, and any adjustments made.
    *   **Maintenance Guide:** Create a concise guide covering:
        *   How to run the extraction.
        *   Common failure points and troubleshooting steps.
        *   How to update dependencies.
        *   How to retrain or fine-tune models if necessary in the future.
    *   **Knowledge Transfer:** Ensure the team responsible for the website or data management understands the process and potential maintenance needs.
    *   **Scheduled Checks:** Define a schedule (e.g., quarterly, yearly) for reviewing the extraction process, checking for website changes, and potentially re-running evaluations.

## Future Improvements

1.  **Extraction Enhancements:**
    *   Add extraction support for additional profile fields as requirements evolve.
    *   Improve accuracy for specific departments or profile types that prove challenging.
    *   Develop more sophisticated handling for edge cases (e.g., ambiguous titles, complex degree names).
    *   Optimize processing speed further through parallelization, asynchronous requests (using `httpx`), or more efficient preprocessing.

2.  **Tooling & Support:**
    *   Develop simple data validation tools (e.g., scripts to check common format issues in the output Excel).
    *   Create scripts to verify data migration steps if applicable.
    *   Build utilities for comparing extracted data across different runs or against previous versions.
    *   Integrate with a more formal issue tracking system for managing identified data problems.

3.  **Post-Launch & Long-Term:**
    *   Refine archiving procedures.
    *   Update documentation on data sources and lineage.
    *   Formalize procedures for handling website updates or significant content changes.
    *   Plan for periodic re-evaluation or potential model updates (e.g., if new Gemini versions offer better cost/performance). 