import time
import requests
import traceback
from typing import Optional
from bs4 import BeautifulSoup
import json

# Import the GraphState TypedDict
from .state import GraphState

# Import configuration
from . import config

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.exceptions import (
    OutputParserException,
)  # Handles parsing issues with structured output
from pydantic import ValidationError  # Handles Pydantic validation issues
from google.api_core import exceptions as google_exceptions  # For Google API errors

# Import schemas
from .schemas import ProfileData, ValidationResult, ValidationStatus

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
        print(f"Sleeping for {config.REQUEST_DELAY_SECONDS} seconds...")
        time.sleep(config.REQUEST_DELAY_SECONDS)

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
    extracted_profile: Optional[ProfileData] = None
    error_message = None
    error_details_dict = None

    # --- Input Validation ---
    if state.get("error"):  # Check for errors from previous nodes
        print("Skipping extraction due to previous error.")
        return state

    preprocessed_content = state.get("preprocessed_content")
    if not preprocessed_content:
        error_message = "No preprocessed content found to extract data from."
        print(f"Error: {error_message}")
        updated_state: GraphState = {
            **state,  # type: ignore
            "metrics": metrics,
            "error": error_message,
            "error_details": {"message": error_message},
        }
        return updated_state

    extract_start_time = time.time()
    input_tokens = 0
    output_tokens = 0
    cost = 0.0

    try:
        # --- LLM and Prompt Setup ---
        llm = ChatGoogleGenerativeAI(
            model=config.MODEL_NAME,
            temperature=config.LLM_TEMPERATURE,
            google_api_key=config.GOOGLE_API_KEY,
        )

        # Use structured output with our Pydantic model
        structured_llm = llm.with_structured_output(ProfileData)

        # Define the prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert assistant tasked with extracting faculty profile information from web page text. "
                    "Extract the requested information accurately based *only* on the provided text. "
                    "Output the data in the requested structured format. Do not guess or hallucinate information not present.",
                ),
                (
                    "human",
                    "Please extract the faculty profile details from the following text content:\n\n---\n{page_content}\n---",
                ),
            ]
        )

        # Create the extraction chain
        chain = prompt | structured_llm

        print("Invoking LLM for data extraction...")
        # --- Invocation and Metadata Handling ---
        result = chain.invoke({"page_content": preprocessed_content})

        if isinstance(result, ProfileData):
            extracted_profile = result
            # AI Engineer Note: Accessing token usage. Structure may vary slightly based on Langchain version.
            # Check the actual result object's structure during testing if this fails.
            # Often it's in response_metadata or result.lc_run_info.run_id -> get run -> usage_metadata
            # Simplified access assuming direct metadata:
            usage_metadata = getattr(result, "response_metadata", {}).get(
                "usage_metadata", {}
            )
            input_tokens = usage_metadata.get("prompt_token_count", 0)
            output_tokens = usage_metadata.get(
                "candidates_token_count", 0
            )  # Gemini often uses this field
            total_tokens = usage_metadata.get(
                "total_token_count", input_tokens + output_tokens
            )

            if input_tokens > 0 or output_tokens > 0:
                cost = calculate_cost(input_tokens, output_tokens)
                print(
                    f"Extraction successful. Tokens - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}. Estimated Cost: ${cost:.6f}"
                )
            else:
                print(
                    "Extraction successful, but could not retrieve token usage metadata."
                )
                # Maybe try getting it from LangSmith if integrated

            # Add source_url to the extracted data
            extracted_profile.source_url = state["url"]

        else:
            # Should not happen with with_structured_output if successful, but good to check
            error_message = "LLM did not return a valid ProfileData object."
            error_details_dict = {"message": error_message, "llm_output": str(result)}
            print(f"Error: {error_message}")

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
    except (OutputParserException, ValidationError) as e:
        error_message = "LLM output failed validation/parsing"
        # Attempt to include the problematic LLM output if possible (might be in exception details)
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

    # --- Update State --- #
    updated_state: GraphState = {
        **state,  # type: ignore
        "extracted_data": extracted_profile,  # Will be None if extraction failed
        "metrics": metrics,
        "error": state.get("error") or error_message,
        "error_details": state.get("error_details") or error_details_dict,
    }
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

    try:
        # --- Judge LLM and Prompt Setup ---
        judge_llm = ChatGoogleGenerativeAI(
            model=config.JUDGE_MODEL_NAME,
            temperature=config.JUDGE_TEMPERATURE,
            google_api_key=config.GOOGLE_API_KEY,
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
                    f"You are an impartial evaluator assessing the accuracy of extracted information based *only* on the provided source text. "
                    f"Compare the fields in the 'Extracted Data' JSON object against the 'Source Text'. "
                    f"For each field in the {ValidationResult.__name__} schema (except overall_comment), determine its status: "
                    f"- '{ValidationStatus.CORRECT}': The extracted value is present and accurate in the Source Text.\\n"
                    f"- '{ValidationStatus.INCORRECT}': The extracted value is present but inaccurate compared to the Source Text, or it was hallucinated (not found in Source Text).\\n"
                    f"- '{ValidationStatus.MISSING}': The information exists in the Source Text, but it was *not* extracted (the corresponding field in Extracted Data is missing/null or incorrect value type).\\n"
                    f"- '{ValidationStatus.NOT_APPLICABLE}': The field is inherently not applicable for validation (e.g., source_url was input, not extracted).\\n"
                    f"Output your evaluation precisely matching the {ValidationResult.__name__} schema.",
                ),
                (
                    "human",
                    "Source Text:\\n---\\n{page_content}\\n---\\n\\nExtracted Data:\\n---\\n{extracted_json}\\n---\n\\nPlease evaluate the Extracted Data based on the Source Text and provide the results in the required format.",
                ),
            ]
        )

        # Create the validation chain
        judge_chain = judge_prompt | judge_structured_llm

        print("Invoking LLM Judge for validation...")
        # --- Invocation and Metadata Handling ---
        result = judge_chain.invoke(
            {"page_content": preprocessed_content, "extracted_json": extracted_data_str}
        )

        if isinstance(result, ValidationResult):
            validation_result = result
            # AI Engineer Note: Accessing token usage - assuming similar structure to extraction node.
            usage_metadata = getattr(result, "response_metadata", {}).get(
                "usage_metadata", {}
            )
            judge_input_tokens = usage_metadata.get("prompt_token_count", 0)
            judge_output_tokens = usage_metadata.get("candidates_token_count", 0)
            total_tokens = usage_metadata.get(
                "total_token_count", judge_input_tokens + judge_output_tokens
            )

            if judge_input_tokens > 0 or judge_output_tokens > 0:
                judge_cost = calculate_cost(
                    judge_input_tokens, judge_output_tokens
                )  # Reuse cost function
                print(
                    f"Validation successful. Judge Tokens - Input: {judge_input_tokens}, Output: {judge_output_tokens}, Total: {total_tokens}. Estimated Cost: ${judge_cost:.6f}"
                )
            else:
                print(
                    "Validation successful, but could not retrieve judge token usage metadata."
                )

        else:
            error_message = "LLM Judge did not return a valid ValidationResult object."
            error_details_dict = {"message": error_message, "llm_output": str(result)}
            print(f"Error: {error_message}")

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
    except (OutputParserException, ValidationError) as e:
        error_message = "LLM Judge output failed validation/parsing"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")
    except Exception as e:
        error_message = "An unexpected error occurred during data validation"
        error_details_dict = {
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"Error: {error_message} - {e}")

    finally:
        validate_end_time = time.time()
        metrics["validation_time_ms"] = (validate_end_time - validate_start_time) * 1000
        metrics["judge_input_tokens"] = judge_input_tokens
        metrics["judge_output_tokens"] = judge_output_tokens
        metrics["cost_per_profile_validation"] = (
            judge_cost  # Store validation cost separately
        )
        print(f"Validation took {metrics['validation_time_ms']:.2f} ms")

    # --- Update State --- #
    updated_state: GraphState = {
        **state,  # type: ignore
        "validation_result": validation_result,  # Will be None if validation skipped or failed
        "metrics": metrics,
        # Preserve previous errors, but allow validation errors to be surfaced if they occur
        "error": state.get("error") or error_message,
        "error_details": state.get("error_details") or error_details_dict,
    }
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
