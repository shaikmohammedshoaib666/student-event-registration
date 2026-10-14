"""Validation helpers for multi-student event registrations."""

import re
from typing import Any, Optional

from event_app.registration_forms import EMAIL_PATTERN


def validate_team_members(
    rows: list[dict[str, Any]],
    *,
    team_size: int,
    leader_student_id: str,
) -> tuple[Optional[list[dict[str, str]]], list[str]]:
    if not 1 <= team_size <= 8:
        return None, ["A team must include at least the registering student."]

    member_rows = rows[: max(team_size - 1, 0)]
    members = []
    student_ids = {leader_student_id.strip().casefold()}
    errors = []
    if len(rows) != team_size - 1:
        return None, ["Enter details for every additional team member."]
    for index, row in enumerate(member_rows, start=2):
        name = " ".join(str(row.get("Name") or "").split())
        student_id = str(row.get("Student ID") or "").strip().upper()
        email = str(row.get("Email") or "").strip().lower()
        phone = str(row.get("Phone") or "").strip()

        if not name or len(name) > 100:
            errors.append(f"Enter a name of up to 100 characters for team member {index}.")
        if len(student_id) < 2 or len(student_id) > 50:
            errors.append(f"Enter a valid student ID for team member {index}.")
        elif student_id.casefold() in student_ids:
            errors.append(f"Student IDs must be unique within the team: {student_id}.")
        else:
            student_ids.add(student_id.casefold())
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            errors.append(f"Enter a valid email for team member {index}.")
        if phone:
            digits = re.sub(r"\D", "", phone)
            if (
                len(digits) < 7
                or len(digits) > 20
                or not re.fullmatch(r"[+()\d\s.-]+", phone)
            ):
                errors.append(f"Enter a valid phone number for team member {index}.")
        members.append(
            {
                "name": name,
                "student_id": student_id,
                "email": email,
                "phone": phone,
            }
        )
    return (None, errors) if errors else (members, [])
