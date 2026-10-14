import pytest

from event_app.validation import validate_registration


def test_registration_details_are_normalized():
    student, errors = validate_registration(
        "  Ada   Lovelace ",
        " stu-20481 ",
        " ADA@Example.EDU ",
        "+1 (555) 123-4567",
    )

    assert errors == []
    assert student == {
        "student_name": "Ada Lovelace",
        "student_id": "STU-20481",
        "email": "ada@example.edu",
        "phone": "+1 (555) 123-4567",
    }


@pytest.mark.parametrize(
    ("name", "student_id", "email", "phone"),
    [
        ("", "STU-1", "ada@example.edu", ""),
        ("Ada", " ", "ada@example.edu", ""),
        ("Ada", "STU-1", "invalid-email", ""),
        ("Ada", "STU-1", "ada@example.edu", "12"),
    ],
)
def test_invalid_registration_details_are_rejected(name, student_id, email, phone):
    student, errors = validate_registration(name, student_id, email, phone)

    assert student is None
    assert errors


def test_invalid_student_email_is_rejected():
    student, errors = validate_registration("Ada Lovelace", "STU-20481", "ada-at-example.com")

    assert student is None
    assert errors == ["Enter a valid email address."]
