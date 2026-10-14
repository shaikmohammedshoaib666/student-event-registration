"""Data access for coordinator-published event updates."""

from typing import Any


def list_event_announcements(client: Any, event_id: str) -> list[dict[str, Any]]:
    return (
        client.table("event_announcements")
        .select("id,event_id,coordinator_email,body,created_at")
        .eq("event_id", event_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def create_event_announcement(
    client: Any,
    event_id: str,
    coordinator_email: str,
    body: str,
) -> dict[str, Any]:
    cleaned_body = body.strip()
    if not 1 <= len(cleaned_body) <= 2000:
        raise ValueError("Event updates must be between 1 and 2,000 characters.")
    rows = (
        client.table("event_announcements")
        .insert(
            {
                "event_id": event_id,
                "coordinator_email": coordinator_email.strip().lower(),
                "body": cleaned_body,
            }
        )
        .execute()
        .data
        or []
    )
    if not rows:
        raise RuntimeError("Supabase did not return the published event update.")
    return rows[0]


def delete_event_announcement(
    client: Any,
    announcement_id: str,
    coordinator_email: str,
) -> None:
    client.table("event_announcements").delete().eq(
        "id", announcement_id
    ).eq("coordinator_email", coordinator_email.strip().lower()).execute()
