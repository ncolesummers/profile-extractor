# Person Profile Data Extraction Spike

## Overview

This spike explores the feasibility of creating the Person profile import dataset for the University of Idaho website using foundation models instead of relying on a poorly documented legacy database. The goal is to extract key fields (Name, Title, Email, Degrees, etc., as defined in the [User Story](https://dev.azure.com/uidaho/Development/_sprints/taskboard/Development%20Team/Development/Sprint%2025.04)) from profile pages identified on `uidaho.edu`.

### Approach

1.  **Identify Profiles:** Start with a list of known profile URLs stored in `data/uidaho_urls.json`. I generated this list by analyzing the website's sitemap.xml file to identify faculty and staff profile pages.
2.  **Crawl & Extract Subset:** Process a subset of these URLs to test the workflow. The core logic uses a [LangGraph](https://python.langchain.com/docs/langgraph/) state machine with the following key steps:
    *   `fetch_page`: Retrieves HTML content respectfully (using configured delays to ensure ethical crawling).
    *   `preprocess_html`: Parses and cleans HTML using BeautifulSoup to isolate relevant content, attempting to handle variations.
    *   `extract_data`: Uses a foundation model (initially Gemini Flash, configurable in the config) to extract information into the `ProfileData` Pydantic schema.
    *   `validate_data`: Employs an LLM-as-a-judge pattern (separate model call) to evaluate the accuracy of the extracted fields against the preprocessed content, outputting results according to the `ValidationResult` schema.
    *   `handle_error`: Captures and logs errors at each step.
3.  **Evaluate:** Analyze the results based on accuracy (using the LLM judge and potentially manual review), cost, and processing time. I used LangSmith for detailed tracing and debugging.

We could use alternative models if results from Gemini Flash prove insufficient for complex pages.

#### Technology

*   **IDE:** Cursor AI
*   **Models:** Google Gemini Flash (initial), Gemini Pro (dev/research), potentially others (Claude 3.5 Sonnet, GPT-4o)
*   **Orchestration:** LangGraph
*   **LLM Framework:** LangChain (including `langchain-google-genai`)
*   **Monitoring:** LangSmith
*   **Environment/Packaging:** UV
*   **Data Validation:** Pydantic
*   **Token Counting:** TikToken (via LangSmith/LangChain callbacks)
*   **Web Interaction:** Requests, HTTPX
*   **HTML Parsing:** BeautifulSoup4
*   **Data Handling:** Pandas, Openpyxl
*   **Configuration:** python-dotenv
*   **Utilities:** Tabulate (for viewing threads)
*   **Linting/Formatting:** Ruff

#### Metrics

The evaluation focuses on the following metrics collected during the spike run and aggregated in the reporting:

*   **Accuracy:**
    *   **LLM Judge:** Field-level correctness (`Correct`, `Incorrect`, `Missing`) reported by the `validate_data` node (results in LangSmith traces).
*   **Cost:**
    *   **Token Usage:** Input, Output, and Total tokens tracked per LLM call (extraction and validation), aggregated per profile and overall (available via LangSmith).
    *   **Estimated Cost:** Calculated based on token usage and model pricing (e.g., Gemini Flash pricing). Reported per profile and overall.
*   **Performance:**
    *   **Latency:** Total execution time for the batch, average processing time per profile. Node-level latency is available via LangSmith.
    *   **Note on Crawl Time:** Most processing time is due to intentional delays between requests to ensure ethical and gentle crawling of the university website. This approach prevents overloading the web servers and follows good web citizenship practices.
*   **Operational:**
    *   **Success Rate:** Percentage of URLs processed without fatal errors.
    *   **Error Analysis:** Categorization of errors (fetch, parsing, extraction, and validation errors) recorded in the error log.

## Results

*Based on processing the entire dataset of 901 URLs on March 30, 2025*

### Cost

* **Summary:** The average estimated Gemini Flash cost per profile was $0.0012, and the total estimated cost was $1.0254. I won't have the actual cost until Google Cloud charges me, but it's close.
* **Details:** Average tokens per successful profile was 3,132, with 2,618,463 tokens used across all profiles.

### Accuracy

* **Success Rate:** 92.79% (836 successful extractions out of 901 URLs)
* **Error Analysis:** Of the 65 failed extractions, 64 (98.5%) were due to HTTP 404 errors, indicating the URLs from the sitemap no longer exist on the website. Only one failure was related to actual extraction issues (a page with multiple faculty profiles that didn't match the expected schema).
* **Output:** Successfully extracted data is available in the output folder. Errors and profiles that failed processing are in a separate error log.

### Time

* **Summary:** Processing the 901 profiles in the dataset took 1h 32m 27s.
* **Details:** The average processing time per profile was 6.6 seconds (6596.34 ms). Total processing time (sum of all steps) was 1h 31m 54s. Most of this time is due to ethical crawling delays rather than actual processing limitations.

### Known Issues

* **Sitemap 404s:** The `uidaho.edu` sitemap contains URLs that return 404 errors, indicating it's outdated. Relying solely on the sitemap for comprehensive coverage is not viable. These 404s were the primary source of errors in this feasibility test, not the foundation model itself.
* **HTML Variability:** The HTML structure of different faculty profile pages varies (e.g., different class names, layouts). The `preprocess_html` step handled these variations well.
* **Multiple Profiles Page:** One failure occurred on a page listing multiple faculty profiles (`/people/adjuncts`), which didn't conform to the single-profile schema our extraction currently supports.

## Recommendations

* **Feasibility:** The foundation model approach has proven highly feasible for extracting the required profile data, with a 92.79% success rate.
* **Model Choice:** Gemini Flash provided excellent accuracy at a low cost ($0.0012 per profile). Based on these results, evaluating more expensive models like Claude 3.7 Sonnet or GPT-4o is unnecessary.
* **Process Improvements:**
    * Develop a more reliable strategy for identifying profile URLs beyond the outdated sitemap.
    * Consider a special handler for pages with multiple profiles (like `/people/adjuncts`).
    * Split the nodes into files.
    * Move the prompts into the config file.
* **Data Considerations:** Because the profiles are all on the public website and data isn't sensitive, this was an excellent feasibility test for foundation models. The non-sensitive nature of the data made it ideal for this approach.

## Next Steps

1. **Refine URL Discovery:** Develop a more reliable strategy for identifying profile URLs beyond the outdated sitemap.
2. **Support Multiple Profiles:** Add support for pages containing multiple profiles.
3. **Documentation:** Update documentation with final findings and procedures.
4. **Continue Processing:** Rerun the process as needed to ensure we extract future changes to the profile pages.
5. **Code Refactoring:** Split the nodes into files and move prompts to the config file.