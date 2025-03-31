from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# New model for structured degree information
class DegreeInfo(BaseModel):
    """Schema for storing structured academic degree information."""

    degree_type: Optional[str] = Field(
        None, description="The type of degree (e.g., Ph.D., M.S., B.A.)."
    )
    institution: Optional[str] = Field(
        None, description="The institution that awarded the degree."
    )
    year: Optional[str] = Field(
        None, description="The year the degree was awarded (as a string)."
    )  # Using str for flexibility with LLM output


class ProfileData(BaseModel):
    """Schema for storing extracted faculty profile information."""

    source_url: str = Field(
        ..., description="The URL from which the profile data was extracted."
    )
    photo_url: Optional[str] = Field(
        None, description="URL of the faculty member's photo."
    )
    first_name: Optional[str] = Field(
        None, description="First name of the faculty member."
    )
    middle_name: Optional[str] = Field(
        None, description="Middle name or initial of the faculty member."
    )
    last_name: Optional[str] = Field(
        None, description="Last name of the faculty member."
    )
    title: Optional[str] = Field(None, description="Official title or position.")
    office: Optional[str] = Field(
        None, description="Office location (building, room number)."
    )
    phone: Optional[str] = Field(None, description="Contact phone number.")
    email: Optional[str] = Field(None, description="Contact email address.")
    college_unit: Optional[str] = Field(
        None, description="The college or primary administrative unit."
    )
    department_division: Optional[str] = Field(
        None, description="The department or division within the college/unit."
    )
    degrees: Optional[List[DegreeInfo]] = Field(
        None,
        description="List of academic degrees held, including type, institution, and year.",
    )
    research_focus_areas: Optional[List[str]] = Field(
        None, description="List of research focus areas or interests."
    )


class ValidationStatus(str, Enum):
    """Possible validation statuses for each extracted field."""

    CORRECT = "Correct"
    INCORRECT = "Incorrect"
    MISSING = "Missing"
    NOT_APPLICABLE = (
        "Not Applicable"  # For fields like source_url which aren't extracted
    )


class ValidationResult(BaseModel):
    """Schema for storing the LLM judge's validation results."""

    photo_url_status: ValidationStatus = Field(
        ..., description="Validation status for photo_url."
    )
    first_name_status: ValidationStatus = Field(
        ..., description="Validation status for first_name."
    )
    middle_name_status: ValidationStatus = Field(
        ..., description="Validation status for middle_name."
    )
    last_name_status: ValidationStatus = Field(
        ..., description="Validation status for last_name."
    )
    title_status: ValidationStatus = Field(
        ..., description="Validation status for title."
    )
    office_status: ValidationStatus = Field(
        ..., description="Validation status for office."
    )
    phone_status: ValidationStatus = Field(
        ..., description="Validation status for phone."
    )
    email_status: ValidationStatus = Field(
        ..., description="Validation status for email."
    )
    college_unit_status: ValidationStatus = Field(
        ..., description="Validation status for college_unit."
    )
    department_division_status: ValidationStatus = Field(
        ..., description="Validation status for department_division."
    )
    degrees_status: ValidationStatus = Field(
        ..., description="Validation status for degrees."
    )
    research_focus_areas_status: ValidationStatus = Field(
        ..., description="Validation status for research_focus_areas."
    )
    overall_comment: Optional[str] = Field(
        None, description="Optional overall comment or reasoning from the LLM judge."
    )
