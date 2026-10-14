import pytest

from event_app.announcements import (
    create_event_announcement,
    delete_event_announcement,
    list_event_announcements,
)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.payload = None
        self.deleted = False

    def select(self, *_args):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def delete(self):
        self.deleted = True
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.client.last_query = self
        if self.payload:
            return FakeResult([{"id": "update-1", **self.payload}])
        if self.deleted:
            return FakeResult([])
        return FakeResult(self.client.updates)


class FakeClient:
    def __init__(self):
        self.updates = [{"id": "update-1", "body": "Meeting moved"}]
        self.last_query = None

    def table(self, table):
        assert table == "event_announcements"
        return FakeQuery(self, table)


def test_create_public_event_update_normalizes_coordinator_email():
    client = FakeClient()

    result = create_event_announcement(
        client,
        "event-1",
        "COORDINATOR@example.edu",
        "  Bring your student ID. ",
    )

    assert result == {
        "id": "update-1",
        "event_id": "event-1",
        "coordinator_email": "coordinator@example.edu",
        "body": "Bring your student ID.",
    }


@pytest.mark.parametrize("body", ["", "  ", "x" * 2001])
def test_public_update_rejects_empty_or_overlong_content(body):
    with pytest.raises(ValueError):
        create_event_announcement(
            FakeClient(),
            "event-1",
            "coordinator@example.edu",
            body,
        )


def test_list_and_delete_updates_are_scoped_to_event_and_coordinator():
    client = FakeClient()

    assert list_event_announcements(client, "event-1") == client.updates
    assert client.last_query.filters == [("event_id", "event-1")]

    delete_event_announcement(
        client,
        "update-1",
        "COORDINATOR@example.edu",
    )
    assert client.last_query.filters == [
        ("id", "update-1"),
        ("coordinator_email", "coordinator@example.edu"),
    ]
