import pytest

from event_app.chat import (
    get_or_create_conversation,
    send_message,
    signed_chat_image_url,
    upload_chat_image,
)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, existing, inserted, table):
        self.existing = existing
        self.inserted = inserted
        self.table = table
        self.inserted_payload = None
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, _count):
        return self

    def insert(self, payload):
        self.inserted_payload = payload
        return self

    def execute(self):
        if self.inserted_payload is not None:
            return FakeResult([self.inserted])
        return FakeResult(self.existing)


class FakeClient:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.inserted_payload = None
        self.inserted = {
            "id": "conversation-1",
            "coordinator_email": "coord@example.edu",
        }

    def table(self, table):
        self.query = FakeQuery(self.existing, self.inserted, table)
        return self.query


class FakeStorageBucket:
    def __init__(self):
        self.uploaded = None

    def upload(self, path, content, options):
        self.uploaded = (path, content, options)

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://example.test/{path}?expires={expires_in}"}


class FakeStorage:
    def __init__(self):
        self.bucket = FakeStorageBucket()

    def from_(self, _bucket):
        return self.bucket


class FakeUpload:
    type = "image/png"

    def __init__(self, data):
        self.data = data

    def getvalue(self):
        return self.data


class FakeMessageClient:
    def __init__(self):
        self.storage = FakeStorage()
        self.payload = None

    def table(self, _table):
        client = self

        class Query:
            def insert(self, payload):
                client.payload = payload
                return self

            def execute(self):
                return None

        return Query()


def test_conversation_creation_records_student_profile_and_normalizes_addresses():
    client = FakeClient()

    thread = get_or_create_conversation(
        client,
        "event-1",
        "student-1",
        "STUDENT@example.edu",
        "Jordan Student",
        "COORD@example.edu",
        "STU-123",
    )

    assert thread["id"] == "conversation-1"
    assert client.query.inserted_payload == {
        "event_id": "event-1",
        "student_user_id": "student-1",
        "student_email": "student@example.edu",
        "student_name": "Jordan Student",
        "student_id": "STU-123",
        "coordinator_email": "coord@example.edu",
    }


def test_conversation_reuses_existing_event_student_coordinator_thread():
    existing = {
        "id": "conversation-1",
        "event_id": "event-1",
        "student_user_id": "student-1",
        "coordinator_email": "coord@example.edu",
    }
    client = FakeClient(existing=[existing])

    thread = get_or_create_conversation(
        client,
        "event-1",
        "student-1",
        "student@example.edu",
        "Jordan Student",
        "coord@example.edu",
    )

    assert thread is existing
    assert client.query.inserted_payload is None
    assert client.query.filters == [
        ("event_id", "event-1"),
        ("student_user_id", "student-1"),
        ("coordinator_email", "coord@example.edu"),
    ]


def test_chat_photo_is_uploaded_to_private_conversation_path_and_signed():
    client = FakeMessageClient()

    path = upload_chat_image(
        client,
        "conversation-1",
        "student-1",
        FakeUpload(b"png bytes"),
    )
    signed_url = signed_chat_image_url(client, path)

    assert path.startswith("conversation-1/student-1/")
    assert path.endswith(".png")
    assert client.storage.bucket.uploaded[1:] == (
        b"png bytes",
        {"content-type": "image/png", "upsert": "false"},
    )
    assert signed_url == f"https://example.test/{path}?expires=3600"


def test_chat_message_allows_photo_only_and_rejects_empty_message():
    client = FakeMessageClient()

    send_message(
        client,
        "conversation-1",
        "student-1",
        "STUDENT@example.edu",
        "",
        attachment_path="conversation-1/student-1/photo.png",
    )

    assert client.payload["body"] == ""
    assert client.payload["attachment_path"].endswith("photo.png")
    assert client.payload["sender_email"] == "student@example.edu"

    try:
        send_message(client, "conversation-1", "student-1", "student@example.edu", "")
    except ValueError as error:
        assert "text or a photo" in str(error)
    else:
        raise AssertionError("Empty chat messages should be rejected.")


def test_chat_photo_rejects_unsupported_types_and_oversized_files():
    client = FakeMessageClient()

    with pytest.raises(ValueError, match="PNG, JPG, or WebP"):
        upload_chat_image(
            client,
            "conversation-1",
            "student-1",
            type("Upload", (), {"type": "application/pdf", "getvalue": lambda _self: b"data"})(),
        )
    with pytest.raises(ValueError, match="5 MB or smaller"):
        upload_chat_image(
            client,
            "conversation-1",
            "student-1",
            FakeUpload(b"x" * (5 * 1024 * 1024 + 1)),
        )
