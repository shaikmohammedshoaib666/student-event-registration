"""Persisted event chat access helpers."""

from uuid import uuid4
from typing import Any, Optional


CHAT_BUCKET = "chat-attachments"
CHAT_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
CHAT_IMAGE_MAX_BYTES = 5 * 1024 * 1024


def get_or_create_conversation(
    client: Any,
    event_id: str,
    student_user_id: str,
    student_email: str,
    student_name: str,
    coordinator_email: str,
    student_id: str = "",
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
            "student_id": student_id.strip(),
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


def get_student_conversation(
    client: Any,
    conversation_id: str,
    student_user_id: str,
) -> Optional[dict[str, Any]]:
    rows = (
        client.table("event_conversations")
        .select("*,events(title,starts_at)")
        .eq("id", conversation_id)
        .eq("student_user_id", student_user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def list_messages(client: Any, conversation_id: str) -> list[dict[str, Any]]:
    return (
        client.table("event_messages")
        .select("id,sender_user_id,sender_email,body,attachment_path,created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
        or []
    )


def upload_chat_image(
    client: Any,
    conversation_id: str,
    sender_user_id: str,
    uploaded: Any,
) -> str:
    mime_type = uploaded.type
    extension = CHAT_IMAGE_TYPES.get(mime_type)
    if extension is None:
        raise ValueError("Chat attachments must be PNG, JPG, or WebP images.")
    content = uploaded.getvalue()
    if not content or len(content) > CHAT_IMAGE_MAX_BYTES:
        raise ValueError("Chat photos must be non-empty and 5 MB or smaller.")

    path = f"{conversation_id}/{sender_user_id}/{uuid4().hex}.{extension}"
    client.storage.from_(CHAT_BUCKET).upload(
        path,
        content,
        {"content-type": mime_type, "upsert": "false"},
    )
    return path


def signed_chat_image_url(client: Any, path: str) -> str:
    result = client.storage.from_(CHAT_BUCKET).create_signed_url(path, 3600)
    signed_url = result.get("signedURL") or result.get("signedUrl")
    if not signed_url:
        raise RuntimeError("Supabase did not return a signed URL for this photo.")
    return signed_url


def send_message(
    client: Any,
    conversation_id: str,
    sender_user_id: str,
    sender_email: str,
    body: str,
    *,
    attachment_path: Optional[str] = None,
) -> None:
    cleaned_body = body.strip()
    if not cleaned_body and not attachment_path:
        raise ValueError("A message must contain text or a photo.")
    client.table("event_messages").insert(
        {
            "conversation_id": conversation_id,
            "sender_user_id": sender_user_id,
            "sender_email": sender_email.lower(),
            "body": cleaned_body,
            "attachment_path": attachment_path,
        }
    ).execute()
