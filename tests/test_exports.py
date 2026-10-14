import csv
import io

from event_app.exports import registrations_csv


def test_registration_csv_escapes_spreadsheet_formulas():
    content = registrations_csv(
        [
            {
                "student_name": "=HYPERLINK(\"https://example.com\")",
                "student_id": "STU-42",
                "email": "student@example.edu",
                "phone": None,
                "created_at": "2026-10-14T12:00:00Z",
            }
        ]
    )
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))

    assert rows[0]["student_name"].startswith("'=")
    assert rows[0]["student_id"] == "STU-42"
