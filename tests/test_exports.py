import csv
import io

from event_app.exports import registrations_csv


def test_registration_csv_escapes_spreadsheet_formulas():
    content = registrations_csv(
        [
            {
                "Student name": "=HYPERLINK(\"https://example.com\")",
                "Student ID": "STU-42",
                "Email": "student@example.edu",
                "Phone": "",
                "Registered at": "2026-10-14T12:00:00Z",
                "Dietary needs": "=IMPORTXML(\"https://example.com\")",
            }
        ]
    )
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))

    assert rows[0]["Student name"].startswith("'=")
    assert rows[0]["Student ID"] == "STU-42"
    assert rows[0]["Dietary needs"].startswith("'=")
