"""Student-friendly event discovery and registration, backed by Supabase."""

from datetime import datetime, time, timezone
from typing import Any, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
import pandas as pd
from supabase import Client, create_client
from streamlit.errors import StreamlitSecretNotFoundError

from event_app.admin_auth import admin_configuration_error, authenticate_admin
from event_app.announcements import (
    create_event_announcement,
    delete_event_announcement,
    list_event_announcements,
)
from event_app.backend_errors import backend_error_message
from event_app.chat import (
    get_student_conversation,
    get_or_create_conversation,
    list_conversations,
    list_messages,
    signed_chat_image_url,
    send_message,
    upload_chat_image,
)
from event_app.exports import registrations_csv
from event_app.registration_forms import (
    coordinator_editor_rows,
    editor_rows,
    flatten_registration,
    validate_coordinators,
    validate_registration_answers,
    validate_registration_fields,
)
from event_app.student_auth import (
    clear_student_session,
    current_student,
    persist_auth_session,
    sign_in_student,
    sign_up_student,
)
from event_app.supabase_data import (
    create_registration,
    delete_event,
    delete_photo_record,
    list_events,
    list_photos,
    list_registrations,
    list_student_registrations,
    registration_counts,
    save_event,
    save_photo_record,
)
from event_app.team_registration import validate_team_members
from event_app.validation import validate_registration


