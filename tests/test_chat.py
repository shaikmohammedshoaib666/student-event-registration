from event_app.chat import get_or_create_conversation


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


def test_conversation_creation_records_student_profile_and_normalizes_addresses():
    client = FakeClient()

    thread = get_or_create_conversation(
        client,
        "event-1",
        "student-1",
        "STUDENT@example.edu",
        "Jordan Student",
        "COORD@example.edu",
    )

    assert thread["id"] == "conversation-1"
    assert client.query.inserted_payload == {
        "event_id": "event-1",
        "student_user_id": "student-1",
        "student_email": "student@example.edu",
        "student_name": "Jordan Student",
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
