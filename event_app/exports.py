"""Safe downloadable exports for administrator workflows."""

import csv
import io
from typing import Any


REGISTRATION_COLUMNS = ("student_name", "student_id", "email", "phone", "created_at")


def registrations_csv(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=REGISTRATION_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        safe_row = {}
        for column in REGISTRATION_COLUMNS:
            value = row.get(column, "")
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = f"'{value}"
            safe_row[column] = value
        writer.writerow(safe_row)
    return output.getvalue().encode("utf-8-sig")
