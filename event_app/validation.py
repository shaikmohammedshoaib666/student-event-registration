"""Input validation shared by the Streamlit UI and tests."""

import re
from typing import Optional


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(
    name: str,
    student_id: str,
    email: str,
    phone: str = "",
) -> tuple[Optional[dict[str, Optional[str]]], list[str]]:
    """Normalize and validate student details before they reach Supabase."""
    cleaned_name = " ".join(name.split())
    cleaned_student_id = student_id.strip().upper()
    cleaned_email = email.strip().lower()
    cleaned_phone = phone.strip()
    errors: list[str] = []

    if not 2 <= len(cleaned_name) <= 100:
        errors.append("Enter your full name (2–100 characters).")
    if not 2 <= len(cleaned_student_id) <= 50:
        errors.append("Enter a valid student ID (2–50 characters).")
    if not EMAIL_PATTERN.fullmatch(cleaned_email) or len(cleaned_email) > 254:
        errors.append("Enter a valid email address.")
    if cleaned_phone:
        digits = re.sub(r"\D", "", cleaned_phone)
        if (
            len(digits) < 7
            or len(digits) > 20
            or not re.fullmatch(r"[+()\d\s.-]+", cleaned_phone)
        ):
            errors.append("Enter a valid phone number or leave it blank.")

    if errors:
        return None, errors

    return {
        "student_name": cleaned_name,
        "student_id": cleaned_student_id,
        "email": cleaned_email,
        "phone": cleaned_phone or None,
    }, []
