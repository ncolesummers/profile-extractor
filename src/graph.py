from typing import TypedDict, Optional, Dict, Any, List

# Import the Pydantic models from schemas.py
# Use a relative import assuming graph.py is in the same directory level as schemas.py
from .schemas import ProfileData, ValidationResult


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
    extracted_data: Optional[ProfileData]
    validation_result: Optional[ValidationResult]
    metrics: Dict[str, Any]
    error: Optional[str]
    error_details: Optional[Dict[str, Any]]


# --- Graph Definition will go below here --- #
# (We will add the StateGraph instantiation, nodes, and edges later)
