from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, END

# Import the Pydantic models from schemas.py
# Use a relative import assuming graph.py is in the same directory level as schemas.py
from .schemas import ProfileData, ValidationResult

# --- Import Node Functions ---
# Import the actual node implementations from nodes.py
from .nodes import (
    fetch_html,
    preprocess_content,
    extract_data,
    validate_data,
    handle_error,
)

# --- Graph State Definition ---
class GraphState(TypedDict):
    """Represents the state passed between nodes in the LangGraph.

    Attributes:
        url: The URL of the profile page being processed.
        html_content: Raw HTML content fetched from the URL.
        preprocessed_content: Cleaned/processed text or HTML snippet ready for the LLM.
        extracted_data: Data extracted by the LLM, conforming to ProfileData schema.
        validation_result: Validation results from the LLM judge, conforming to ValidationResult schema.
        metrics: Dictionary to store performance and cost metrics.
        error: A string describing the latest error encountered, if any.
        error_details: A dictionary holding more detailed error information (e.g., exception details).
    """
    url: str
    html_content: Optional[str]
    preprocessed_content: Optional[str]
    extracted_data: Optional[ProfileData]  # Will be populated by extract_data node
    validation_result: Optional[
        ValidationResult
    ]  # Will be populated by validate_data node
    metrics: Dict[str, Any]
    error: Optional[str]
    error_details: Optional[Dict[str, Any]]


# --- Conditional Edge Logic ---
# Functions that determine the next step based on the current state.


def should_preprocess(state: GraphState) -> str:
    """Determines the next step after fetching HTML."""
    if state.get("error"):
        return "handle_error"
    if state.get("html_content"):
        return "preprocess_content"
    else:
        # This case should ideally be caught by fetch_html setting an error,
        # but provides a fallback.
        print("Warning: HTML content missing after fetch step without explicit error.")
        # state["error"] = "HTML content is missing after fetch step." # Let handle_error log based on fetch state
        return "handle_error"  # Or perhaps a specific "missing_content_error" node if needed


def should_extract(state: GraphState) -> str:
    """Determines the next step after preprocessing."""
    if state.get("error"):
        return "handle_error"
    # Allow extraction even if preprocessed_content is empty/None,
    # let the extraction node handle potentially empty input gracefully.
    return "extract_data"
    # else: # Original logic might prevent processing empty pages
    #     state["error"] = "Preprocessing failed to produce content."
    #     return "handle_error"


def should_validate(state: GraphState) -> str:
    """Determines the next step after data extraction."""
    if state.get(
        "error"
    ):  # Check if extraction itself failed (API error, validation error)
        return "handle_error"
    if (
        state.get("extracted_data") is not None
    ):  # Check if data was successfully extracted (even if empty fields)
        return "validate_data"
    else:
        # This likely means extraction failed and set an error, which should be caught above.
        # If no error was set but data is None, it indicates an issue.
        print(
            "Warning: Extracted data is None after extraction step without explicit error."
        )
        state["error"] = "Extraction resulted in None data without explicit error."
        return "handle_error"


def decide_after_validation(state: GraphState) -> str:
    """Determines the final step after validation."""
    if state.get("error"):  # Check if validation itself failed
        return "handle_error"

    validation = state.get("validation_result")
    # Proceed to END regardless of validation outcome; the result is stored in the state.
    # Downstream processes can check `validation_result`.
    # if validation and validation.get("is_valid"):
    #     return END
    # else:
    #     print("--- Validation Failed or Missing - Ending ---")
    #     # We store the result, no need to set GraphState error here unless validation node failed.
    #     return END
    return END


# --- Graph Workflow ---
workflow = StateGraph(GraphState)

# Add nodes using the imported functions
workflow.add_node("fetch_html", fetch_html)
workflow.add_node("preprocess_content", preprocess_content)
workflow.add_node("extract_data", extract_data)
workflow.add_node("validate_data", validate_data)
workflow.add_node("handle_error", handle_error)  # Error handling node

# Set the entry point
workflow.set_entry_point("fetch_html")

# Define the edges and conditional routing
workflow.add_conditional_edges(
    "fetch_html",
    should_preprocess,
    {"preprocess_content": "preprocess_content", "handle_error": "handle_error"},
)

workflow.add_conditional_edges(
    "preprocess_content",
    should_extract,
    {
        "extract_data": "extract_data",
        "handle_error": "handle_error",  # Route errors during preprocessing
    },
)

workflow.add_conditional_edges(
    "extract_data",
    should_validate,
    {
        "validate_data": "validate_data",
        "handle_error": "handle_error",  # Route errors during extraction (API, validation)
    },
)

workflow.add_conditional_edges(
    "validate_data",
    decide_after_validation,  # Always goes to END after validation attempt
    {
        END: END,  # Successful validation ends
        "handle_error": "handle_error",  # Route errors during the validation call itself
    },
)

# Error handling node leads to the end
workflow.add_edge("handle_error", END)


# Compile the graph into a runnable LangChain object
app = workflow.compile()

print("Compiled LangGraph application ready.")
# --- End of src/graph.py ---
