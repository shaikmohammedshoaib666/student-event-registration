"""Student-friendly event discovery and registration, backed by Supabase."""

from datetime import datetime, time, timezone
from typing import Any, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
from supabase import Client, create_client
from streamlit.errors import StreamlitSecretNotFoundError

from event_app.admin_auth import admin_configuration_error, authenticate_admin
from event_app.exports import registrations_csv
from event_app.student_auth import (
    clear_student_session,
    current_student,
    persist_auth_session,
    sign_in_student,
    sign_up_student,
)
from event_app.supabase_data import (
    create_registration,
    delete_photo_record,
    list_events,
    list_photos,
    list_registrations,
    registration_counts,
    save_event,
    save_photo_record,
)
from event_app.validation import validate_registration


st.set_page_config(
    page_title="Campus Connect | Student Events",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
    :root { --ink: #17243b; --muted: #68758a; --brand: #4b5ce2; --mint: #e8f5f0; }
    .stApp { background: #f7f8fc; color: var(--ink); font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif; letter-spacing: -0.035em; }
    .hero { padding: 2.5rem 0 1.3rem; }
    .eyebrow { color: var(--brand); font-size: .8rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .hero h1 { font-size: clamp(2.5rem, 6vw, 4.2rem); line-height: 1.05; margin: .55rem 0; color: var(--ink); }
    .hero p { color: var(--muted); font-size: 1.1rem; max-width: 690px; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: white; border-radius: 18px; border-color: #e9ecf4; }
    [data-testid="stMetric"] { background: var(--mint); padding: .8rem 1rem; border-radius: 12px; }
    .tag { color: #3546c6; font-weight: 700; background: #eef0ff; padding: .3rem .65rem; border-radius: 99px; font-size: .82rem; }
    div.stButton > button[kind="primary"] { background: var(--brand); border-color: var(--brand); }
    @media (max-width: 640px) { .hero { padding-top: 1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def secret_value(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default


def get_supabase_client() -> Client:
    url = secret_value("SUPABASE_URL")
    key = secret_value("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY to Streamlit secrets."
        )
    return create_client(url, key)


def get_auth_client() -> Client:
    url = secret_value("SUPABASE_URL")
    key = secret_value("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Student accounts are not configured. Add SUPABASE_URL and "
            "SUPABASE_PUBLISHABLE_KEY to Streamlit secrets."
        )
    return create_client(url, key)


def configured_timezone() -> ZoneInfo:
    timezone_name = secret_value("APP_TIMEZONE", "UTC")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(f"APP_TIMEZONE must be a valid IANA time zone; received {timezone_name!r}.") from error


def format_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(configured_timezone()).strftime("%A, %B %-d · %-I:%M %p %Z")


def error_message(error: Exception) -> str:
    detail = str(error).lower()
    if (
        "duplicate key" in detail
        or "unique_event_student" in detail
        or "unique_event_user" in detail
        or "registrations_event_id_student_id_key" in detail
    ):
        return "You're already registered for this event with that student ID."
    if "event_registration_full" in detail:
        return "Sorry, this event just reached capacity. Please check out another event."
    if "event_not_open" in detail:
        return "Registration for this event is closed."
    return "We couldn't complete that request. Please try again in a moment."


def event_save_error(error: Exception) -> str:
    if "capacity_below_registration_count" in str(error).lower():
        return "Capacity can't be lower than the number of students already registered."
    return "We couldn't save the event. Please check the details and try again."


def show_event_card(event: dict[str, Any], count: int) -> None:
    with st.container(border=True):
        col_text, col_action = st.columns([4, 1])
        with col_text:
            st.markdown(f"### {event['title']}")
            st.markdown(
                f"📅 {format_datetime(event['starts_at'])}  ·  📍 {event['venue']}"
            )
            remaining = max(int(event["capacity"]) - count, 0)
            st.caption(f"{remaining} of {event['capacity']} spots left")
        with col_action:
            if st.button("Details", key=f"details-{event['id']}", use_container_width=True):
                st.session_state["selected_event_id"] = event["id"]


def show_registration_form(
    client: Client,
    event: dict[str, Any],
    count: int,
    student_user: Optional[Any],
) -> None:
    capacity = int(event["capacity"])
    if count >= capacity:
        st.warning("This event is full and registration is closed.")
        return
    if student_user is None:
        st.info("Create a student account or sign in to register for this event.")
        return

    metadata = student_user.user_metadata or {}
    student, errors = validate_registration(
        metadata.get("student_name", ""),
        metadata.get("student_id", ""),
        student_user.email or "",
        metadata.get("phone", ""),
    )
    if errors or student is None:
        st.error("Your student account profile is incomplete. Please contact an administrator.")
        return

    st.caption(f"Registering as **{student['student_name']}** · {student['student_id']} · {student['email']}")
    if student.get("phone"):
        st.caption(f"Phone: {student['phone']}")
    st.markdown("#### Save your spot")
    with st.form(f"register-{event['id']}-{student_user.id}"):
        submitted = st.form_submit_button(
            "Register for this event",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        try:
            create_registration(client, event["id"], student, student_user.id)
            st.success("You're in! Your registration has been saved.")
            st.rerun()
        except Exception as error:
            st.error(error_message(error))


def show_event_detail(
    client: Client,
    event: dict[str, Any],
    count: int,
    student_user: Optional[Any],
) -> None:
    st.markdown("---")
    if st.button("← Back to all events", key="back-to-events"):
        st.session_state.pop("selected_event_id", None)
        st.rerun()
    with st.container(border=True):
        st.markdown(f"## {event['title']}")
        st.markdown(
            f"**📅 {format_datetime(event['starts_at'])}**  ·  **📍 {event['venue']}**"
        )
        st.write(event["description"])
        left, right = st.columns([2, 1])
        with left:
            try:
                photos = list_photos(client, event["id"])
            except Exception:
                st.warning("Event photos are temporarily unavailable.")
                photos = []
            if photos:
                st.image([photo["public_url"] for photo in photos], use_container_width=True)
        with right:
            st.metric("Spots remaining", max(int(event["capacity"]) - count, 0))
            show_registration_form(client, event, count, student_user)


def show_public_view(client: Client, student_user: Optional[Any]) -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Your campus, your community</div>
          <h1>Find your next<br>favorite thing.</h1>
          <p>Meet people, try something new, and make campus memories. Your next event is just around the corner.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        events = list_events(client)
        counts = registration_counts(client)
    except Exception:
        st.error("We couldn't load events right now. Please refresh the page or try again later.")
        return

    upcoming = [
        event for event in events
        if datetime.fromisoformat(event["starts_at"].replace("Z", "+00:00")) >= datetime.now(timezone.utc)
    ]
    st.markdown("### Upcoming on campus")
    if not upcoming:
        st.info("No upcoming events just yet. Check back soon!")
        return
    for event in upcoming:
        show_event_card(event, counts.get(event["id"], 0))

    selected_id = st.session_state.get("selected_event_id")
    if selected_id:
        event = next((item for item in upcoming if item["id"] == selected_id), None)
        if event:
            show_event_detail(client, event, counts.get(event["id"], 0), student_user)


def show_student_account(auth_client: Client, student_user: Optional[Any]) -> None:
    st.markdown("### Student account")
    if student_user:
        metadata = student_user.user_metadata or {}
        st.success(f"Signed in as {metadata.get('student_name', student_user.email)}")
        if st.button("Sign out of student account", key="student-sign-out"):
            try:
                auth_client.auth.sign_out()
            finally:
                clear_student_session(st.session_state)
            st.rerun()
        return

    if st.session_state.pop("student_auth_error", False):
        st.warning("Your student session couldn't be verified. Please sign in again.")
    sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account"])
    with sign_in_tab:
        with st.form("student-sign-in"):
            email = st.text_input("Email", key="student-login-email")
            password = st.text_input("Password", type="password", key="student-login-password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                response = sign_in_student(auth_client, email.strip().lower(), password)
                if not response.session:
                    st.error("Sign-in didn't return an active session. Confirm your email, then try again.")
                    return
                persist_auth_session(response.session, st.session_state)
                st.success("Signed in. You can now register for events.")
                st.rerun()
            except Exception:
                st.error("We couldn't sign you in. Check your email and password, then try again.")

    with create_account_tab:
        st.caption("Use one account to register for campus events. You can still browse events without signing in.")
        with st.form("student-create-account"):
            name = st.text_input("Full name", max_chars=100, key="student-signup-name")
            student_id = st.text_input("Student ID", max_chars=50, key="student-signup-id")
            email = st.text_input("Email", max_chars=254, key="student-signup-email")
            phone = st.text_input("Phone number (optional)", max_chars=30, key="student-signup-phone")
            password = st.text_input(
                "Password (at least 10 characters)",
                type="password",
                key="student-signup-password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="student-signup-confirm-password",
            )
            submitted = st.form_submit_button("Create student account", type="primary")
        if submitted:
            profile, errors = validate_registration(name, student_id, email, phone)
            if errors:
                for message in errors:
                    st.error(message)
            elif len(password) < 10:
                st.error("Choose a password with at least 10 characters.")
            elif password != confirm_password:
                st.error("The passwords don't match.")
            elif profile is None:
                st.error("Please check your student account details.")
            else:
                try:
                    response = sign_up_student(
                        auth_client,
                        profile["email"] or "",
                        password,
                        profile["student_name"],
                        profile["student_id"],
                        profile["phone"],
                    )
                    if response.session:
                        persist_auth_session(response.session, st.session_state)
                        st.success("Your account is ready. You can now register for events.")
                        st.rerun()
                    else:
                        st.success(
                            "Account created. Check your email for the confirmation link, "
                            "then sign in here."
                        )
                except Exception:
                    st.error(
                        "We couldn't create that account. Check the details; if this email "
                        "is already registered, sign in instead."
                    )


def is_admin_authenticated() -> bool:
    try:
        configured_admins = st.secrets.get("ADMIN_USERS", {})
    except StreamlitSecretNotFoundError:
        configured_admins = {}
    configuration_error = admin_configuration_error(configured_admins)
    if configuration_error:
        st.error(f"Admin access is disabled. {configuration_error}")
        return False
    return bool(st.session_state.get("admin_email"))


def show_admin_login() -> bool:
    if is_admin_authenticated():
        top_left, top_right = st.columns([5, 1])
        with top_left:
            st.caption(f"Signed in as {st.session_state['admin_email']}")
        with top_right:
            if st.button("Sign out", key="admin-sign-out"):
                st.session_state.pop("admin_email", None)
                st.rerun()
        return True

    st.markdown("Sign in with your administrator email and password to manage campus events.")
    with st.form("admin-login"):
        email = st.text_input("Admin email")
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        try:
            configured_admins = st.secrets.get("ADMIN_USERS", {})
        except StreamlitSecretNotFoundError:
            configured_admins = {}
        if authenticate_admin(configured_admins, email, password):
            st.session_state["admin_email"] = email.strip().lower()
            st.rerun()
        st.error("That email and password didn't match an administrator account.")
    return False


def event_form(
    *,
    event: Optional[dict[str, Any]] = None,
    key: str,
) -> tuple[bool, dict[str, Any]]:
    default_title = event["title"] if event else ""
    default_description = event["description"] if event else ""
    default_venue = event["venue"] if event else ""
    default_capacity = int(event["capacity"]) if event else 50
    default_published = bool(event["published"]) if event else False
    if event:
        starts = datetime.fromisoformat(event["starts_at"].replace("Z", "+00:00")).astimezone(
            configured_timezone()
        )
        default_date, default_time = starts.date(), starts.time().replace(tzinfo=None, second=0, microsecond=0)
    else:
        default_date, default_time = datetime.now(configured_timezone()).date(), time(17, 0)

    with st.form(key):
        title = st.text_input("Event title", value=default_title, max_chars=150)
        description = st.text_area("Description", value=default_description, max_chars=5000, height=120)
        venue = st.text_input("Venue", value=default_venue, max_chars=200)
        date_col, time_col, capacity_col = st.columns(3)
        with date_col:
            event_date = st.date_input("Date", value=default_date)
        with time_col:
            timezone_name = secret_value("APP_TIMEZONE", "UTC")
            event_time = st.time_input(f"Start time ({timezone_name})", value=default_time)
        with capacity_col:
            capacity = st.number_input("Capacity", min_value=1, max_value=100000, value=default_capacity, step=1)
        published = st.checkbox("Published (visible to students)", value=default_published)
        submitted = st.form_submit_button("Save event", type="primary")

    values = {
        "title": title.strip(),
        "description": description.strip(),
        "venue": venue.strip(),
        "capacity": int(capacity),
        "published": published,
        "starts_at": (
            datetime.combine(event_date, event_time)
            .replace(tzinfo=configured_timezone())
            .isoformat()
        ),
    }
    return submitted, values


def upload_event_photos(client: Client, event_id: str, files: list[Any]) -> None:
    bucket = secret_value("SUPABASE_STORAGE_BUCKET", "event-photos")
    storage = client.storage.from_(bucket)
    for uploaded in files:
        suffix = uploaded.name.rsplit(".", 1)[-1].lower()
        path = f"{event_id}/{uuid4().hex}.{suffix}"
        storage.upload(
            path,
            uploaded.getvalue(),
            {"content-type": uploaded.type or "application/octet-stream", "upsert": "false"},
        )
        save_photo_record(client, event_id, path, storage.get_public_url(path))


def show_event_admin(client: Client, events: list[dict[str, Any]]) -> None:
    st.markdown("#### Create an event")
    submitted, values = event_form(key="create-event")
    if submitted:
        if not values["title"] or not values["description"] or not values["venue"]:
            st.error("Add an event title, description, and venue before saving.")
        else:
            try:
                saved = save_event(client, values)
                st.success(f"Created “{saved['title']}”.")
                st.rerun()
            except Exception as error:
                st.error(event_save_error(error))

    if not events:
        return
    st.markdown("---")
    st.markdown("#### Update an event")
    labels = {f"{event['title']} · {event['id'][:8]}": event for event in events}
    selected_label = st.selectbox("Choose an event", options=list(labels))
    selected = labels[selected_label]
    submitted, values = event_form(event=selected, key=f"update-event-{selected['id']}")
    if submitted:
        if not values["title"] or not values["description"] or not values["venue"]:
            st.error("Add an event title, description, and venue before saving.")
        else:
            try:
                save_event(client, values, selected["id"])
                st.success("Event updated.")
                st.rerun()
            except Exception as error:
                st.error(event_save_error(error))

    st.markdown("#### Event photos")
    uploads = st.file_uploader(
        "Upload event photos (PNG, JPG, or WebP)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"photos-{selected['id']}",
    )
    if uploads and st.button("Upload photos", key=f"upload-{selected['id']}"):
        try:
            upload_event_photos(client, selected["id"], uploads)
            st.success("Photos uploaded.")
            st.rerun()
        except Exception:
            st.error("Photo upload failed. Check Supabase Storage setup and try again.")
    try:
        photos = list_photos(client, selected["id"])
    except Exception:
        st.error("We couldn't load this event's photos.")
        photos = []
    for photo in photos:
        image_col, delete_col = st.columns([4, 1])
        with image_col:
            st.image(photo["public_url"], width=320)
        with delete_col:
            if st.button("Remove", key=f"remove-photo-{photo['id']}"):
                try:
                    client.storage.from_(secret_value("SUPABASE_STORAGE_BUCKET", "event-photos")).remove(
                        [photo["storage_path"]]
                    )
                    delete_photo_record(client, photo["id"])
                    st.rerun()
                except Exception:
                    st.error("We couldn't remove that photo. Please try again.")


def show_registration_admin(client: Client, events: list[dict[str, Any]]) -> None:
    st.markdown("#### Registrations")
    if not events:
        st.info("Create an event first to see its registrations.")
        return
    event_labels = {f"{event['title']} · {event['id'][:8]}": event for event in events}
    label = st.selectbox("Event registrations", options=list(event_labels), key="registration-event")
    event = event_labels[label]
    try:
        rows = list_registrations(client, event["id"])
    except Exception:
        st.error("We couldn't load registrations for this event.")
        return
    st.caption(f"{len(rows)} registered · capacity {event['capacity']}")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.download_button(
            "Download registrations as CSV",
            data=registrations_csv(rows),
            file_name=f"registrations-{event['id'][:8]}.csv",
            mime="text/csv",
            type="primary",
        )
    else:
        st.info("No students have registered for this event yet.")


def show_admin_view(client: Client) -> None:
    st.markdown("### Event administrator")
    if not show_admin_login():
        return
    try:
        events = list_events(client, published_only=False)
    except Exception:
        st.error("We couldn't load admin data. Check your Supabase configuration.")
        return
    event_tab, registration_tab = st.tabs(["Manage events", "Registrations"])
    with event_tab:
        show_event_admin(client, events)
    with registration_tab:
        show_registration_admin(client, events)


def main() -> None:
    st.markdown(
        '<div class="hero"><div class="eyebrow">CAMPUS CONNECT</div></div>',
        unsafe_allow_html=True,
    )
    try:
        client = get_supabase_client()
        auth_client = get_auth_client()
        configured_timezone()
    except Exception as error:
        st.error(str(error))
        st.info("Set up your Supabase project by following the instructions in README.md.")
        return

    student_user = current_student(auth_client, st.session_state)
    events_tab, account_tab, admin_tab = st.tabs(
        ["Discover events", "Student account", "Admin"]
    )
    with events_tab:
        show_public_view(client, student_user)
    with account_tab:
        show_student_account(auth_client, student_user)
    with admin_tab:
        show_admin_view(client)


if __name__ == "__main__":
    main()
