# Feature: Crawl for Person Profiles

In an effort to address the Known Issues in the [Research Spike](../initial/spike.md), I need to plan some updates. Because the sitemap is out of date, we now need to validate the URLs in the sitemap by crawling for new Profiles. 

I have a series of group pages that follow an "Our People pattern that can be used to crawl for new profiles.

## Plan to Crawl for Person Profiles

**Project Goal:** Augment the existing `output/extracted_profiles.csv` by discovering new profile URLs from the provided group pages (`docs/research/second_pass/group_urls.json`), extracting their data, and merging the results.

**Plan:**

**Phase 1: URL Discovery and Filtering**

1.  **Analyze Sample Group Pages:**
    *   Before full crawling, manually inspect a representative sample (e.g., 5-10) of URLs from `docs/research/second_pass/group_urls.json`.
    *   Identify common HTML structures (e.g., specific `div` classes containing profile lists, common parent elements) and `href` patterns (e.g., containing `/people/`, `/our-people/`, `/faculty/`, `firstname-lastname`) used for linking to individual profiles.
    *   **Goal:** Verify if a generalizable approach (e.g., a few common CSS selectors or `href` patterns) can capture profile links across the diverse group pages. Document findings.
2.  **Develop & Refine Crawler Script:**
    *   Create/update a Python script using `requests` or `httpx` and `BeautifulSoup4`.
    *   Based on the analysis (Step 1), implement logic to:
        *   Fetch HTML content for each group page URL in `docs/research/second_pass/group_urls.json`, respecting `robots.txt` and incorporating delays (e.g., 1-2 seconds) between requests.
        *   Parse the HTML with `BeautifulSoup`.
        *   Use the identified common patterns/selectors to find potential profile `<a>` tags.
        *   Extract the `href` value for each potential profile link.
3.  **Normalize and Filter URLs:**
    *   Convert relative URLs to absolute URLs (e.g., prepend `https://www.uidaho.edu` if missing).
    *   Filter out irrelevant links (e.g., links to department homepages, PDFs, external sites, anchor links `#`, mailto links).
    *   Store the discovered, cleaned URLs in a temporary list.
4.  **Identify Unique New URLs:**
    *   Load the `source_url` column from `output/extracted_profiles.csv` into a set for efficient lookup.
    *   Create a new list containing only those discovered URLs that are *not* present in the existing set.
    *   Remove duplicates from this new list.
5.  **Output:**
    *   Save the final list of unique, new profile URLs to `data/new_profile_urls.json`.

*   **Definition of Done (Phase 1):** `data/new_profile_urls.json` exists and contains a list of unique profile URLs not found in the original `output/extracted_profiles.csv`, based on a discovery method verified against a sample of group pages.

**Phase 2: Profile Extraction**

1.  **Adapt Existing Workflow:**
    *   Modify the main execution script (`src/main.py` or similar) to read URLs from `data/new_profile_urls.json` instead of the original sitemap-derived list.
2.  **Execute Extraction:**
    *   Run the LangGraph pipeline on this new list of URLs.
    *   The pipeline should perform the same steps as the initial spike: fetch, preprocess, extract (Gemini Flash), validate (LLM Judge), and error handling.
    *   Ensure results, metrics (cost, tokens, latency), and errors are logged appropriately (e.g., using LangSmith and local log files).
3.  **Output:**
    *   Save the successfully extracted profiles to a new file, e.g., `output/newly_extracted_profiles.csv`.

*   **Definition of Done (Phase 2):** The extraction process completes for the URLs in `data/new_profile_urls.json`. `output/newly_extracted_profiles.csv` and associated logs/metrics are generated.

**Phase 3: Data Merging**

1.  **Load Data:**
    *   Use Pandas to load both `output/extracted_profiles.csv` (original) and `output/newly_extracted_profiles.csv` into DataFrames.
2.  **Combine and De-duplicate:**
    *   Concatenate the two DataFrames.
    *   Perform a final de-duplication step based on the `source_url` column to ensure integrity.
3.  **Output:**
    *   Overwrite the original `output/extracted_profiles.csv` with the merged and de-duplicated DataFrame.

*   **Definition of Done (Phase 3):** `output/extracted_profiles.csv` contains the combined, unique profile data from both the initial and the new extraction runs.

**Risk Assessment & Mitigation:**

1.  **Risk:** **Inconsistent Group Page Structures.** Identifying profile links reliably across diverse group page layouts is challenging.
    *   **Mitigation:** Start by analyzing a sample of group pages to find common HTML structures or URL patterns for profile links. Develop flexible parsing logic. Consider using heuristics (e.g., link text often contains a person's name) or even a small LLM call for link classification if simple pattern matching fails. Budget time for potential script adjustments after initial runs.
2.  **Risk:** **URL Discovery Accuracy.** The script might miss valid profile URLs (false negatives) or include incorrect links (false positives).
    *   **Mitigation:** Refine filtering logic based on observed patterns (e.g., exclude URLs ending in `.pdf`, `.docx`). Manually review a subset of the discovered URLs (`data/new_profile_urls.json`) before running the full extraction phase to catch obvious errors.
3.  **Risk:** **Scalability/Performance.** Crawling dozens of group pages and potentially hundreds/thousands of new profiles will take time, primarily due to ethical delays.
    *   **Mitigation:** Use asynchronous programming (`asyncio` with `httpx`) for fetching pages concurrently while still respecting per-request delays. Provide realistic time estimates for completion. Ensure the process is resumable (checkpointing).
4.  **Risk:** **Rate Limiting/Blocking.** Increased crawling activity might trigger website defenses.
    *   **Mitigation:** Maintain conservative delays between requests (1-2 seconds). Implement retry logic with exponential backoff for transient errors (e.g., HTTP 429, 503). Monitor error logs closely during the crawl.
5.  **Risk:** **Outdated Existing Data.** The profiles in the original `extracted_profiles.csv` are static snapshots. This plan only adds *new* profiles, it doesn't update existing ones.
    *   **Mitigation:** Acknowledge this limitation. Schedule a separate task for periodic full refreshes of *all* known profile URLs if keeping data current is a requirement.