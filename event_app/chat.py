"""Persisted event chat access helpers."""

from typing import Any


def get_or_create_conversation(
    client: Any,
    event_id: str,
    student_user_id: str,
    student_email: str,
    student_name: str,
    coordinator_email: str,
) -> dict[str, Any]:
    query = (
        client.table("event_conversations")
        .select("*")
        .eq("event_id", event_id)
        .eq("student_user_id", student_user_id)
        .eq("coordinator_email", coordinator_email.lower())
    )
    existing = query.limit(1).execute().data or []
    if existing:
        return existing[0]
    inserted = client.table("event_conversations").insert(
        {
            "event_id": event_id,
            "student_user_id": student_user_id,
            "student_email": student_email.lower(),
            "student_name": student_name,
            "coordinator_email": coordinator_email.lower(),
        }
    ).execute().data or []
    if not inserted:
        raise RuntimeError("Supabase did not return the new conversation.")
    return inserted[0]


def list_conversations(client: Any, user_id: str, email: str) -> list[dict[str, Any]]:
    student_threads = (
        client.table("event_conversations")
        .select("*,events(title,starts_at)")
        .eq("student_user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )
    coordinator_threads = (
        client.table("event_conversations")
        .select("*,events(title,starts_at)")
        .eq("coordinator_email", email.lower())
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )
    conversations = {thread["id"]: thread for thread in student_threads}
    conversations.update({thread["id"]: thread for thread in coordinator_threads})
    return sorted(
        conversations.values(),
        key=lambda thread: thread.get("updated_at", ""),
        reverse=True,
    )


def list_messages(client: Any, conversation_id: str) -> list[dict[str, Any]]:
    return (
        client.table("event_messages")
        .select("id,sender_user_id,sender_email,body,created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
        or []
    )


def send_message(
    client: Any,
    conversation_id: str,
    sender_user_id: str,
    sender_email: str,
    body: str,
) -> None:
    client.table("event_messages").insert(
        {
            "conversation_id": conversation_id,
            "sender_user_id": sender_user_id,
            "sender_email": sender_email.lower(),
            "body": body.strip(),
        }
    ).execute()
