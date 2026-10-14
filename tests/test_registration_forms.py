import math

from event_app.registration_forms import (
    editor_rows,
    flatten_registration,
    validate_registration_answers,
    validate_registration_fields,
)


def test_admin_form_questions_round_trip_through_editor():
    original = [
        {
            "label": "Meal choice",
            "type": "select",
            "required": True,
            "options": ["Vegetarian", "Vegan"],
        }
    ]

    rows = editor_rows(original)
    fields, errors = validate_registration_fields(rows)

    assert errors == []
    assert fields == original


def test_registration_question_validation_rejects_bad_and_duplicate_fields():
    fields, errors = validate_registration_fields(
        [
            {
                "Question": "Meal choice",
                "Answer type": "Dropdown",
                "Required": True,
                "Dropdown choices (comma separated)": "Vegetarian",
            },
            {
                "Question": "meal choice",
                "Answer type": "Short answer",
                "Required": False,
                "Dropdown choices (comma separated)": "",
            },
        ]
    )

    assert fields is None
    assert any("at least two" in error for error in errors)
    assert any("unique" in error for error in errors)


def test_registration_question_validation_prevents_student_field_collisions():
    fields, errors = validate_registration_fields(
        [
            {
                "Question": "Email",
                "Answer type": "Short answer",
                "Required": False,
                "Dropdown choices (comma separated)": "",
            }
        ]
    )

    assert fields is None
    assert "reserved" in errors[0]


def test_empty_dynamic_editor_rows_with_nan_cells_are_ignored():
    fields, errors = validate_registration_fields(
        [
            {
                "Question": float("nan"),
                "Answer type": float("nan"),
                "Required": math.nan,
                "Dropdown choices (comma separated)": float("nan"),
            }
        ]
    )

    assert fields == []
    assert errors == []


def test_registration_answers_enforce_required_and_dropdown_values():
    fields = [
        {
            "label": "Dietary needs",
            "type": "text",
            "required": True,
        },
        {
            "label": "Meal choice",
            "type": "select",
            "required": True,
            "options": ["Vegetarian", "Vegan"],
        },
    ]

    errors = validate_registration_answers(
        fields,
        {"Dietary needs": "   ", "Meal choice": "Meat"},
    )

    assert len(errors) == 2


def test_registration_answers_are_flattened_for_admin_review():
    result = flatten_registration(
        {
            "student_name": "Ada Lovelace",
            "student_id": "STU-1",
            "email": "ada@example.edu",
            "phone": None,
            "created_at": "2026-10-14T12:00:00Z",
            "form_answers": {"Meal choice": "Vegan"},
        },
        [{"label": "Meal choice"}],
    )

    assert result["Registered at"] == "2026-10-14T12:00:00Z"
    assert result["Meal choice"] == "Vegan"


def test_flattening_keeps_answers_to_questions_removed_from_event():
    result = flatten_registration(
        {
            "student_name": "Ada Lovelace",
            "form_answers": {"Old question": "Historical answer"},
        },
        [],
    )

    assert result["Old question"] == "Historical answer"
