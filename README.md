# Campus Connect

A student-friendly event discovery and registration app built with Streamlit and Supabase. Events, registrations, and event photos live in Supabase; the app does not use local or browser storage as its data source.

## Features

- Browse published upcoming events, event details, photos, venue, date/time, capacity, and available spaces.
- Register using your name, student ID, email, and optional phone number.
- Prevent duplicate registrations per event and student ID; database triggers serialize registrations and enforce capacity.
- Admin-only event creation, editing, publishing/unpublishing, photo uploads/removals, and per-event CSV registration exports.
- Server-side-only Supabase service-role access with database row-level security enabled.

## Local setup

1. Use Python 3.9 or newer and create a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Create a Supabase project and run [`supabase/schema.sql`](supabase/schema.sql) in its SQL Editor.
4. In Supabase **Project Settings → API**, copy the project URL and service-role key. Keep the service-role key private; it bypasses row-level security.
5. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a long, unique `ADMIN_PASSWORD`. Set `APP_TIMEZONE` to the campus IANA time zone (for example, `America/New_York`); it defaults to UTC. Keep the secrets file out of version control.
6. Start the app: `streamlit run app.py`.

`SUPABASE_STORAGE_BUCKET` defaults to `event-photos`. The SQL script creates this public-read bucket with a 10 MB per-image limit for JPEG, PNG, and WebP uploads. Uploaded photos are publicly viewable; do not upload sensitive images.

The app's service-role key remains on the Streamlit server. Public students never receive Supabase credentials. Admin authentication is enforced by a server-side password check; choose a strong password and only share it with event administrators. Admin sessions use Streamlit's server-side session state.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub and create a Community Cloud app for it, using `app.py` as the main file.
2. In the app's **Settings → Secrets**, add the same TOML keys shown in `.streamlit/secrets.toml.example`, using the project URL, service-role key, a strong admin password, and the campus IANA time zone.
3. Deploy and verify the public event list loads. Sign in to the Admin tab to create/publish an event and upload a test photo.
4. Keep the service-role key exclusively in Streamlit Cloud secrets. Rotate it in Supabase if it is ever exposed.

## Database and security notes

The schema enables RLS on all application tables. Anonymous and authenticated roles can only read published event details and their public event photos; they cannot read registrations or write application data. Streamlit performs writes and admin reads server-side with the service-role key. SQL constraints and triggers enforce valid capacities, unique event/student registrations, published-event registration, and capacity even when simultaneous submissions compete for the final place.

If you change the storage bucket name in Streamlit secrets, update the bucket ID and storage policy in `supabase/schema.sql` to match. Re-run the schema script only when setting up a new project; review migrations before applying schema changes to an existing production database.

## Tests

Run focused validation tests with `python -m pytest`.
