"""Constant-time verification for a small server-configured admin allowlist."""

import hmac
import re
from typing import Mapping, Optional


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def admin_configuration_error(credentials: Mapping[str, str]) -> Optional[str]:
    if not 1 <= len(credentials) <= 3:
        return "Configure between one and three admin email/password pairs."
    for email, password in credentials.items():
        if not EMAIL_PATTERN.fullmatch(str(email).strip()):
            return "Each admin account needs a valid email address."
        if len(str(password)) < 16:
            return "Each admin password must contain at least 16 characters."
    return None


def authenticate_admin(
    credentials: Mapping[str, str],
    email: str,
    password: str,
) -> bool:
    if admin_configuration_error(credentials):
        return False
    candidate_email = email.strip().lower()
    matched = False
    for configured_email, configured_password in credentials.items():
        email_matches = hmac.compare_digest(
            candidate_email.encode("utf-8"),
            str(configured_email).strip().lower().encode("utf-8"),
        )
        password_matches = hmac.compare_digest(
            password.encode("utf-8"),
            str(configured_password).encode("utf-8"),
        )
        matched = matched or (email_matches and password_matches)
    return matched
