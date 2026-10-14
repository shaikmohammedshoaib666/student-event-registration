"""Validation and rendering-independent logic for admin-defined event questions."""

import re
from math import isnan
from typing import Any, Optional


EDITOR_TYPES = {
    "Short answer": "text",
    "Paragraph": "textarea",
    "Dropdown": "select",
    "Checkbox": "checkbox",
}
DISPLAY_TYPES = {value: key for key, value in EDITOR_TYPES.items()}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESERVED_LABELS = {
    "student name",
    "student id",
    "email",
    "phone",
    "registered at",
}


def _cell_value(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return value


def editor_rows(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for field in fields or []:
        rows.append(
            {
                "Question": field.get("label", ""),
                "Answer type": DISPLAY_TYPES.get(field.get("type", "text"), "Short answer"),
                "Required": bool(field.get("required", False)),
                "Dropdown choices (comma separated)": ", ".join(field.get("options", [])),
            }
        )
    return rows


def coordinator_editor_rows(coordinators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Name": coordinator.get("name", ""),
            "Email": coordinator.get("email", ""),
            "Phone": coordinator.get("phone", ""),
        }
        for coordinator in coordinators or []
    ]


def validate_coordinators(
    rows: list[dict[str, Any]],
) -> tuple[Optional[list[dict[str, str]]], list[str]]:
    coordinators = []
    errors = []
    seen_emails = set()

    for row in rows:
        name = " ".join(str(_cell_value(row.get("Name"))).split())
        email = str(_cell_value(row.get("Email"))).strip().lower()
        phone = str(_cell_value(row.get("Phone"))).strip()
        if not name and not email and not phone:
            continue
        if not name:
            errors.append("Add a name for every event coordinator.")
            continue
        if email and not EMAIL_PATTERN.fullmatch(email):
            errors.append(f"Enter a valid email for coordinator {name}.")
            continue
        if email in seen_emails:
            errors.append(f"Coordinator email must be unique: {email}.")
            continue
        if not email and not phone:
            errors.append(f"Add an email or phone number for coordinator {name}.")
            continue
        if phone and not all(character.isdigit() or character in "+ ()-." for character in phone):
            errors.append(f"Enter a valid phone number for coordinator {name}.")
            continue
        if email:
            seen_emails.add(email)
        coordinators.append({"name": name, "email": email, "phone": phone})

    if len(coordinators) > 10:
        errors.append("An event can have at most 10 coordinators.")
    return (None, errors) if errors else (coordinators, [])


def validate_registration_fields(
    rows: list[dict[str, Any]],
) -> tuple[Optional[list[dict[str, Any]]], list[str]]:
    fields = []
    errors = []
    labels_seen = set()

    for row in rows:
        label = " ".join(str(_cell_value(row.get("Question"))).split())
        answer_type = EDITOR_TYPES.get(
            _cell_value(row.get("Answer type")) or "Short answer"
        )
        raw_options = str(
            _cell_value(row.get("Dropdown choices (comma separated)"))
        )
        options = list(dict.fromkeys(
            " ".join(option.split()) for option in str(raw_options).split(",") if option.strip()
        ))
        required = bool(_cell_value(row.get("Required", False)))

        if not label and not raw_options.strip():
            continue
        if not label:
            errors.append("Give each registration question a label.")
            continue
        normalized_label = label.casefold()
        if normalized_label in RESERVED_LABELS:
            errors.append(f"“{label}” is reserved for student registration details.")
            continue
        if normalized_label in labels_seen:
            errors.append(f"Question labels must be unique: “{label}”.")
            continue
        labels_seen.add(normalized_label)
        if answer_type is None:
            errors.append(f"Choose an answer type for “{label}”.")
            continue
        if len(label) > 120:
            errors.append(f"Question labels must be 120 characters or fewer: “{label}”.")
            continue
        if answer_type == "select" and len(options) < 2:
            errors.append(f"Add at least two comma-separated choices for “{label}”.")
            continue

        field = {"label": label, "type": answer_type, "required": required}
        if answer_type == "select":
            field["options"] = options
        fields.append(field)

    if errors:
        return None, errors
    if len(fields) > 12:
        return None, ["An event can have at most 12 additional registration questions."]
    return fields, []


def validate_registration_answers(
    fields: list[dict[str, Any]],
    answers: dict[str, Any],
) -> list[str]:
    errors = []
    for field in fields or []:
        label = field["label"]
        answer = answers.get(label)
        if field.get("required") and (
            answer is None
            or (isinstance(answer, str) and not answer.strip())
            or (field["type"] == "checkbox" and answer is not True)
        ):
            errors.append(f"Answer “{label}” to continue.")
        if field["type"] == "select" and answer and answer not in field.get("options", []):
            errors.append(f"Choose one of the listed options for “{label}”.")
        if field["type"] == "text" and isinstance(answer, str) and len(answer) > 500:
            errors.append(f"Keep “{label}” to 500 characters or fewer.")
        if field["type"] == "textarea" and isinstance(answer, str) and len(answer) > 3000:
            errors.append(f"Keep “{label}” to 3,000 characters or fewer.")
    return errors


def flatten_registration(row: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    flattened = {
        "Student name": row.get("student_name"),
        "Student ID": row.get("student_id"),
        "Email": row.get("email"),
        "Phone": row.get("phone"),
        "Registered at": row.get("created_at"),
    }
    answers = row.get("form_answers") or {}
    for field in fields or []:
        flattened[field["label"]] = answers.get(field["label"], "")
    for label, answer in answers.items():
        flattened.setdefault(label, answer)
    return flattened
