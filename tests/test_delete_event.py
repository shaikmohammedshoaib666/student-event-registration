from event_app.supabase_data import delete_event


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.deleting = False

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def delete(self):
        self.deleting = True
        return self

    def execute(self):
        if self.deleting:
            self.client.deleted_events.append(dict(self.filters))
            return FakeResult()
        if self.table == "event_photos":
            return FakeResult(
                [{"storage_path": "event-1/photo.jpg"}]
                if ("event_id", "event-1") in self.filters
                else []
            )
        if self.table == "event_conversations":
            return FakeResult(
                [{"id": "conversation-1"}]
                if ("event_id", "event-1") in self.filters
                else []
            )
        if self.table == "event_messages":
            return FakeResult(
                [{"attachment_path": "conversation-1/student-1/chat.png"}]
            )
        raise AssertionError(f"Unexpected table: {self.table}")


class FakeStorageBucket:
    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket

    def remove(self, paths):
        self.client.removed_objects.append((self.bucket, paths))


class FakeStorage:
    def __init__(self, client):
        self.client = client

    def from_(self, bucket):
        return FakeStorageBucket(self.client, bucket)


class FakeClient:
    def __init__(self):
        self.deleted_events = []
        self.removed_objects = []
        self.storage = FakeStorage(self)

    def table(self, table):
        return FakeQuery(self, table)


def test_deleting_event_removes_storage_and_then_cascades_database_records():
    client = FakeClient()

    delete_event(client, "event-1", event_photo_bucket="campus-event-photos")

    assert client.removed_objects == [
        ("campus-event-photos", ["event-1/photo.jpg"]),
        ("chat-attachments", ["conversation-1/student-1/chat.png"]),
    ]
    assert client.deleted_events == [{"id": "event-1"}]
