"""Safe downloadable exports for administrator workflows."""

import csv
import io
from typing import Any


REGISTRATION_COLUMNS = (
    "Student name",
    "Student ID",
    "Email",
    "Phone",
    "Registered at",
)


def registrations_csv(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    extra_columns = list(dict.fromkeys(
        column for row in rows for column in row if column not in REGISTRATION_COLUMNS
    ))
    columns = [*REGISTRATION_COLUMNS, *extra_columns]
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        safe_row = {}
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = f"'{value}"
            safe_row[column] = value
        writer.writerow(safe_row)
    return output.getvalue().encode("utf-8-sig")
