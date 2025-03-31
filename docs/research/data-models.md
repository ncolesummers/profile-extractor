# Data Models

This document defines the Pydantic data models used for structuring the extracted profile data and the validation results from the LLM judge.

## Phase 2: Data Modeling (Pydantic)

1.  **Define Profile Schema (`schemas.py`):**
    *   Create a Pydantic `BaseModel` representing the desired output for a single profile. This enforces structure and types.
    ```python
    from pydantic import BaseModel, Field, HttpUrl, EmailStr
    from typing import Optional, List

    # Add definition for the new DegreeInfo model
    class DegreeInfo(BaseModel):
        degree_type: Optional[str] = Field(None, description="The type of degree (e.g., Ph.D., M.S., B.A.).")
        institution: Optional[str] = Field(None, description="The institution that awarded the degree.")
        year: Optional[str] = Field(None, description="The year the degree was awarded (as a string).")

    class ProfileData(BaseModel):
        source_url: HttpUrl = Field(description="The URL the data was extracted from")
        photo_url: Optional[HttpUrl] = Field(None, description="URL of the profile photo")
        first_name: Optional[str] = Field(None, description="Person's first name")
        middle_name: Optional[str] = Field(None, description="Person's middle name or initial")
        last_name: Optional[str] = Field(None, description="Person's last name")
        title: Optional[str] = Field(None, description="Job title(s). Comma-separate if multiple.")
        office: Optional[str] = Field(None, description="Office location (building/room number)")
        phone: Optional[str] = Field(None, description="Primary phone number")
        email: Optional[EmailStr] = Field(None, description="Primary email address")
        college_unit: Optional[str] = Field(None, description="College or main administrative unit")
        department_division: Optional[str] = Field(None, description="Department or division within the college/unit")
        # Update the degrees field description and type
        degrees: Optional[List[DegreeInfo]] = Field(None, description="List of academic degrees held (type, institution, year)")
        research_focus_areas: Optional[List[str]] = Field(None, description="List of research areas or focus keywords")

        class Config:
            extra = 'ignore' # Ignore extra fields returned by LLM if any
    ```
2.  **Define Judge Schema (`schemas.py`):**
    *   Create a Pydantic model for the structured output expected from the LLM judge.
    ```python
    class FieldValidation(BaseModel):
        status: str = Field(description="Evaluation status: 'Correct', 'Incorrect', 'Missing'")
        reason: Optional[str] = Field(None, description="Brief explanation if status is not 'Correct'")

    class ValidationResult(BaseModel):
        photo_url: Optional[FieldValidation] = None
        first_name: Optional[FieldValidation] = None
        middle_name: Optional[FieldValidation] = None
        last_name: Optional[FieldValidation] = None
        title: Optional[FieldValidation] = None
        office: Optional[FieldValidation] = None
        phone: Optional[FieldValidation] = None
        email: Optional[FieldValidation] = None
        college_unit: Optional[FieldValidation] = None
        department_division: Optional[FieldValidation] = None
        degrees: Optional[FieldValidation] = None
        research_focus_areas: Optional[FieldValidation] = None
        # Add other fields as needed
    ``` 