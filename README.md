# Campus Connect

A student-friendly event discovery and registration app built with Streamlit and Supabase. Events, registrations, and event photos live in Supabase; the app does not use local or browser storage as its data source.

## Features

- Browse published upcoming events, event details, photos, venue, date/time, capacity, and available spaces.
- Students create an account with Supabase Auth using their name, student ID, email, and optional phone number; event details remain browsable without signing in, but registration requires a student account.
- Prevent duplicate registrations per event and student ID/account; database triggers serialize registrations and enforce capacity.
- Admins can enable team registration per event and set a maximum team size. A signed-in student can register as lead, enter each teammate's name, student ID, email, and optional phone, and reserve every team member's spot against event capacity.
- The admin dashboard can assign up to 10 coordinators to an event by name, phone, and Supabase account email. Students can tap to call or open WhatsApp from a phone, or use persisted in-app messages when the coordinator email is assigned.
- Coordinators sign in through the same Supabase student account flow, using the email assigned to the event; their inbox shows only threads addressed to that email.
- Each student has a separate event/coordinator conversation with text and private photo attachments (PNG, JPG, or WebP, up to 5 MB); photos are served with short-lived signed URLs.
- Admin-only event creation, editing, publishing/unpublishing, photo uploads/removals, editable signup questions, and per-event CSV registration exports.
- Admins can add up to 12 required/optional student registration questions per event (short answer, paragraph, dropdown, or checkbox); answers appear in the registration table and CSV export.
- Server-side-only Supabase service-role access with database row-level security enabled.

## Local setup

1. Use Python 3.9 or newer and create a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Create a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql) in its SQL Editor.
4. In Supabase **Project Settings → API Keys**, copy the project URL, a publishable key, and a server-side secret key. Student sign-up/sign-in uses the publishable key; database operations use the secret/service-role key, which bypasses row-level security. Keep the server-side key private.
5. In Supabase **Authentication → Providers → Email**, enable email/password sign-up. Choose whether student emails require confirmation; if confirmation is enabled, students must follow the confirmation link before signing in.
6. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`. Under `[ADMIN_USERS]`, replace the three example entries with one to three actual administrator emails and different, unique passwords of at least 16 characters. Set `APP_TIMEZONE` to the campus IANA time zone (for example, `America/New_York`); it defaults to UTC. Keep the secrets file out of version control.
7. Start the app: `streamlit run app.py`.

`SUPABASE_STORAGE_BUCKET` defaults to `event-photos`. The SQL script creates this public-read bucket with a 10 MB per-image limit for JPEG, PNG, and WebP uploads. Event photos are publicly viewable; do not upload sensitive images. It also creates a separate private `chat-attachments` bucket (5 MB max per image) for coordinator chat photos.

The app's server-side secret/service-role key remains on the Streamlit server and is never sent to student browsers. Student passwords are handled by Supabase Auth; verified user sessions are kept server-side, and each registration is tied to the authenticated Supabase user. Admin authentication is separate and supports up to three email/password pairs from the server-side `[ADMIN_USERS]` secrets table. Use actual admin email addresses and different passwords with at least 16 characters; no default credentials are enabled.

## App navigation and coordinators

The expanded sidebar has **Events**, **Student account**, **Messages**, and **Admin login / dashboard**. Admins choose **Admin login / dashboard** and sign in with an email/password pair configured in Streamlit Secrets under `[ADMIN_USERS]`; there is no admin signup form. The app is configured with a light theme and high-contrast white form fields. Students and coordinators use **Student account** with Supabase Auth. Signed-in students see their enrolled events, status, date/venue, team roster, and Call, WhatsApp, and in-app chat actions in **Student account**. To assign a coordinator, an admin adds the coordinator's name, phone (including country code), and the email they will use for a student account while creating or editing an event. An in-app chat requires the coordinator's account email; phone alone only provides Call/WhatsApp actions. A coordinator creates/signs into the account with the assigned email, then opens **Messages** to use the coordinator workspace: assigned-event registrations, participant details, and one-to-one student chats. Coordinators do not get admin event-editing controls. Each event/student/coordinator combination has its own thread; messages can include text and a private photo attachment. Messages are stored in Supabase and are not publicly visible, but this is not end-to-end encrypted like WhatsApp. Admin accounts are not automatically included in these private conversations. Use **Refresh messages** to check for replies.

In the admin dashboard, select **Manage events & photos**, choose a saved event, then use **Choose event photos** and **Upload photos**. An event must be saved before photos can be uploaded; uploaded event photos appear in student event details. The same section includes **Delete event permanently**. Deleting requires explicit confirmation and permanently removes the event, registrations/team rosters, conversations, and stored event/chat photos.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub and create a Community Cloud app for it, using `app.py` as the main file.
2. In the app's **Settings → Secrets**, add the same TOML keys shown in `.streamlit/secrets.toml.example`, using the project URL, publishable key, server-side service-role/secret key, the actual admin email/password pairs under `[ADMIN_USERS]`, and the campus IANA time zone.
3. Deploy and verify the public event list loads. Choose **Admin login / dashboard** in the visible left sidebar to sign in, then create/publish an event and upload a test photo.
4. Keep the service-role key exclusively in Streamlit Cloud secrets. Rotate it in Supabase if it is ever exposed.

## Database and security notes

The schema enables RLS on all application tables. Anonymous and authenticated roles can only read published event details and their public event photos; they cannot read registrations or write application data. Streamlit verifies students with Supabase Auth and performs database writes, chat participant filtering, and admin reads server-side. SQL constraints and triggers enforce valid capacities, unique event/student and event/account registrations, published-event registration, and capacity even when simultaneous submissions compete for the final place.

If you initialized the database using an earlier version of the schema, run the latest `supabase/schema.sql` in the SQL Editor to add student account linkage, registration answers, team-size settings and rosters, coordinator contacts, text/photo chat support, and both event-photo and private chat-photo storage buckets. The script requests a PostgREST schema-cache reload at the end. It is idempotent for these setup steps, but review migrations before applying schema changes to an existing production database. If you change the event photo bucket name in Streamlit secrets, update the bucket ID and storage policy in the SQL to match.

If the event list displays a database setup error, follow its specific guidance. A missing-table/column message means the latest schema has not been applied to the same Supabase project whose URL is in Streamlit Secrets. An invalid-key/permission message means to check the project URL and server-side key; re-run the schema after confirming the project.

## Tests

Run focused validation tests with `python -m pytest`.
