"""Convert common Supabase/PostgREST failures into useful safe setup guidance."""

from typing import Any


def backend_error_message(error: Exception) -> str:
    code = str(getattr(error, "code", "") or "")
    message = str(getattr(error, "message", "") or error).strip()
    lowered = f"{code} {message}".lower()

    if any(marker in lowered for marker in ("pgrst205", "pgrst204", "42p01", "42703", "does not exist")):
        return (
            "The Supabase tables or columns are missing or outdated. In the correct Supabase "
            "project, run the latest `supabase/schema.sql` from this repository in SQL Editor, "
            "then reload this app."
        )
    if code == "42501" or "permission denied" in lowered or "not allowed" in lowered:
        return (
            "Supabase denied database access. Check that `SUPABASE_SERVICE_ROLE_KEY` is a "
            "server-side Secret key and rerun `supabase/schema.sql` in this project."
        )
    if code in ("401", "403") or "invalid api key" in lowered or "invalid jwt" in lowered:
        return (
            "Supabase rejected the configured key. Check `SUPABASE_URL` and replace "
            "`SUPABASE_SERVICE_ROLE_KEY` with the server-side Secret key for this same project."
        )
    if "could not translate host" in lowered or "name or service not known" in lowered:
        return "The Supabase URL could not be reached. Check `SUPABASE_URL` in Streamlit Secrets."

    # Error messages returned by PostgREST contain database diagnostics, not request headers.
    # Bound their size so a server error cannot flood the public app.
    detail = message[:300]
    return f"Supabase request failed ({code or 'unknown error'}): {detail}"
