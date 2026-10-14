"""Student account operations using Supabase Auth."""

from typing import Any, Optional


def sign_up_student(
    auth_client: Any,
    email: str,
    password: str,
    student_name: str,
    student_id: str,
    phone: Optional[str],
) -> Any:
    return auth_client.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "student_name": student_name,
                    "student_id": student_id,
                    "phone": phone or "",
                }
            },
        }
    )


def sign_in_student(auth_client: Any, email: str, password: str) -> Any:
    return auth_client.auth.sign_in_with_password({"email": email, "password": password})


def persist_auth_session(session: Any, session_state: Any) -> None:
    session_state["student_access_token"] = session.access_token
    session_state["student_refresh_token"] = session.refresh_token
    session_state.pop("student_auth_error", None)


def current_student(auth_client: Any, session_state: Any) -> Optional[Any]:
    access_token = session_state.get("student_access_token")
    refresh_token = session_state.get("student_refresh_token")
    if not access_token or not refresh_token:
        return None

    try:
        session = auth_client.auth.set_session(access_token, refresh_token).session
        if session is None:
            clear_student_session(session_state)
            return None
        persist_auth_session(session, session_state)
        response = auth_client.auth.get_user(session.access_token)
        return response.user if response else None
    except Exception:
        clear_student_session(session_state)
        session_state["student_auth_error"] = True
        return None


def clear_student_session(session_state: Any) -> None:
    session_state.pop("student_access_token", None)
    session_state.pop("student_refresh_token", None)
    session_state.pop("account_chat_conversation_id", None)
    session_state.pop("selected_conversation_id", None)
