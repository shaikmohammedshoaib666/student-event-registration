from datetime import datetime, timedelta, timezone
from pathlib import Path

import supabase
from streamlit.testing.v1 import AppTest


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table, event, registrations):
        self.table = table
        self.event = event
        self.registrations = registrations
        self.filters = []

    def select(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
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
        if self.table == "registrations":
            rows = self.registrations
            for column, value in self.filters:
                if column == "user_id":
                    rows = [row for row in rows if row.get("user_id") == value]
                elif column == "event_id":
                    rows = [row for row in rows if row.get("event_id") == value]
            return FakeResult(rows)
        if self.table in (
            "event_photos",
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
    def __init__(self, event, registrations=None):
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
        self.registrations = registrations or []

    def table(self, table):
        return FakeQuery(table, self.event, self.registrations)


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
        checkbox.label.startswith("I understand that")
        for checkbox in app.checkbox
    )
    assert any(
        button.label == "Delete event permanently" and button.disabled
        for button in app.button
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


def test_student_account_lists_enrollments_and_coordinator_chat(monkeypatch):
    event = {
        "id": "event-1",
        "title": "Campus welcome",
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "venue": "Main Hall",
        "capacity": 40,
        "published": True,
        "coordinators": [
            {
                "name": "Jordan Coordinator",
                "email": "coordinator@example.edu",
                "phone": "+15551234567",
            }
        ],
    }
    registrations = [
        {
            "event_id": "event-1",
            "user_id": "student-1",
            "student_name": "Test Student",
            "student_id": "STU-123",
            "email": "student@example.edu",
            "created_at": "2026-10-14T12:00:00Z",
            "team_size": 2,
            "team_members": [
                {
                    "name": "Teammate",
                    "student_id": "STU-456",
                    "email": "teammate@example.edu",
                }
            ],
            "events": event,
        }
    ]
    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda *_args, **_kwargs: FakeClient(event, registrations),
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
        }
    )
    app.session_state["app_section"] = "Student account"
    app.session_state["student_access_token"] = "test-access-token"
    app.session_state["student_refresh_token"] = "test-refresh-token"

    app.run()

    assert not app.exception
    assert any("Campus welcome" in item.value for item in app.markdown)
    assert any("Status:** Enrolled" in item.value for item in app.markdown)
    assert any("Team:** 2 people" in item.value for item in app.markdown)
    assert any("Teammate (STU-456)" in item.value for item in app.caption)
    assert any(button.label == "In-app chat" for button in app.button)
    assert any(link.label == "Call Jordan Coordinator" for link in app.get("link_button"))
    assert any(
        link.label == "WhatsApp Jordan Coordinator"
        for link in app.get("link_button")
    )


def test_assigned_coordinator_sees_only_scoped_workspace_on_messages(monkeypatch):
    event = {
        "id": "event-1",
        "title": "Campus welcome",
        "description": "Welcome to campus",
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "venue": "Main Hall",
        "capacity": 40,
        "published": True,
        "coordinators": [
            {
                "name": "Test Student",
                "email": "student@example.edu",
                "phone": "",
            }
        ],
        "registration_fields": [],
    }
    registrations = [
        {
            "event_id": "event-1",
            "student_name": "Registered Student",
            "student_id": "STU-456",
            "email": "registered@example.edu",
            "created_at": "2026-10-14T12:00:00Z",
            "team_size": 1,
            "team_members": [],
            "form_answers": {},
        }
    ]
    monkeypatch.setattr(
        supabase,
        "create_client",
        lambda *_args, **_kwargs: FakeClient(event, registrations),
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
        }
    )
    app.session_state["app_section"] = "Messages"
    app.session_state["student_access_token"] = "test-access-token"
    app.session_state["student_refresh_token"] = "test-refresh-token"

    app.run()

    assert not app.exception
    assert any("Coordinator workspace" in item.value for item in app.markdown)
    assert any("Registered Student" in str(frame.value) for frame in app.dataframe)
