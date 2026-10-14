from event_app.student_auth import (
    clear_student_session,
    current_student,
    persist_auth_session,
    sign_in_student,
    sign_up_student,
)


class FakeAuth:
    def __init__(self):
        self.signup_credentials = None
        self.login_credentials = None
        self.user = None

    def sign_up(self, credentials):
        self.signup_credentials = credentials
        return "signup response"

    def sign_in_with_password(self, credentials):
        self.login_credentials = credentials
        return "login response"

    def set_session(self, access_token, refresh_token):
        return type(
            "AuthResponse",
            (),
            {
                "session": type(
                    "Session",
                    (),
                    {"access_token": access_token, "refresh_token": refresh_token},
                )()
            },
        )()

    def get_user(self, access_token):
        return type("UserResponse", (), {"user": self.user})()


class FakeAuthClient:
    def __init__(self):
        self.auth = FakeAuth()


def test_signup_saves_student_profile_as_supabase_auth_metadata():
    client = FakeAuthClient()

    sign_up_student(client, "ada@example.edu", "long-password", "Ada Lovelace", "STU-1", None)

    assert client.auth.signup_credentials["options"]["data"] == {
        "student_name": "Ada Lovelace",
        "student_id": "STU-1",
        "phone": "",
    }


def test_login_uses_supabase_email_password_auth():
    client = FakeAuthClient()

    sign_in_student(client, "ada@example.edu", "long-password")

    assert client.auth.login_credentials == {
        "email": "ada@example.edu",
        "password": "long-password",
    }


def test_student_session_is_verified_and_refresh_tokens_are_persisted():
    client = FakeAuthClient()
    client.auth.user = type("User", (), {"id": "user-1"})()
    state = {
        "student_access_token": "access-token",
        "student_refresh_token": "refresh-token",
    }

    user = current_student(client, state)

    assert user.id == "user-1"
    assert state["student_access_token"] == "access-token"
    assert state["student_refresh_token"] == "refresh-token"


def test_clearing_student_session_removes_both_tokens():
    state = {"student_access_token": "access", "student_refresh_token": "refresh"}

    clear_student_session(state)

    assert state == {}
