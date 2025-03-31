# Foundation Model Data Extraction Spike

## Overview

This spike explores the feasibility of creating the Person profile import dataset for the University of Idaho website using foundation models instead of relying on a poorly documented legacy database. The goal is to extract key fields (Name, Title, Email, Degrees, etc., as defined in `src/schemas.py:ProfileData`) from profile pages identified on `uidaho.edu`.

### Approach

1.  **Identify Profiles:** Start with a list of known profile URLs stored in `data/uidaho_urls.json`.
2.  **Crawl & Extract Subset:** Process a subset of these URLs to test the workflow. The core logic uses a [LangGraph](https://python.langchain.com/docs/langgraph/) state machine (`src/graph.py`, `src/nodes.py`) with the following key steps:
    *   `fetch_page`: Retrieves HTML content respectfully (using configured delays).
    *   `preprocess_html`: Parses and cleans HTML using BeautifulSoup to isolate relevant content, attempting to handle variations.
    *   `extract_data`: Uses a foundation model (initially Gemini Flash, configurable in `src/config.py`) via LangChain to extract information into the `src/schemas.py:ProfileData` Pydantic schema.
    *   `validate_data`: Employs an LLM-as-a-judge pattern (separate model call) to evaluate the accuracy of the extracted fields against the preprocessed content, outputting results according to the `src/schemas.py:ValidationResult` schema.
    *   `handle_error`: Captures and logs errors at each step.
3.  **Evaluate:** Analyze the results based on accuracy (using the LLM judge and potentially manual review), cost, and processing time. LangSmith is used for detailed tracing and debugging (`scripts/view_threads.py` can be used for analysis).

If initial results with Gemini Flash are insufficient for complex pages, alternative models like Claude 3.5 Sonnet or GPT-4o will be evaluated.

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
*   **Utilities:** Tabulate (for `view_threads.py`)
*   **Linting/Formatting:** Ruff

#### Metrics

The evaluation focuses on the following metrics, collected during the spike run and aggregated in `src/reporting.py`:

*   **Accuracy:**
    *   **LLM Judge:** Field-level correctness (`Correct`, `Incorrect`, `Missing`) reported by the `validate_data` node (results in LangSmith traces).
    *   **Manual Review:** Comparison against a small, manually verified "golden set" of profiles (if created).
    *   **Completeness:** Percentage of target fields successfully extracted per profile.
*   **Cost:**
    *   **Token Usage:** Input, Output, and Total tokens tracked per LLM call (extraction and validation), aggregated per profile and overall (available via LangSmith).
    *   **Estimated Cost:** Calculated based on token usage and model pricing (e.g., Gemini Flash pricing). Reported per profile and overall.
*   **Performance:**
    *   **Latency:** Total execution time for the batch, average processing time per profile. Node-level latency available via LangSmith.
*   **Operational:**
    *   **Success Rate:** Percentage of URLs processed without fatal errors.
    *   **Error Analysis:** Categorization of errors (fetch errors, parsing errors, extraction errors, validation errors) recorded in `output/errors_extracted_profiles.xlsx`.

## Results

*Based on processing the sample set (`output/sample_of_100/`)*

### Cost

*   **Summary:** The average estimated cost per profile using Gemini Flash was [$X.XX]. Total cost for the sample was [$Y.YY].
*   **Details:** Average input/output tokens per profile for extraction were [A]/[B], and for validation were [C]/[D]. See LangSmith traces for detailed breakdowns.

### Accuracy

*   **LLM Judge:** The validation node reported an average field-level correctness of [Z]% across the processed profiles. Fields like [Field Name] were consistently accurate, while [Field Name] proved more challenging.
*   **Manual Review:** (If performed) Manual spot-checking of [N] profiles confirmed [details about accuracy, common errors, comparison to LLM judge].
*   **Output:** Successfully extracted data is available in `output/sample_of_100/extracted_profiles.xlsx`. Errors and profiles that failed processing are in `output/sample_of_100/extracted_profiles_errors.xlsx`.

### Time

*   **Summary:** Processing the [Number] profiles in the sample took [Total Time].
*   **Details:** The average processing time per profile was [Average Time] seconds. The [Step Name, e.g., extraction] step was the main bottleneck.

### Known Issues

*   **Sitemap 404s:** The `uidaho.edu` sitemap contains URLs that return 404 errors, indicating it's outdated. Relying solely on the sitemap for comprehensive coverage is not viable.
*   **HTML Variability:** Significant variations exist in the HTML structure across different faculty profile pages (e.g., different class names, layouts). The `preprocess_html` step needs to be robust or adaptable.
*   **Extraction Challenges:** Specific fields like [e.g., degrees, research areas] were harder to extract consistently due to varied formatting or ambiguity.
*   **LLM Judge Limitations:** The LLM judge occasionally [e.g., misinterprets instructions, hallucinates details not present, disagrees with manual review].

## Recommendations

*   **Feasibility:** The foundation model approach appears [Feasible/Promising/Challenging] for extracting the required profile data.
*   **Model Choice:** Gemini Flash provided [Acceptable/Unacceptable] accuracy at a low cost. For profiles where it struggled, [Consider/Recommend] evaluating [GPT-4o/Claude 3.5 Sonnet] despite higher costs.
*   **Process Improvements:**
    *   Refine the `preprocess_html` logic to better handle observed HTML variations.
    *   Improve extraction prompts, particularly for challenging fields like [Field Name]. Provide more few-shot examples or clearer instructions.
    *   Enhance error handling to capture more specific failure modes.
    *   Investigate alternative methods for identifying profile URLs beyond the unreliable sitemap (e.g., targeted crawling from department pages).
    *   Split the nodes into their own files and modules.
    *   Move the prompts into the config file.
*   **LLM Judge:** Use the LLM judge results as a guide but supplement with targeted manual review, especially for critical fields or profiles flagged with low confidence.

## Next Steps

1.  **Refine Prompts & Preprocessing:** Implement improvements based on the analysis of extraction errors and challenging fields.
2.  **Evaluate Alternative Models:** (If necessary) Run a comparative test on a subset of difficult profiles using GPT-4o or Claude 3.5 Sonnet.
3.  **Expand URL List:** Develop a more reliable strategy for identifying profile URLs.
4.  **Scale Testing:** Process a larger, more representative set of profiles (e.g., 25-50) to validate performance and cost at scale.
5.  **Develop Golden Set:** Create a manually verified golden dataset for more rigorous accuracy evaluation.
6.  **Integrate Feedback:** Incorporate feedback from stakeholders on the extracted data format and content.
7.  **Documentation:** Update `README.md` and other documentation with final findings and procedures.
