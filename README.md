# Campus Connect

A student-friendly event discovery and registration app built with Streamlit and Supabase. Events, registrations, and event photos live in Supabase; the app does not use local or browser storage as its data source.

## Features

- Browse published upcoming events, event details, photos, venue, date/time, capacity, and available spaces.
- Students create an account with Supabase Auth using their name, student ID, email, and optional phone number; event details remain browsable without signing in, but registration requires a student account.
- Prevent duplicate registrations per event and student ID/account; database triggers serialize registrations and enforce capacity.
- Admin-only event creation, editing, publishing/unpublishing, photo uploads/removals, and per-event CSV registration exports.
- Server-side-only Supabase service-role access with database row-level security enabled.

## Local setup

1. Use Python 3.9 or newer and create a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Create a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql) in its SQL Editor.
4. In Supabase **Project Settings → API Keys**, copy the project URL, a publishable key, and a server-side secret key. Student sign-up/sign-in uses the publishable key; database operations use the secret/service-role key, which bypasses row-level security. Keep the server-side key private.
5. In Supabase **Authentication → Providers → Email**, enable email/password sign-up. Choose whether student emails require confirmation; if confirmation is enabled, students must follow the confirmation link before signing in.
6. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`. Under `[ADMIN_USERS]`, replace the three example entries with one to three actual administrator emails and different, unique passwords of at least 16 characters. Set `APP_TIMEZONE` to the campus IANA time zone (for example, `America/New_York`); it defaults to UTC. Keep the secrets file out of version control.
7. Start the app: `streamlit run app.py`.

`SUPABASE_STORAGE_BUCKET` defaults to `event-photos`. The SQL script creates this public-read bucket with a 10 MB per-image limit for JPEG, PNG, and WebP uploads. Uploaded photos are publicly viewable; do not upload sensitive images.

The app's server-side secret/service-role key remains on the Streamlit server and is never sent to student browsers. Student passwords are handled by Supabase Auth; verified user sessions are kept server-side, and each registration is tied to the authenticated Supabase user. Admin authentication is separate and supports up to three email/password pairs from the server-side `[ADMIN_USERS]` secrets table. Use actual admin email addresses and different passwords with at least 16 characters; no default credentials are enabled.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub and create a Community Cloud app for it, using `app.py` as the main file.
2. In the app's **Settings → Secrets**, add the same TOML keys shown in `.streamlit/secrets.toml.example`, using the project URL, publishable key, server-side service-role/secret key, the actual admin email/password pairs under `[ADMIN_USERS]`, and the campus IANA time zone.
3. Deploy and verify the public event list loads. Sign in to the Admin tab to create/publish an event and upload a test photo.
4. Keep the service-role key exclusively in Streamlit Cloud secrets. Rotate it in Supabase if it is ever exposed.

## Database and security notes

The schema enables RLS on all application tables. Anonymous and authenticated roles can only read published event details and their public event photos; they cannot read registrations or write application data. Streamlit verifies students with Supabase Auth and performs database writes and admin reads server-side. SQL constraints and triggers enforce valid capacities, unique event/student and event/account registrations, published-event registration, and capacity even when simultaneous submissions compete for the final place.

If you initialized the database using an earlier version of the schema before student accounts were added, run the updated `supabase/schema.sql` in the SQL Editor to add the account linkage and uniqueness index. The script is idempotent for these setup steps, but review migrations before applying schema changes to an existing production database. If you change the storage bucket name in Streamlit secrets, update the bucket ID and storage policy in the SQL to match.

## Tests

Run focused validation tests with `python -m pytest`.
