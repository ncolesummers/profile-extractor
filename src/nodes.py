import time
import requests
import traceback
from typing import Optional
from bs4 import BeautifulSoup
import json
import uuid
import os

# Import the GraphState TypedDict
from .state import GraphState

# Import configuration
from .config import settings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.exceptions import (
    OutputParserException,
)  # Handles parsing issues with structured output
from pydantic import ValidationError  # Handles Pydantic validation issues
from google.api_core import exceptions as google_exceptions  # For Google API errors
from langchain.output_parsers import PydanticOutputParser
from .utils import dump_debug_info, count_tokens

# Import schemas
from .schemas import ProfileData, ValidationResult, ValidationStatus

# Import LangChain tracing components
from langchain.callbacks.tracers.langchain import wait_for_all_tracers

# Import LangSmith client for manual tracking if API key exists
if settings.LANGSMITH_API_KEY:
    from langsmith import Client, traceable

    langsmith_client = Client(api_key=settings.LANGSMITH_API_KEY)
else:
    langsmith_client = None

    # Define a no-op traceable if langsmith is not available
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f


# Placeholder for cost calculation (replace with actual Gemini pricing)
# Prices per 1 million tokens (Input, Output)
GEMINI_FLASH_PRICING = {"input": 0.35 / 1_000_000, "output": 0.70 / 1_000_000}


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculates the estimated cost based on token counts."""
    # AI Engineer Note: Ensure these prices match the specific model used (e.g., gemini-2.0-flash-latest)
    # Check Google Cloud documentation for the latest pricing.
    input_cost = input_tokens * GEMINI_FLASH_PRICING["input"]
    output_cost = output_tokens * GEMINI_FLASH_PRICING["output"]
    return input_cost + output_cost


def fetch_html(state: GraphState) -> GraphState:
    """Fetches the HTML content for the URL specified in the state.

    Args:
        state: The current graph state.

    Returns:
        The updated graph state with html_content, metrics, and potentially errors.
    """
    print(f"--- Node: fetch_html for URL: {state['url']} ---")
    url = state["url"]
    metrics = state.get("metrics", {})  # Ensure metrics dict exists
    fetch_start_time = time.time()
    html_content = None
    error_message = None
    error_details_dict = None

    try:
        # Respectful delay before making the request
        print(f"Sleeping for {settings.REQUEST_DELAY_SECONDS} seconds...")
        time.sleep(settings.REQUEST_DELAY_SECONDS)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Set a reasonable timeout (e.g., 30 seconds)
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        html_content = response.text
        print(f"Successfully fetched content (approx {len(html_content)} bytes).")

    except requests.exceptions.Timeout as e:
        error_message = "Request timed out"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message}")
    except requests.exceptions.RequestException as e:
        error_message = "Failed to fetch URL"
        # Add status code if available
        status_code = getattr(e.response, "status_code", None)
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "status_code": status_code,
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - Status: {status_code} - {e}")
    except Exception as e:  # Catch any other unexpected errors
        error_message = "An unexpected error occurred during fetch"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")

    finally:
        fetch_end_time = time.time()
        metrics["fetch_time_ms"] = (fetch_end_time - fetch_start_time) * 1000
        print(f"Fetch took {metrics['fetch_time_ms']:.2f} ms")

    # Update the state
    updated_state: GraphState = {
        **state,  # type: ignore # Spread previous state
        "html_content": html_content,
        "metrics": metrics,
        "error": error_message,
        "error_details": error_details_dict,
    }
    return updated_state


def preprocess_content(state: GraphState) -> GraphState:
    """Parses HTML, removes boilerplate, and extracts main text content.

    Args:
        state: The current graph state containing html_content.

    Returns:
        The updated graph state with preprocessed_content and metrics/errors.
    """
    print(f"--- Node: preprocess_content for URL: {state['url']} ---")
    metrics = state.get("metrics", {})
    preprocessed_content = None
    error_message = None
    error_details_dict = None

    # --- Input Validation ---
    if state.get("error"):  # Check for errors from previous nodes
        print("Skipping preprocessing due to previous error.")
        return state  # Pass through state if fetch failed

    html_content = state.get("html_content")
    if not html_content:
        error_message = "No HTML content found to preprocess."
        print(f"Error: {error_message}")
        updated_state: GraphState = {
            **state,  # type: ignore
            "metrics": metrics,
            "error": error_message,
            "error_details": {"message": error_message},
        }
        return updated_state

    preprocess_start_time = time.time()

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # --- Boilerplate Removal (Common Tags) ---
        tags_to_remove = ["script", "style", "header", "footer", "nav", "aside", "form"]
        for tag_name in tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        print(f"Removed common boilerplate tags: {tags_to_remove}")

        # --- Content Extraction Strategy ---
        # AI Engineer Note: Selector strategy needs refinement based on analyzing
        # actual UIdaho profile page structures. Start broad, then narrow down.
        content_container = None
        # Attempt 1: Common main content semantic tags
        potential_containers = [
            "main",
            "article",
            ".content",
            "#main",
            "#content",
        ]  # Add site-specific selectors here
        for selector in potential_containers:
            container = soup.select_one(selector)
            if container:
                content_container = container
                print(f"Found content container using selector: {selector}")
                break

        # Attempt 2 (Fallback): Use body if no specific container found
        if not content_container:
            content_container = soup.body
            if content_container:
                print(
                    "Warning: Could not find specific content container, falling back to <body>."
                )
            else:
                raise ValueError("Could not find <body> tag in HTML.")

        # ---  Extract Photo URL ---
        photo_url = None
        headshot_div = soup.select_one(".profile-container-headshot")
        if headshot_div:
            img_tag = headshot_div.find("img")
            if img_tag:
                photo_url = img_tag["src"]
                print(f"Successfully extracted photo URL: {photo_url}")
            else:
                print("No img tag found within .profile-container-headshot")
        else:
            print("No div with class 'profile-container-headshot' found.")

        # --- Extract Text --- #
        if content_container:
            preprocessed_content = content_container.get_text(separator=" ", strip=True)
            print(
                f"Successfully extracted text content (approx {len(preprocessed_content)} chars)."
            )
            # Optional: Add a check for minimum content length if needed
            if len(preprocessed_content) < 100:  # Example threshold
                print(
                    f"Warning: Preprocessed content is very short ({len(preprocessed_content)} chars)."
                )
        else:
            # This case should ideally not be reached due to fallback to body
            error_message = "Could not extract any content container."
            print(f"Error: {error_message}")

    except Exception as e:
        error_message = "An error occurred during HTML preprocessing"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")
        # Ensure preprocessed_content remains None if error occurs
        preprocessed_content = None

    finally:
        preprocess_end_time = time.time()
        metrics["preprocess_time_ms"] = (
            preprocess_end_time - preprocess_start_time
        ) * 1000
        print(f"Preprocessing took {metrics['preprocess_time_ms']:.2f} ms")

    # --- Update State --- #
    updated_state: GraphState = {
        **state,  # type: ignore
        "preprocessed_content": preprocessed_content,
        "metrics": metrics,
        # Preserve previous error if one occurred earlier in this node
        "error": state.get("error") or error_message,
        "error_details": state.get("error_details") or error_details_dict,
    }
    if photo_url:
        updated_state["extracted_data"] = {"photo_url": photo_url}
    return updated_state


def extract_data(state: GraphState) -> GraphState:
    """Extracts structured data from preprocessed content using an LLM.

    Args:
        state: The current graph state containing preprocessed_content.

    Returns:
        The updated graph state with extracted_data, metrics, and potentially errors.
    """
    print(f"--- Node: extract_data for URL: {state['url']} ---")
    metrics = state.get("metrics", {})
    extracted_profile = None
    error_message = None
    error_details_dict = None

    # --- Input Validation ---
    if state.get("error"):  # Check for errors from previous nodes
        print("Skipping extraction due to previous error.")
        return state  # Skip if an error occurred before

    preprocessed_content = state.get("preprocessed_content")
    if not preprocessed_content:
        print("No preprocessed content found. Using empty string instead.")
        preprocessed_content = ""  # Could continue with an empty string or set error

    # --- Extraction ---
    extract_start_time = time.time()
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cost = 0.0
    run_id = None

    try:
        # --- LLM Setup ---
        run_id = str(uuid.uuid4())

        # Get thread_id from state for LangSmith tracing
        thread_id = state.get("thread_id")

        # Create metadata with thread_id for tracing
        metadata = {
            "url": state["url"],
            "run_id": run_id,
            "operation": "extract_data",
            "thread_id": thread_id,  # Include thread_id in metadata
        }

        # Initialize LLM with metadata
        llm = ChatGoogleGenerativeAI(
            model=settings.MODEL_NAME,
            temperature=settings.LLM_TEMPERATURE,
            google_api_key=settings.GOOGLE_API_KEY,
            stream_usage=True,  # Enable usage metadata
            metadata=metadata,  # Add metadata for tracing
            tags=["extraction"],  # Add tags for better filtering in LangSmith
        )

        # Use structured output with our Pydantic model
        structured_llm = llm.with_structured_output(ProfileData)

        # Define the prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert assistant specializing in extracting information from university faculty and staff profile web pages. "
                    "Your task is to carefully read the provided text content, identify key details about the individual, and structure them according to the `ProfileData` JSON schema."
                    "\\n\\n**Instructions:**\\n"
                    "1.  **Source:** The input text originates from a single faculty or staff profile page.\\n"
                    "2.  **Accuracy:** Extract information *only* if it is explicitly present in the text. Do not infer, guess, or add information.\\n"
                    "3.  **Schema Adherence:** Your output MUST strictly conform to the `ProfileData` JSON schema. Ensure all required fields are present and correctly typed, even if the value is null or empty.\\n"
                    "4.  **Name Extraction:**\\n"
                    "    *   Identify the full name of the primary faculty/staff member mentioned.\\n"
                    "    *   Parse the name into `first_name`, `last_name`, and `middle_name` (if available). If no middle name is found, leave the `middle_name` field null or empty.\\n"
                    "5.  **Specific Fields:** Pay close attention to extracting:\\n"
                    "    *   `title`: The person's official job title(s).\\n"
                    "    *   `office`: Their physical office location.\\n"
                    "    *   `phone`: Primary contact phone number.\\n"
                    "    *   `email`: Primary contact email address.\\n"
                    "    *   `college_unit`, `department_division`: Their university affiliations.\\n"
                    "    *   `degrees`: List of academic degrees. For each degree, extract the type (e.g., 'Ph.D.', 'M.S.'), the awarding institution, and the year (if available). Structure this as a list of JSON objects, where each object has keys: `degree_type`, `institution`, and `year`. If no specific degrees are listed, provide null or an empty list.\\n"
                    "    *   `research_focus_areas`: List of research focus areas.\\n"
                    "6.  **Completeness:** Extract all available information for the defined schema fields. If a piece of information isn't in the text, the corresponding field should be null or empty as per the schema definition.",
                ),
                (
                    "human",
                    "Source URL: {source_url}\\n\\nProfile Content:\\n{content}",
                ),
            ]
        )

        # Create the extraction chain
        parser = PydanticOutputParser(pydantic_object=ProfileData)
        chain = prompt | llm  # Chain now outputs AIMessage

        print("Invoking LLM for data extraction...")
        # --- Invocation and Metadata Handling ---\
        ai_message = chain.invoke(
            {"content": preprocessed_content, "source_url": state["url"]}
        )

        # Ensure tracers have completed
        wait_for_all_tracers()

        # --- Extract Metadata ---\
        # AI Engineer Note: Accessing token usage from AIMessage.response_metadata
        usage_metadata = getattr(ai_message, "response_metadata", {}).get(
            "usage_metadata", {}
        )
        input_tokens = usage_metadata.get("prompt_token_count", 0)
        output_tokens = usage_metadata.get(
            "candidates_token_count", 0
        )  # Gemini often uses this field
        total_tokens = usage_metadata.get(
            "total_token_count", input_tokens + output_tokens
        )

        # Manually update token counts in LangSmith if we have the client
        try:
            if langsmith_client and input_tokens > 0 and run_id:
                latest_runs = langsmith_client.list_runs(
                    filter=f"tags.operation = extract_data AND metadata.thread_id = '{thread_id}'",
                    execution_order=-1,
                    limit=1,
                )
                for run in latest_runs:
                    # Update token usage for the run
                    feedback = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "thread_id": thread_id,  # Include thread_id in feedback
                    }
                    langsmith_client.create_feedback(
                        run.id,
                        "token_usage",
                        score=1.0,  # Not relevant for token usage
                        value=feedback,
                    )
                    print(f"Updated token usage in LangSmith for run: {run.id}")
        except Exception as e:
            print(f"Error updating LangSmith token usage: {e}")

        if input_tokens > 0 or output_tokens > 0:
            cost = calculate_cost(input_tokens, output_tokens)
            print(
                f"LLM call successful. Tokens - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}. Estimated Cost: ${cost:.6f}"
            )
        else:
            # This case might still happen if the API response structure changes or lacks metadata
            print("LLM call successful, but could not retrieve token usage metadata.")
            # Use fallback tokenizer to estimate token counts
            prompt_text = prompt.format(
                content=preprocessed_content, source_url=state["url"]
            )
            input_tokens = count_tokens(prompt_text)
            output_tokens = count_tokens(str(ai_message.content))
            total_tokens = input_tokens + output_tokens
            cost = calculate_cost(input_tokens, output_tokens)
            print(
                f"Estimated tokens using fallback tokenizer - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}"
            )

        # --- Parse the Output ---
        try:
            # NEW: Handle potential list wrapping from LLM
            raw_content = ai_message.content
            # Strip potential markdown code fences
            if raw_content.strip().startswith("```json"):
                raw_content = raw_content.strip()[7:-3].strip()
            elif raw_content.strip().startswith("```"):
                raw_content = raw_content.strip()[3:-3].strip()

            parsed_json = json.loads(raw_content)
            if isinstance(parsed_json, list) and len(parsed_json) == 1:
                target_obj = parsed_json[0]
                print("LLM returned a list, extracting first element.")
            elif isinstance(parsed_json, dict):
                target_obj = parsed_json
            else:
                raise ValueError(
                    "LLM output is not a JSON object or a list containing a single object."
                )

            # Ensure source_url is added to the target object
            target_obj["source_url"] = state["url"]

            # Preserve photo_url from preprocessing step if available
            existing_extracted_data = state.get("extracted_data", {})
            if (
                isinstance(existing_extracted_data, dict)
                and "photo_url" in existing_extracted_data
            ):
                target_obj["photo_url"] = existing_extracted_data["photo_url"]
                print(
                    f"Preserved photo URL from preprocessing: {existing_extracted_data['photo_url']}"
                )

            # More robust Pydantic parsing
            try:
                # First normalize numeric year values to strings
                if (
                    isinstance(target_obj, dict)
                    and "degrees" in target_obj
                    and isinstance(target_obj["degrees"], list)
                ):
                    for degree in target_obj["degrees"]:
                        if (
                            isinstance(degree, dict)
                            and "year" in degree
                            and degree["year"] is not None
                        ):
                            if isinstance(degree["year"], int):
                                degree["year"] = str(degree["year"])

                # Then try parsing using the parser
                extracted_profile = parser.parse(json.dumps(target_obj))
            except (OutputParserException, ValidationError) as e:
                # If that fails, try direct instantiation with model validation
                try:
                    extracted_profile = ProfileData(**target_obj)
                except ValidationError as ve:
                    # If direct instantiation also fails, provide more details and re-raise
                    print(f"ValidationError: {ve}")
                    print(f"Target object: {target_obj}")
                    raise

            print("Successfully parsed LLM output into ProfileData.")

        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            error_message = "Failed to decode LLM output as JSON"
            error_details_dict = {
                "exception_type": type(e).__name__,
                "message": str(e),
                "llm_content": ai_message.content,  # Include raw content
                "traceback": traceback.format_exc(),
            }
            print(f"Error: {error_message} - {e}")
            extracted_profile = None
        except (OutputParserException, ValidationError, ValueError) as e:
            # Handle parsing/validation errors
            error_message = "LLM output failed validation/parsing after successful call"
            error_details_dict = {
                "exception_type": type(e).__name__,
                "message": str(e),
                "llm_content": ai_message.content,  # Include raw content for debugging
                "traceback": traceback.format_exc(),
            }
            print(f"Error: {error_message} - {e}")
            extracted_profile = None

    except (
        google_exceptions.GoogleAPIError,
        requests.exceptions.RequestException,
    ) as e:
        error_message = f"LLM API request failed: {type(e).__name__}"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")
    except Exception as e:
        error_message = "An unexpected error occurred during data extraction"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")

    finally:
        extract_end_time = time.time()
        metrics["extraction_time_ms"] = (extract_end_time - extract_start_time) * 1000
        metrics["extraction_input_tokens"] = input_tokens
        metrics["extraction_output_tokens"] = output_tokens
        metrics["cost_per_profile_extraction"] = (
            cost  # Store extraction cost separately
        )
        print(f"Extraction took {metrics['extraction_time_ms']:.2f} ms")

    # --- Update State ---
    updated_state: GraphState = {
        **state,  # type: ignore
        "extracted_data": extracted_profile,  # Will be None if extraction failed
        "metrics": metrics,
        "error": state.get("error") or error_message,
        "error_details": state.get("error_details") or error_details_dict,
    }

    # Dump debug info if there was an error in extraction
    if error_message:
        debug_file = dump_debug_info(updated_state, debug_dir="logs/debug/extraction")
        print(f"Extraction debug info saved to {debug_file}")

    return updated_state


def validate_data(state: GraphState) -> GraphState:
    """Validates the extracted data against the preprocessed content using an LLM judge.

    Args:
        state: The current graph state containing preprocessed_content and extracted_data.

    Returns:
        The updated graph state with validation_result, metrics, and potentially errors.
    """
    print(f"--- Node: validate_data for URL: {state['url']} ---")
    metrics = state.get("metrics", {})
    validation_result: Optional[ValidationResult] = None
    error_message = None
    error_details_dict = None

    # --- Input Validation ---
    if state.get("error"):  # Check for errors from previous nodes
        print("Skipping validation due to previous error.")
        return state

    preprocessed_content = state.get("preprocessed_content")
    extracted_data = state.get("extracted_data")

    if not preprocessed_content:
        # Cannot validate without source text
        print("Skipping validation: No preprocessed content found.")
        # Don't set an error here, just proceed without validation result
        return state

    if not extracted_data:
        # Cannot validate if extraction failed
        print("Skipping validation: No extracted data found.")
        # Don't set an error here, just proceed without validation result
        return state

    validate_start_time = time.time()
    judge_input_tokens = 0
    judge_output_tokens = 0
    judge_cost = 0.0
    run_id = None

    try:
        # --- Judge LLM and Prompt Setup ---
        run_id = str(uuid.uuid4())

        # Get thread_id from state for LangSmith tracing
        thread_id = state.get("thread_id")

        metadata = {
            "url": state["url"],
            "run_id": run_id,
            "operation": "validate_data",
            "thread_id": thread_id,  # Include thread_id in metadata
        }

        judge_llm = ChatGoogleGenerativeAI(
            model=settings.JUDGE_MODEL_NAME,
            temperature=settings.JUDGE_TEMPERATURE,
            google_api_key=settings.GOOGLE_API_KEY,
            stream_usage=True,  # Enable usage metadata
            metadata=metadata,  # Add metadata for tracing
            tags=["validation"],  # Add tags for better filtering in LangSmith
        )

        # Use structured output with our ValidationResult schema
        judge_structured_llm = judge_llm.with_structured_output(ValidationResult)

        # Serialize the extracted data for the prompt
        # Use Pydantic's dict() method for clean serialization, exclude unset fields
        extracted_data_str = json.dumps(
            extracted_data.model_dump(exclude_unset=True), indent=2
        )

        # Define the judge prompt
        judge_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert assistant tasked with validating the accuracy of extracted faculty profile information. "
                    "Compare the extracted data against the source text and determine if each field is correct, missing, "
                    "or not applicable. Return your assessment in the requested structured format.\n\n"
                    "YOUR RESPONSE MUST BE A VALID JSON OBJECT WITH THE FOLLOWING STRUCTURE:\n"
                    "{{\n"
                    '  "photo_url_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "first_name_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "middle_name_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "last_name_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "title_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "office_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "phone_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "email_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "college_unit_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "department_division_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "degrees_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "research_focus_areas_status": "Correct", "Incorrect", "Missing", or "Not Applicable",\n'
                    '  "overall_comment": "Your overall assessment and reasoning"\n'
                    "}}\n"
                    "Do not nest, format differently, or add extra fields to this structure.",
                ),
                (
                    "human",
                    "Please validate the following extracted faculty profile data against the source text:"
                    "\n\nSOURCE TEXT:\n{source_text}\n\nEXTRACTED DATA:\n{extracted_data}\n\n"
                    "For each field, determine if the extraction is Correct, Incorrect, Missing, or Not Applicable.",
                ),
            ]
        )

        # Create the judgment chain
        judge_parser = PydanticOutputParser(pydantic_object=ValidationResult)
        judge_chain = judge_prompt | judge_llm  # LLM will output AIMessage

        print("Invoking LLM Judge for validation...")
        # --- Invocation and Metadata Handling ---
        judge_ai_message = judge_chain.invoke(
            {
                "source_text": preprocessed_content,
                "extracted_data": extracted_data_str,
            }
        )

        # --- Extract Metadata ---
        judge_usage_metadata = getattr(judge_ai_message, "response_metadata", {}).get(
            "usage_metadata", {}
        )
        judge_input_tokens = judge_usage_metadata.get("prompt_token_count", 0)
        judge_output_tokens = judge_usage_metadata.get("candidates_token_count", 0)
        judge_total_tokens = judge_usage_metadata.get(
            "total_token_count", judge_input_tokens + judge_output_tokens
        )

        # Manually update token counts in LangSmith if we have the client
        try:
            if langsmith_client and judge_input_tokens > 0 and run_id:
                latest_runs = langsmith_client.list_runs(
                    filter=f"tags.operation = validate_data AND metadata.thread_id = '{thread_id}'",
                    execution_order=-1,
                    limit=1,
                )
                for run in latest_runs:
                    # Update token usage for the run
                    feedback = {
                        "input_tokens": judge_input_tokens,
                        "output_tokens": judge_output_tokens,
                        "total_tokens": judge_total_tokens,
                        "thread_id": thread_id,  # Include thread_id in feedback
                    }
                    langsmith_client.create_feedback(
                        run.id,
                        "token_usage",
                        score=1.0,  # Not relevant for token usage
                        value=feedback,
                    )
                    print(f"Updated token usage in LangSmith for run: {run.id}")

                    # Add validation result as quality feedback
                    if validation_result and hasattr(
                        validation_result, "overall_status"
                    ):
                        # Map validation status to score (1.0 = correct, 0.0 = incorrect)
                        quality_score = (
                            1.0
                            if validation_result.overall_status
                            == ValidationStatus.CORRECT
                            else 0.0
                        )
                        langsmith_client.create_feedback(
                            run.id,
                            "validation_quality",
                            score=quality_score,
                            value={
                                "validation_result": validation_result.model_dump(),
                                "thread_id": thread_id,
                            },
                        )
                        print(f"Added validation quality feedback for run: {run.id}")
        except Exception as e:
            print(f"Error updating LangSmith validation feedback: {e}")

        if judge_input_tokens > 0 or judge_output_tokens > 0:
            judge_cost = calculate_cost(judge_input_tokens, judge_output_tokens)
            print(
                f"LLM Judge call successful. Tokens - Input: {judge_input_tokens}, Output: {judge_output_tokens}, "
                f"Total: {judge_total_tokens}. Estimated Cost: ${judge_cost:.6f}"
            )
        else:
            print(
                "LLM Judge call successful, but could not retrieve judge token usage metadata."
            )
            # Use fallback tokenizer to estimate token counts
            prompt_text = judge_prompt.format(
                source_text=preprocessed_content, extracted_data=extracted_data_str
            )
            judge_input_tokens = count_tokens(prompt_text)
            judge_output_tokens = count_tokens(str(judge_ai_message.content))
            judge_total_tokens = judge_input_tokens + judge_output_tokens
            judge_cost = calculate_cost(judge_input_tokens, judge_output_tokens)
            print(
                f"Estimated judge tokens using fallback tokenizer - Input: {judge_input_tokens}, Output: {judge_output_tokens}, Total: {judge_total_tokens}"
            )

        # --- Parse the Output ---
        try:
            # Extract the raw content from the LLM response
            raw_content = judge_ai_message.content
            # Strip potential markdown code fences
            if raw_content.strip().startswith("```json"):
                raw_content = raw_content.strip()[7:-3].strip()
            elif raw_content.strip().startswith("```"):
                raw_content = raw_content.strip()[3:-3].strip()

            # Enhanced parsing logic with more robust error handling
            try:
                # First attempt: direct JSON parsing
                response_json = json.loads(raw_content)
            except json.JSONDecodeError:
                # Second attempt: try to extract JSON from text that might contain explanations
                import re

                json_pattern = r"\{[\s\S]*\}"
                json_match = re.search(json_pattern, raw_content)
                if json_match:
                    try:
                        response_json = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        # If still failing, raise the original error
                        raise
                else:
                    # If no JSON-like pattern found, raise
                    raise ValueError("Could not find JSON object in LLM response")

            # Create a dictionary with default values for all required fields
            validation_values = {
                "photo_url_status": "Not Applicable",
                "first_name_status": "Not Applicable",
                "middle_name_status": "Not Applicable",
                "last_name_status": "Not Applicable",
                "title_status": "Not Applicable",
                "office_status": "Not Applicable",
                "phone_status": "Not Applicable",
                "email_status": "Not Applicable",
                "college_unit_status": "Not Applicable",
                "department_division_status": "Not Applicable",
                "degrees_status": "Not Applicable",
                "research_focus_areas_status": "Not Applicable",
                "overall_comment": "Validation performed with limited information.",
            }

            # Attempt to map the LLM output to our expected fields
            if "overall_comment" in response_json:
                validation_values["overall_comment"] = response_json["overall_comment"]

            # Mapping of possible field names to our schema names
            field_mappings = {
                "photo_url": "photo_url_status",
                "first_name": "first_name_status",
                "middle_name": "middle_name_status",
                "last_name": "last_name_status",
                "title": "title_status",
                "office": "office_status",
                "phone": "phone_status",
                "email": "email_status",
                "college_unit": "college_unit_status",
                "department_division": "department_division_status",
                "degrees": "degrees_status",
                "research_focus_areas": "research_focus_areas_status",
            }

            # Try to extract status information from the response
            for field, status_field in field_mappings.items():
                if field in response_json and "status" in response_json[field]:
                    validation_values[status_field] = response_json[field]["status"]
                elif field + "_status" in response_json:
                    validation_values[status_field] = response_json[field + "_status"]

            # Create the ValidationResult manually
            validation_result = ValidationResult(**validation_values)
            print("Successfully parsed LLM Judge output into ValidationResult.")

        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            error_message = "Failed to decode LLM Judge output as JSON"
            error_details_dict = {
                "exception_type": type(e).__name__,
                "message": str(e),
                "llm_content": judge_ai_message.content,  # Include raw content
                "traceback": traceback.format_exc(),
            }
            print(f"Error: {error_message} - {e}")
            validation_result = None
        except (OutputParserException, ValidationError, ValueError) as e:
            # Handle parsing/validation errors
            error_message = (
                "LLM Judge output failed validation/parsing after successful call"
            )
            error_details_dict = {
                "exception_type": type(e).__name__,
                "message": str(e),
                "llm_content": judge_ai_message.content,  # Include raw content for debugging
                "traceback": traceback.format_exc(),
            }
            print(f"Error: {error_message} - {e}")
            validation_result = None

    except (
        google_exceptions.GoogleAPIError,
        requests.exceptions.RequestException,
    ) as e:
        error_message = f"LLM Judge API request failed: {type(e).__name__}"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")
    except Exception as e:
        error_message = "An unexpected error occurred during validation"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")

    finally:
        validate_end_time = time.time()
        metrics["validation_time_ms"] = (validate_end_time - validate_start_time) * 1000
        metrics["validation_input_tokens"] = judge_input_tokens
        metrics["validation_output_tokens"] = judge_output_tokens
        metrics["cost_per_profile_validation"] = judge_cost
        print(f"Validation took {metrics['validation_time_ms']:.2f} ms")

    # --- Update State --- #
    updated_state: GraphState = {
        **state,  # type: ignore
        "validation_result": validation_result,
        "metrics": metrics,
        "error": state.get("error") or error_message,
        "error_details": state.get("error_details") or error_details_dict,
    }

    # Dump debug info if there was an error in validation
    if error_message:
        debug_file = dump_debug_info(updated_state, debug_dir="logs/debug/validation")
        print(f"Validation debug info saved to {debug_file}")

    return updated_state


def handle_error(state: GraphState) -> GraphState:
    """Handles and logs errors captured in the graph state.

    This is typically a terminal node reached when a previous node sets an error.

    Args:
        state: The current graph state, expected to contain error information.

    Returns:
        The original state (or potentially a modified state if specific error
        handling logic were added, e.g., marking for retry).
    """
    error = state.get("error")
    error_details = state.get("error_details")
    url = state.get("url", "Unknown URL")  # Get URL for context

    print(f"--- Node: handle_error for URL: {url} ---")
    if error:
        print(f"ERROR encountered for {url}:")
        print(f"  Message: {error}")
        if error_details:
            print(
                f"  Details: {json.dumps(error_details, indent=2)}"
            )  # Pretty print details
        else:
            print("  No further details provided.")
    else:
        # This node should ideally only be reached if an error is set,
        # but log a warning if called unexpectedly.
        print(
            f"Warning: handle_error node reached for {url} without an error being set in the state."
        )

    # This node typically doesn't modify the state further, just logs.
    # It acts as an endpoint for error paths in the graph.
    return state


# --- Other node functions will go below here --- #
