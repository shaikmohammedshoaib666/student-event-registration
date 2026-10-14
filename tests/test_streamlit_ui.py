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

    def limit(self, *_args):
        return self

    def insert(self, *_args):
        return self

    def execute(self):
        if self.table == "events":
            return FakeResult([self.event] if self.event else [])
        if self.table == "event_registration_counts":
            if not self.event:
                return FakeResult([])
            return FakeResult([{"event_id": self.event["id"], "registration_count": 0}])
        if self.table in (
            "event_photos",
            "registrations",
            "event_conversations",
            "event_messages",
        ):
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
        "allow_team_registration": True,
        "max_team_size": 4,
        "coordinators": [
            {
                "name": "Jordan Coordinator",
                "email": "coordinator@example.edu",
                "phone": "+15551234567",
            }
        ],
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
    assert app.radio[0].options == [
        "Events",
        "Student account",
        "Messages",
        "Admin login / dashboard",
    ]
    assert any("Campus welcome" in block.value for block in app.markdown)
    assert any(selectbox.label == "Meal choice *" for selectbox in app.selectbox)
    assert any(
        selectbox.label == "How many people are registering? (including you)"
        and selectbox.options == ["1 person", "2 people", "3 people", "4 people"]
        for selectbox in app.selectbox
    )
    team_size_select = next(
        selectbox
        for selectbox in app.selectbox
        if selectbox.label == "How many people are registering? (including you)"
    )
    team_size_select.set_value(4)
    app.run()
    assert not app.exception
    assert any(
        input_widget.key == "team-member-id-event-1-student-1-4"
        for input_widget in app.text_input
    )
    assert any(link.label == "Call" for link in app.get("link_button"))
    assert any(link.label == "WhatsApp" for link in app.get("link_button"))
    assert any("Jordan Coordinator" in block.value for block in app.markdown)


def test_admin_dashboard_exposes_admin_login_route(monkeypatch):
    event = {
        "id": "event-1",
        "title": "Campus welcome",
        "description": "Welcome to campus",
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "venue": "Main Hall",
        "capacity": 40,
        "published": False,
        "registration_fields": [],
        "coordinators": [],
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
    app.session_state["app_section"] = "Admin login / dashboard"

    app.run()

    assert not app.exception
    assert any(text.label == "Admin email" for text in app.text_input)
    assert any(text.label == "Admin password" for text in app.text_input)

    app.session_state["admin_email"] = "admin@example.edu"
    app.session_state["event-admin-task"] = "Manage events & photos"
    app.run()

    assert not app.exception
    assert any(
        uploader.label == "Choose event photos" for uploader in app.get("file_uploader")
    )
    assert any(button.label == "Upload photos" for button in app.button)
    assert any(
        "Event coordinators" in item.value for item in app.markdown
    )
    assert any(
        "Event coordinators" in item.value for item in app.markdown
    )


def test_empty_events_page_points_organizers_to_admin_login(monkeypatch):
    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda *_args, **_kwargs: FakeClient(None),
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
            "ADMIN_USERS": {"admin@example.edu": "a-long-test-admin-password"},
        }
    )

    app.run()

    assert not app.exception
    assert any("No upcoming events" in item.value for item in app.info)
    assert any("Admin login / dashboard" in item.value for item in app.markdown)


def test_message_section_explains_student_and_coordinator_account_login(monkeypatch):
    event = {
        "id": "event-1",
        "title": "Campus welcome",
        "description": "Welcome to campus",
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "venue": "Main Hall",
        "capacity": 40,
        "published": True,
        "registration_fields": [],
        "coordinators": [],
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
            "ADMIN_USERS": {"admin@example.edu": "a-long-test-admin-password"},
        }
    )
    app.session_state["app_section"] = "Messages"

    app.run()

    assert not app.exception
    assert any("Sign in or create a student account" in item.value for item in app.info)
