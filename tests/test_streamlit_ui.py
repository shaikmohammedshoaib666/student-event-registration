from datetime import datetime, timedelta, timezone
from pathlib import Path

import supabase
from streamlit.testing.v1 import AppTest


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table, event):
        self.table = table
        self.event = event

    def select(self, *_args):
        return self

    def order(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        if self.table == "events":
            return FakeResult([self.event])
        if self.table == "event_registration_counts":
            return FakeResult(
                [{"event_id": self.event["id"], "registration_count": 0}]
            )
        if self.table in ("event_photos", "registrations"):
            return FakeResult([])
        raise AssertionError(f"Unexpected Supabase table: {self.table}")


class FakeAuth:
    def __init__(self, user):
        self.user = user

    def set_session(self, access_token, refresh_token):
        session = type(
            "Session",
            (),
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
        )()
        return type("AuthResponse", (), {"session": session})()

    def get_user(self, _access_token):
        return type("UserResponse", (), {"user": self.user})()


class FakeClient:
    def __init__(self, event):
        self.auth = FakeAuth(
            type(
                "User",
                (),
                {
                    "id": "student-1",
                    "email": "student@example.edu",
                    "user_metadata": {
                        "student_name": "Test Student",
                        "student_id": "STU-123",
                    },
                },
            )()
        )
        self.event = event

    def table(self, table):
        return FakeQuery(table, self.event)


def test_student_and_admin_views_render_with_event_registration_form(monkeypatch):
    event = {
        "id": "event-1",
        "title": "Campus welcome",
        "description": "Welcome to campus",
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "venue": "Main Hall",
        "capacity": 40,
        "published": True,
        "registration_fields": [
            {
                "label": "Meal choice",
                "type": "select",
                "required": True,
                "options": ["Vegan", "Vegetarian"],
            }
        ],
    }
    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda *_args, **_kwargs: FakeClient(event),
    )
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=20,
    )
    app.secrets.update(
        {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
            "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_test",
            "ADMIN_USERS": {
                "admin@example.edu": "a-long-test-admin-password",
            },
        }
    )
    app.session_state["admin_email"] = "admin@example.edu"
    app.session_state["selected_event_id"] = "event-1"
    app.session_state["student_access_token"] = "test-access-token"
    app.session_state["student_refresh_token"] = "test-refresh-token"

    app.run()

    assert not app.exception
    assert [tab.label for tab in app.tabs[:3]] == [
        "Discover events",
        "Student account",
        "Admin",
    ]
    assert any("Campus welcome" in block.value for block in app.markdown)
    assert any(selectbox.label == "Meal choice *" for selectbox in app.selectbox)
    assert len(app.dataframe) == 2