st.set_page_config(
    page_title="Campus Connect | Student Events",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
    :root { --ink: #17243b; --muted: #68758a; --brand: #4b5ce2; --mint: #e8f5f0; }
    .stApp { background: #f7f8fc; color: var(--ink); font-family: 'DM Sans', sans-serif; }
    .stApp, .stApp [data-testid="stMarkdownContainer"], .stApp label,
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
        color: var(--ink);
    }
    .stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div,
    .stApp [data-testid="stDateInput"] input, .stApp [data-testid="stTimeInput"] input {
        background-color: #ffffff !important;
        color: #17243b !important;
        border-color: #cbd3e2 !important;
    }
    .stApp input::placeholder, .stApp textarea::placeholder { color: #68758a !important; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif; letter-spacing: -0.035em; }
    .hero { padding: 2.5rem 0 1.3rem; }
    .eyebrow { color: var(--brand); font-size: .8rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .hero h1 { font-size: clamp(2.5rem, 6vw, 4.2rem); line-height: 1.05; margin: .55rem 0; color: var(--ink); }
    .hero p { color: var(--muted); font-size: 1.1rem; max-width: 690px; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: white; border-radius: 18px; border-color: #e9ecf4; }
    [data-testid="stMetric"] { background: var(--mint); padding: .8rem 1rem; border-radius: 12px; }
    [data-testid="stSidebar"] { background: #eef1fb; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #17243b !important; }
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


APP_SECTIONS = (
    "Events",
    "Student account",
    "Messages",
    "Admin login / dashboard",
)


def request_navigation(section: str) -> None:
    st.session_state["pending_app_section"] = section
    st.rerun()


def apply_pending_navigation() -> None:
    section = st.session_state.pop("pending_app_section", None)
    if section in APP_SECTIONS:
        st.session_state["app_section"] = section


def show_conversation_thread(
    client: Client,
    student_user: Any,
    conversation: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    email = (student_user.email or "").strip().lower()
    event = conversation.get("events") or {}
    other_person = (
        conversation["coordinator_email"]
        if conversation["student_user_id"] == student_user.id
        else (
            f"{conversation.get('student_name') or 'Student'} · "
            f"ID {conversation.get('student_id') or 'not provided'} "
            f"({conversation['student_email']})"
        )
    )
    st.caption(f"{event.get('title', 'Event')} · with {other_person}")
    try:
        messages = list_messages(client, conversation["id"])
    except Exception as error:
        st.error(f"Couldn't load messages. {backend_error_message(error)}")
        return

    for message in messages:
        is_current_user = message["sender_user_id"] == student_user.id
        with st.chat_message("user" if is_current_user else "assistant"):
            st.caption(
                "You" if is_current_user else message.get("sender_email", "Participant")
            )
            if message.get("body"):
                st.write(message["body"])
            if message.get("attachment_path"):
                try:
                    image_url = signed_chat_image_url(client, message["attachment_path"])
                    st.image(image_url, caption="Photo attachment", width=420)
                except Exception as error:
                    st.warning(f"Couldn't load this photo. {backend_error_message(error)}")
            st.caption(message["created_at"])

    with st.form(
        f"send-message-{key_prefix}-{conversation['id']}",
        clear_on_submit=True,
    ):
        body = st.text_area(
            "Message",
            max_chars=4000,
            height=90,
            key=f"message-body-{key_prefix}-{conversation['id']}",
        )
        attachment = st.file_uploader(
            "Attach a photo (optional, up to 5 MB)",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"chat-photo-{key_prefix}-{conversation['id']}",
        )
        send = st.form_submit_button("Send message", type="primary")
    if send:
        cleaned_body = body.strip()
        if not cleaned_body and attachment is None:
            st.warning("Write a message or attach a photo before sending.")
            return
        if attachment is not None and attachment.size > 5 * 1024 * 1024:
            st.error("Chat photos must be 5 MB or smaller.")
            return
        attachment_path = None
        try:
            if attachment is not None:
                attachment_path = upload_chat_image(
                    client,
                    conversation["id"],
                    student_user.id,
                    attachment,
                )
            send_message(
                client,
                conversation["id"],
                student_user.id,
                email,
                cleaned_body,
                attachment_path=attachment_path,
            )
            st.rerun()
        except Exception as error:
            if attachment_path:
                try:
                    client.storage.from_("chat-attachments").remove([attachment_path])
                except Exception as cleanup_error:
                    st.warning(
                        "The photo upload could not be cleaned up after the message failed. "
                        f"{backend_error_message(cleanup_error)}"
                    )
            st.error(f"Couldn't send this message. {backend_error_message(error)}")


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
    if "duplicate_team_student_id" in detail:
        return "A student ID in this team is already registered for this event."
    if "invalid_team_registration" in detail:
        return "Check the team size and each teammate's details, then try again."
    if "event_teams_not_allowed" in detail:
        return "This event does not accept team registrations."
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
    return f"We couldn't save the event. {backend_error_message(error)}"


def coordinator_display_name(event: dict[str, Any], coordinator_email: str) -> str:
    normalized_email = coordinator_email.strip().lower()
    for coordinator in event.get("coordinators") or []:
        if str(coordinator.get("email") or "").strip().lower() == normalized_email:
            return str(coordinator.get("name") or "").strip() or "Event coordinator"
    return "Event coordinator"


def show_event_card(event: dict[str, Any], count: Optional[int]) -> None:
    with st.container(border=True):
        col_text, col_action = st.columns([4, 1])
        with col_text:
            st.markdown(f"### {event['title']}")
            st.markdown(
                f"📅 {format_datetime(event['starts_at'])}  ·  📍 {event['venue']}"
            )
            if count is None:
                st.caption("Availability temporarily unavailable")
            else:
                remaining = max(int(event["capacity"]) - count, 0)
                st.caption(f"{remaining} of {event['capacity']} spots left")
        with col_action:
            if st.button("Details", key=f"details-{event['id']}", use_container_width=True):
                st.session_state["selected_event_id"] = event["id"]


def show_registration_form(
    client: Client,
    event: dict[str, Any],
    count: Optional[int],
    student_user: Optional[Any],
) -> None:
    capacity = int(event["capacity"])
    if count is None:
        st.warning("Registration availability is temporarily unavailable. Please try again shortly.")
        return
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
    fields = event.get("registration_fields") or []
    answers = {}
    allow_teams = bool(event.get("allow_team_registration", False))
    maximum_team_size = max(2, min(int(event.get("max_team_size", 4)), 8))
    remaining = max(capacity - count, 0)
    team_sizes = list(range(1, min(maximum_team_size, remaining) + 1))
    team_size = 1
    if allow_teams:
        team_size = st.selectbox(
            "How many people are registering? (including you)",
            options=team_sizes,
            format_func=lambda size: f"{size} " + ("person" if size == 1 else "people"),
            key=f"team-size-{event['id']}-{student_user.id}",
        )
        if team_size > 1:
            st.caption(
                f"You are the team lead. Enter the details for the other "
                f"{team_size - 1} team member(s). This reserves {team_size} event spots."
            )
    with st.form(f"register-{event['id']}-{student_user.id}"):
        member_rows = []
        if team_size > 1:
            for index in range(2, team_size + 1):
                st.markdown(f"##### Team member {index}")
                member_name = st.text_input(
                    "Full name",
                    key=f"team-member-name-{event['id']}-{student_user.id}-{index}",
                )
                member_student_id = st.text_input(
                    "Student ID",
                    key=f"team-member-id-{event['id']}-{student_user.id}-{index}",
                )
                member_email = st.text_input(
                    "Email",
                    key=f"team-member-email-{event['id']}-{student_user.id}-{index}",
                )
                member_phone = st.text_input(
                    "Phone (optional)",
                    key=f"team-member-phone-{event['id']}-{student_user.id}-{index}",
                )
                member_rows.append(
                    {
                        "Name": member_name,
                        "Student ID": member_student_id,
                        "Email": member_email,
                        "Phone": member_phone,
                    }
                )
        for index, field in enumerate(fields):
            key = f"registration-answer-{event['id']}-{student_user.id}-{index}"
            label = field["label"] + (" *" if field.get("required") else "")
            if field["type"] == "textarea":
                answers[field["label"]] = st.text_area(label, max_chars=3000, key=key)
            elif field["type"] == "select":
                options = field.get("options", [])
                selection = st.selectbox(
                    label,
                    options=[""] + options,
                    format_func=lambda option: option or "Select an option",
                    key=key,
                )
                answers[field["label"]] = selection or None
            elif field["type"] == "checkbox":
                answers[field["label"]] = st.checkbox(label, key=key)
            else:
                answers[field["label"]] = st.text_input(label, max_chars=500, key=key)
        submitted = st.form_submit_button(
            "Register for this event",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        team_members, team_errors = validate_team_members(
            member_rows,
            team_size=team_size,
            leader_student_id=student["student_id"],
        )
        if team_errors:
            for message in team_errors:
                st.error(message)
            return
        answer_errors = validate_registration_answers(fields, answers)
        if answer_errors:
            for message in answer_errors:
                st.error(message)
            return
        try:
            create_registration(
                client,
                event["id"],
                student,
                student_user.id,
                answers,
                team_size=team_size,
                team_members=team_members or [],
            )
            st.success(
                f"You're in! Your registration for {team_size} "
                f"{'person' if team_size == 1 else 'people'} has been saved."
            )
            st.rerun()
        except Exception as error:
            st.error(error_message(error))


def show_event_detail(
    client: Client,
    event: dict[str, Any],
    count: Optional[int],
    student_user: Optional[Any],
    student_email: Optional[str],
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
        st.markdown("#### Coordinator updates")
        try:
            announcements = list_event_announcements(client, event["id"])
        except Exception as error:
            st.error(
                f"Couldn't load coordinator updates. {backend_error_message(error)}"
            )
            announcements = []
        if announcements:
            for announcement in announcements:
                with st.container(border=True):
                    st.write(announcement["body"])
                    st.caption(
                        f"Posted by "
                        f"{coordinator_display_name(event, announcement['coordinator_email'])} · "
                        f"{announcement['created_at']}"
                    )
        else:
            st.caption("No coordinator updates yet.")
        coordinators = event.get("coordinators") or []
        if coordinators:
            st.markdown("#### Event coordinators")
            for index, coordinator in enumerate(coordinators):
                name = coordinator.get("name", "Event coordinator")
                email = (coordinator.get("email") or "").strip().lower()
                phone = (coordinator.get("phone") or "").strip()
                contact_cols = st.columns([2, 1, 1, 2])
                contact_cols[0].markdown(f"**{name}**")
                if phone:
                    digits = "".join(character for character in phone if character.isdigit())
                    if digits:
                        contact_cols[1].link_button(
                            "Call",
                            f"tel:{phone}",
                        )
                        contact_cols[2].link_button(
                            "WhatsApp",
                            f"https://wa.me/{digits}",
                        )
                if email:
                    if student_user and student_email:
                        if contact_cols[3].button(
                            f"Chat with {name}",
                            key=f"chat-coordinator-{event['id']}-{index}",
                            type="primary",
                        ):
                            thread = get_or_create_conversation(
                                client,
                                event["id"],
                                student_user.id,
                                student_email,
                                (student_user.user_metadata or {}).get(
                                    "student_name",
                                    student_email,
                                ),
                                email,
                                (student_user.user_metadata or {}).get("student_id", ""),
                            )
                            st.session_state["selected_conversation_id"] = thread["id"]
                            request_navigation("Messages")
                    else:
                        contact_cols[3].caption("Sign in to message in the app")
                elif student_user:
                    st.caption(
                        f"{name} can be messaged in-app after the admin assigns their coordinator account email."
                    )
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
            st.metric(
                "Spots remaining",
                "—" if count is None else max(int(event["capacity"]) - count, 0),
            )
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
    except Exception as error:
        st.error(f"We couldn't load events. {backend_error_message(error)}")
        return
    try:
        counts = registration_counts(client)
    except Exception as error:
        counts = {}
        st.warning(
            "Events are available to browse, but registration availability could not be loaded. "
            + backend_error_message(error)
        )

    upcoming = [
        event for event in events
        if datetime.fromisoformat(event["starts_at"].replace("Z", "+00:00")) >= datetime.now(timezone.utc)
    ]
    st.markdown("### Upcoming on campus")
    if not upcoming:
        st.info("No upcoming events just yet. Check back soon!")
        st.markdown(
            "Are you organizing an event? Choose **Admin login / dashboard** in the left "
            "navigation, sign in with your configured admin email and password, and publish "
            "your first event."
        )
        return
    availability_loaded = bool(counts) or not events
    for event in upcoming:
        show_event_card(
            event,
            counts.get(event["id"], 0) if availability_loaded else None,
        )

    selected_id = st.session_state.get("selected_event_id")
    if selected_id:
        event = next((item for item in upcoming if item["id"] == selected_id), None)
        if event:
            show_event_detail(
                client,
                event,
                counts.get(event["id"], 0) if availability_loaded else None,
                student_user,
                getattr(student_user, "email", None),
            )


def show_student_account(
    auth_client: Client,
    data_client: Client,
    student_user: Optional[Any],
) -> None:
    st.markdown("### Student account")
    if student_user:
        metadata = student_user.user_metadata or {}
        st.success(f"Signed in as {metadata.get('student_name', student_user.email)}")
        st.markdown("#### My registrations")
        try:
            registrations = list_student_registrations(data_client, student_user.id)
        except Exception as error:
            st.error(
                f"We couldn't load your event registrations. {backend_error_message(error)}"
            )
            registrations = []
        if not registrations:
            st.info(
                "You haven't registered for an event yet. Browse Events, choose an "
                "event, and register to see your enrollment here."
            )
        for registration in registrations:
            event = registration.get("events") or {}
            title = event.get("title", "Campus event")
            team_size = int(registration.get("team_size") or 1)
            starts_at = event.get("starts_at")
            status = (
                "Completed"
                if starts_at
                and datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
                < datetime.now(timezone.utc)
                else "Enrolled"
            )
            with st.container(border=True):
                st.markdown(f"#### {title}")
                details = [f"**Status:** {status}"]
                if starts_at:
                    details.append(f"**When:** {format_datetime(starts_at)}")
                if event.get("venue"):
                    details.append(f"**Where:** {event['venue']}")
                details.append(
                    f"**Team:** {team_size} " + ("person" if team_size == 1 else "people")
                )
                st.markdown("  ·  ".join(details))
                teammates = registration.get("team_members") or []
                if teammates:
                    st.caption(
                        "Team members: "
                        + ", ".join(
                            f"{member.get('name')} ({member.get('student_id')})"
                            for member in teammates
                        )
                    )
                student_updates = []
                if event.get("published"):
                    try:
                        student_updates = list_event_announcements(
                            data_client,
                            registration["event_id"],
                        )
                    except Exception as error:
                        st.error(
                            "Couldn't load event updates. "
                            + backend_error_message(error)
                        )
                if student_updates:
                    with st.expander("Coordinator updates"):
                        for update in student_updates:
                            st.write(update["body"])
                            st.caption(
                                f"{coordinator_display_name(event, update['coordinator_email'])} · "
                                f"{update['created_at']}"
                            )
                for index, coordinator in enumerate(event.get("coordinators") or []):
                    coordinator_email = (
                        str(coordinator.get("email") or "").strip().lower()
                    )
                    coordinator_phone = str(coordinator.get("phone") or "").strip()
                    name = coordinator.get("name") or "Coordinator"
                    st.markdown(f"**Coordinator: {name}**")
                    contact_columns = st.columns(3)
                    digits = "".join(
                        character for character in coordinator_phone
                        if character.isdigit()
                    )
                    if coordinator_phone and digits:
                        contact_columns[0].link_button(
                            f"Call {name}",
                            f"tel:{coordinator_phone}",
                        )
                        contact_columns[1].link_button(
                            f"WhatsApp {name}",
                            f"https://wa.me/{digits}",
                        )
                    if coordinator_email:
                        if contact_columns[2].button(
                            "In-app chat",
                            key=f"account-chat-{registration['event_id']}-{coordinator_email}",
                            type="primary",
                        ):
                            try:
                                thread = get_or_create_conversation(
                                    data_client,
                                    registration["event_id"],
                                    student_user.id,
                                    (student_user.email or "").strip().lower(),
                                    metadata.get("student_name", student_user.email or ""),
                                    coordinator_email,
                                    metadata.get("student_id", ""),
                                )
                                st.session_state["selected_conversation_id"] = thread["id"]
                                st.session_state["account_chat_conversation_id"] = thread["id"]
                                st.rerun()
                            except Exception as error:
                                st.error(
                                    "Couldn't open coordinator chat. "
                                    + backend_error_message(error)
                                )
                    elif coordinator_phone:
                        st.caption(
                            "In-app chat is available when an admin assigns the "
                            "coordinator's account email."
                        )
                if st.button(
                    "View event",
                    key=f"account-event-{registration['event_id']}",
                ):
                    st.session_state["selected_event_id"] = registration["event_id"]
                    request_navigation("Events")
        inline_chat_id = st.session_state.get("account_chat_conversation_id")
        if inline_chat_id:
            try:
                conversation = get_student_conversation(
                    data_client,
                    inline_chat_id,
                    student_user.id,
                )
            except Exception as error:
                st.error(
                    f"Couldn't open your private chat. {backend_error_message(error)}"
                )
                conversation = None
            if conversation:
                with st.container(border=True):
                    st.markdown("#### In-app coordinator chat")
                    if st.button(
                        "Close chat",
                        key=f"close-account-chat-{inline_chat_id}",
                    ):
                        st.session_state.pop("account_chat_conversation_id", None)
                        st.rerun()
                    show_conversation_thread(
                        data_client,
                        student_user,
                        conversation,
                        key_prefix="student-account",
                    )
            else:
                st.session_state.pop("account_chat_conversation_id", None)
        if st.button("Sign out of student account", key="student-sign-out"):
            try:
                auth_client.auth.sign_out()
            finally:
                clear_student_session(st.session_state)
                st.session_state.pop("account_chat_conversation_id", None)
                st.session_state.pop("selected_conversation_id", None)
            st.rerun()
        return

    if st.session_state.pop("student_auth_error", False):
        st.warning("Your student session couldn't be verified. Please sign in again.")
    account_action = st.radio(
        "Choose an account action",
        ["Sign in", "Create account"],
        horizontal=True,
        key="student_account_action",
    )
    if account_action == "Sign in":
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

    else:
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


def show_messages(client: Client, student_user: Optional[Any]) -> None:
    st.title("Coordinator messages")
    if student_user is None:
        st.info(
            "Sign in or create a student account to message an event coordinator. "
            "Coordinators sign in with the account email assigned to their event."
        )
        return

    if st.button("Refresh messages", key="refresh-message-inbox"):
        st.rerun()

    email = (student_user.email or "").strip().lower()
    try:
        assigned_events = get_coordinator_events(client, email)
    except Exception as error:
        st.error(
            f"Couldn't load the coordinator workspace. {backend_error_message(error)}"
        )
        assigned_events = []
    if assigned_events:
        coordinator_tab, inbox_tab = st.tabs(
            ["Coordinator workspace", "Student / coordinator chats"]
        )
        with coordinator_tab:
            show_coordinator_workspace(client, email, assigned_events)
        with inbox_tab:
            show_chat_inbox(client, student_user, email)
    else:
        st.caption(
            "No coordinator events are assigned to this account yet. Ask an admin "
            "to assign this exact email to an event."
        )
        show_chat_inbox(client, student_user, email)


def show_chat_inbox(
    client: Client,
    student_user: Any,
    email: str,
) -> None:
    try:
        threads = list_conversations(client, student_user.id, email)
    except Exception as error:
        st.error(f"Couldn't load your conversations. {backend_error_message(error)}")
        return
    if not threads:
        st.info(
            "No messages yet. Open an event, select Details, then choose “Chat with” "
            "a coordinator."
        )
        return

    labels = {}
    for thread in threads:
        event = thread.get("events") or {}
        event_title = event.get("title", "Event")
        if thread["student_user_id"] == student_user.id:
            other_person = thread["coordinator_email"]
            role = "Coordinator"
        else:
            other_person = (
                f"{thread.get('student_name') or 'Student'} · "
                f"ID {thread.get('student_id') or 'not provided'} "
                f"({thread['student_email']})"
            )
            role = "Student"
        labels[
            f"{event_title} · {role}: {other_person} · {thread['id'][:8]}"
        ] = thread
    thread_labels = list(labels)
    preferred_id = st.session_state.get("selected_conversation_id")
    default_index = next(
        (
            index
            for index, label in enumerate(thread_labels)
            if labels[label]["id"] == preferred_id
        ),
        0,
    )
    selected_label = st.selectbox(
        "Conversation",
        thread_labels,
        index=default_index,
        key="selected-chat-thread",
    )
    conversation = labels[selected_label]
    st.session_state["selected_conversation_id"] = conversation["id"]
    show_conversation_thread(
        client,
        student_user,
        conversation,
        key_prefix="messages",
    )


def get_coordinator_events(
    client: Client,
    coordinator_email: str,
) -> list[dict[str, Any]]:
    events = list_events(client, published_only=False)
    return [
        event
        for event in events
        if any(
            str(coordinator.get("email") or "").strip().lower() == coordinator_email
            for coordinator in event.get("coordinators") or []
        )
    ]

def show_coordinator_workspace(
    client: Client,
    coordinator_email: str,
    assigned_events: list[dict[str, Any]],
) -> None:
    st.caption(
        "Your coordinator tools are limited to the events assigned to this account. "
        "Review participant rosters, answer student chats, and post public event updates."
    )
    for event in assigned_events:
        with st.expander(f"{event['title']} · {event['venue']}", expanded=True):
            st.caption(format_datetime(event["starts_at"]))
            try:
                registrations = list_registrations(client, event["id"])
            except Exception as error:
                st.error(
                    f"Couldn't load event registrations. {backend_error_message(error)}"
                )
                continue
            reserved_spots = sum(
                int(row.get("team_size") or 1) for row in registrations
            )
            st.caption(
                f"{len(registrations)} registration(s) · {reserved_spots} of "
                f"{event['capacity']} spots reserved"
            )
            if registrations:
                fields = event.get("registration_fields") or []
                st.dataframe(
                    [flatten_registration(row, fields) for row in registrations],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "No students have registered yet. Their chats will appear below "
                    "after they contact you."
                )

            if event.get("published"):
                st.markdown("#### Post a public update")
                with st.form(
                    f"coordinator-update-{event['id']}",
                    clear_on_submit=True,
                ):
                    update_body = st.text_area(
                        "Update visible to all students on the event page",
                        max_chars=2000,
                        key=f"coordinator-update-body-{event['id']}",
                    )
                    submitted = st.form_submit_button("Publish update", type="primary")
                if submitted:
                    try:
                        create_event_announcement(
                            client,
                            event["id"],
                            coordinator_email,
                            update_body,
                        )
                        st.success(
                            "Your update is now visible on the public event page."
                        )
                        st.rerun()
                    except Exception as error:
                        st.error(
                            "Couldn't publish this update. "
                            + backend_error_message(error)
                        )
            else:
                st.info("Public updates are available after the admin publishes this event.")

            try:
                announcements = list_event_announcements(client, event["id"])
            except Exception as error:
                st.error(
                    f"Couldn't load coordinator updates. {backend_error_message(error)}"
                )
                announcements = []
            if announcements:
                for announcement in announcements:
                    with st.container(border=True):
                        st.write(announcement["body"])
                        st.caption(
                            f"{announcement['coordinator_email']} · "
                            f"{announcement['created_at']}"
                        )
                        if announcement["coordinator_email"] == coordinator_email:
                            if st.button(
                                "Remove update",
                                key=f"remove-update-{announcement['id']}",
                            ):
                                try:
                                    delete_event_announcement(
                                        client,
                                        announcement["id"],
                                        coordinator_email,
                                    )
                                    st.rerun()
                                except Exception as error:
                                    st.error(
                                        "Couldn't remove this update. "
                                        + backend_error_message(error)
                                    )
            else:
                st.caption("No public updates have been posted for this event yet.")


def is_admin_authenticated() -> bool:
    try:
        configured_admins = st.secrets.get("ADMIN_USERS", {})
    except StreamlitSecretNotFoundError:
        configured_admins = {}
    configuration_error = admin_configuration_error(configured_admins)
    if configuration_error:
        st.error(f"Admin access is disabled. {configuration_error}")
        return False
    authenticated_email = st.session_state.get("admin_email", "")
    return any(
        str(configured_email).strip().lower() == authenticated_email
        for configured_email in configured_admins
    )


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
) -> tuple[bool, dict[str, Any], list[str]]:
    default_title = event["title"] if event else ""
    default_description = event["description"] if event else ""
    default_venue = event["venue"] if event else ""
    default_capacity = int(event["capacity"]) if event else 50
    default_published = bool(event["published"]) if event else False
    default_allow_teams = bool(event.get("allow_team_registration", False)) if event else False
    default_max_team_size = int(event.get("max_team_size", 4)) if event else 4
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
        allow_teams = st.checkbox(
            "Allow team registrations",
            value=default_allow_teams,
            help="A student can register as the team lead and enter each teammate's details.",
        )
        max_team_size = st.number_input(
            "Maximum team size (including the team lead)",
            min_value=2,
            max_value=8,
            value=max(2, min(default_max_team_size, 8)),
            step=1,
            disabled=not allow_teams,
        )
        published = st.checkbox("Published (visible to students)", value=default_published)
        st.markdown("##### Student registration questions")
        st.caption(
            "Add optional questions students answer when registering. For Dropdown, "
            "enter choices separated by commas."
        )
        question_rows = st.data_editor(
            pd.DataFrame(
                editor_rows(event.get("registration_fields", []) if event else []),
                columns=[
                    "Question",
                    "Answer type",
                    "Required",
                    "Dropdown choices (comma separated)",
                ],
            ),
            column_config={
                "Question": st.column_config.TextColumn("Question", required=True),
                "Answer type": st.column_config.SelectboxColumn(
                    "Answer type",
                    options=["Short answer", "Paragraph", "Dropdown", "Checkbox"],
                    required=True,
                ),
                "Required": st.column_config.CheckboxColumn("Required"),
                "Dropdown choices (comma separated)": st.column_config.TextColumn(
                    "Dropdown choices (comma separated)",
                    help="Only used for Dropdown questions.",
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            key=f"registration-fields-{key}",
        )
        st.markdown("##### Event coordinators")
        st.caption(
            "Assign a coordinator name and phone for direct calls/WhatsApp. Add their "
            "student-account email to enable in-app chat. Coordinators must create an "
            "account with that same email to receive messages."
        )
        coordinator_rows = st.data_editor(
            pd.DataFrame(
                coordinator_editor_rows(event.get("coordinators", []) if event else []),
                columns=["Name", "Email", "Phone"],
            ),
            column_config={
                "Name": st.column_config.TextColumn("Name", required=True),
                "Email": st.column_config.TextColumn("Account email for in-app chat"),
                "Phone": st.column_config.TextColumn("Phone (include country code)"),
            },
            num_rows="dynamic",
            hide_index=True,
            key=f"coordinator-contacts-{key}",
        )
        submitted = st.form_submit_button("Save event", type="primary")

    fields, field_errors = validate_registration_fields(question_rows.to_dict("records"))
    coordinators, coordinator_errors = validate_coordinators(
        coordinator_rows.to_dict("records")
    )
    values = {
        "title": title.strip(),
        "description": description.strip(),
        "venue": venue.strip(),
        "capacity": int(capacity),
        "allow_team_registration": allow_teams,
        "max_team_size": int(max_team_size),
        "published": published,
        "registration_fields": fields or [],
        "coordinators": coordinators or [],
        "starts_at": (
            datetime.combine(event_date, event_time)
            .replace(tzinfo=configured_timezone())
            .isoformat()
        ),
    }
    return submitted, values, field_errors + coordinator_errors


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
    event_task = st.radio(
        "Event tasks",
        ["Create event", "Manage events & photos"],
        horizontal=True,
        key="event-admin-task",
    )
    if event_task == "Create event":
        st.markdown("#### Create an event")
        submitted, values, field_errors = event_form(key="create-event")
        if submitted:
            if field_errors:
                for message in field_errors:
                    st.error(message)
            elif not values["title"] or not values["description"] or not values["venue"]:
                st.error("Add an event title, description, and venue before saving.")
            else:
                try:
                    saved = save_event(client, values)
                    st.success(
                        f"Created “{saved['title']}”. Choose “Manage events & photos” "
                        "to upload its event photos."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(event_save_error(error))
        return

    if not events:
        st.info("Create and save an event first. Then choose it here to upload photos.")
        return

    st.markdown("---")
    labels = {f"{event['title']} · {event['id'][:8]}": event for event in events}
    selected_label = st.selectbox("Choose an event", options=list(labels))
    selected = labels[selected_label]
    st.markdown("#### Event photos")
    st.caption(
        "Upload PNG, JPG, or WebP images here. After upload, photos appear on the "
        "student-facing event details."
    )
    uploads = st.file_uploader(
        "Choose event photos",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"photos-{selected['id']}",
    )
    upload_clicked = st.button(
        "Upload photos",
        key=f"upload-{selected['id']}",
        type="primary",
        disabled=not uploads,
    )
    if uploads and upload_clicked:
        try:
            upload_event_photos(client, selected["id"], uploads)
            st.success("Photos uploaded.")
            st.rerun()
        except Exception as error:
            st.error(f"Photo upload failed. {backend_error_message(error)}")
    try:
        photos = list_photos(client, selected["id"])
    except Exception as error:
        st.error(f"We couldn't load this event's photos. {backend_error_message(error)}")
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
                except Exception as error:
                    st.error(f"We couldn't remove that photo. {backend_error_message(error)}")

    st.markdown("---")
    st.markdown("#### Update event details")
    submitted, values, field_errors = event_form(
        event=selected,
        key=f"update-event-{selected['id']}",
    )
    if submitted:
        if field_errors:
            for message in field_errors:
                st.error(message)
        elif not values["title"] or not values["description"] or not values["venue"]:
            st.error("Add an event title, description, and venue before saving.")
        else:
            try:
                save_event(client, values, selected["id"])
                st.success("Event updated.")
                st.rerun()
            except Exception as error:
                st.error(event_save_error(error))

    st.markdown("---")
    with st.expander("Delete event permanently"):
        st.warning(
            "This permanently deletes the event, its registrations and team rosters, "
            "coordinator conversations, and stored event/chat photos. This cannot be undone."
        )
        confirm_delete = st.checkbox(
            f"I understand that “{selected['title']}” and its data will be deleted.",
            key=f"confirm-delete-event-{selected['id']}",
        )
        if st.button(
            "Delete event permanently",
            key=f"delete-event-{selected['id']}",
            type="primary",
            disabled=not confirm_delete,
        ):
            try:
                delete_event(
                    client,
                    selected["id"],
                    event_photo_bucket=secret_value(
                        "SUPABASE_STORAGE_BUCKET",
                        "event-photos",
                    ),
                )
                st.session_state.pop("selected_event_id", None)
                st.success("Event and its related data were deleted.")
                st.rerun()
            except Exception as error:
                st.error(
                    f"We couldn't completely delete this event. "
                    f"{backend_error_message(error)}"
                )


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
    except Exception as error:
        st.error(f"We couldn't load registrations. {backend_error_message(error)}")
        return
    reserved_spots = sum(int(row.get("team_size") or 1) for row in rows)
    st.caption(
        f"{len(rows)} registration(s) · {reserved_spots} spot(s) reserved · "
        f"capacity {event['capacity']}"
    )
    if rows:
        fields = event.get("registration_fields") or []
        export_rows = [flatten_registration(row, fields) for row in rows]
        st.dataframe(export_rows, use_container_width=True, hide_index=True)
        st.download_button(
            "Download registrations as CSV",
            data=registrations_csv(export_rows),
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
    st.caption("Create and publish events, manage photos and registration forms, and review student sign-ups.")
    try:
        events = list_events(client, published_only=False)
    except Exception as error:
        st.error(f"We couldn't load admin data. {backend_error_message(error)}")
        return
    admin_section = st.radio(
        "Admin tools",
        ["Manage events", "Registrations"],
        horizontal=True,
        key="admin_tool_section",
    )
    if admin_section == "Manage events":
        show_event_admin(client, events)
    else:
        show_registration_admin(client, events)


def main() -> None:
    apply_pending_navigation()
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
    st.sidebar.title("Campus Connect")
    st.sidebar.caption("Find campus events, register, and contact coordinators.")
    if student_user:
        profile = student_user.user_metadata or {}
        st.sidebar.success(
            f"Signed in: {profile.get('student_name', student_user.email)}"
        )
    else:
        st.sidebar.info("Browse events as a guest. Sign in to register and chat.")
    section = st.sidebar.radio(
        "Go to",
        list(APP_SECTIONS),
        key="app_section",
    )
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Admins: choose **Admin login / dashboard**. Students and coordinators "
        "sign in with their Supabase accounts."
    )

    if section == "Events":
        show_public_view(client, student_user)
    elif section == "Student account":
        show_student_account(auth_client, client, student_user)
    elif section == "Messages":
        show_messages(client, student_user)
    else:
        show_admin_view(client)


if __name__ == "__main__":
    main()
