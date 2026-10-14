"""Supabase data access for events, registrations, and event photos."""

from typing import Any
from typing import Optional


def list_events(client: Any, *, published_only: bool = True) -> list[dict[str, Any]]:
    query = client.table("events").select("*").order("starts_at")
    if published_only:
        query = query.eq("published", True)
    return query.execute().data or []


def registration_counts(client: Any) -> dict[str, int]:
    rows = client.table("event_registration_counts").select("event_id,registration_count").execute().data or []
    return {row["event_id"]: int(row["registration_count"]) for row in rows}


def list_photos(client: Any, event_id: str) -> list[dict[str, Any]]:
    return (
        client.table("event_photos")
        .select("*")
        .eq("event_id", event_id)
        .order("created_at")
        .execute()
        .data
        or []
    )


def save_event(
    client: Any,
    event_data: dict[str, Any],
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    if event_id:
        result = client.table("events").update(event_data).eq("id", event_id).execute()
    else:
        result = client.table("events").insert(event_data).execute()
    if not result.data:
        raise RuntimeError("Supabase did not return the saved event.")
    return result.data[0]


def create_registration(
    client: Any,
    event_id: str,
    student: dict[str, Optional[str]],
    user_id: str,
) -> None:
    client.table("registrations").insert(
        {"event_id": event_id, "user_id": user_id, **student}
    ).execute()


def list_registrations(client: Any, event_id: str) -> list[dict[str, Any]]:
    return (
        client.table("registrations")
        .select("student_name,student_id,email,phone,created_at")
        .eq("event_id", event_id)
        .order("created_at")
        .execute()
        .data
        or []
    )


def save_photo_record(
    client: Any,
    event_id: str,
    storage_path: str,
    public_url: str,
) -> None:
    client.table("event_photos").insert(
        {"event_id": event_id, "storage_path": storage_path, "public_url": public_url}
    ).execute()


def delete_photo_record(client: Any, photo_id: str) -> None:
    client.table("event_photos").delete().eq("id", photo_id).execute()
