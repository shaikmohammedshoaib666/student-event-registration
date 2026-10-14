-- Run this script in the Supabase SQL Editor for a new project.
create extension if not exists pgcrypto;

create table if not exists public.events (
    id uuid primary key default gen_random_uuid(),
    title text not null check (char_length(title) between 1 and 150),
    description text not null check (char_length(description) between 1 and 5000),
    starts_at timestamptz not null,
    venue text not null check (char_length(venue) between 1 and 200),
    capacity integer not null check (capacity > 0),
    published boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.set_event_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists events_set_updated_at on public.events;
create trigger events_set_updated_at
before update on public.events
for each row execute function public.set_event_updated_at();

create table if not exists public.registrations (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.events(id) on delete cascade,
    student_name text not null check (char_length(student_name) between 2 and 100),
    student_id text not null check (char_length(student_id) between 2 and 50),
    email text not null check (char_length(email) between 3 and 254),
    phone text,
    created_at timestamptz not null default now(),
    constraint unique_event_student unique (event_id, student_id)
);
create index if not exists registrations_event_id_idx on public.registrations(event_id);

create table if not exists public.event_photos (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.events(id) on delete cascade,
    storage_path text not null unique,
    public_url text not null,
    created_at timestamptz not null default now()
);
create index if not exists event_photos_event_id_idx on public.event_photos(event_id);

-- Counts are exposed to the server-side app using its service-role key.
create or replace view public.event_registration_counts as
select e.id as event_id, count(r.id)::integer as registration_count
from public.events e
left join public.registrations r on r.event_id = e.id
group by e.id;

-- Serialize signups per event and make the registration rules atomic even
-- when multiple students submit the final available spot simultaneously.
create or replace function public.check_event_registration()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    event_capacity integer;
    event_is_published boolean;
    current_registrations integer;
begin
    select e.capacity, e.published
      into event_capacity, event_is_published
      from public.events e
     where e.id = new.event_id
      for no key update;

    if not found or not event_is_published then
        raise exception 'event_not_open' using errcode = 'P0001';
    end if;

    select count(*) into current_registrations
      from public.registrations r
     where r.event_id = new.event_id;

    if current_registrations >= event_capacity then
        raise exception 'event_registration_full' using errcode = 'P0001';
    end if;
    return new;
end;
$$;

drop trigger if exists registrations_check_event_capacity on public.registrations;
create trigger registrations_check_event_capacity
before insert on public.registrations
for each row execute function public.check_event_registration();

create or replace function public.check_event_capacity_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_registrations integer;
begin
    if new.capacity < old.capacity then
        select count(*) into current_registrations
          from public.registrations r
         where r.event_id = old.id;
        if new.capacity < current_registrations then
            raise exception 'capacity_below_registration_count' using errcode = 'P0001';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists events_check_capacity_update on public.events;
create trigger events_check_capacity_update
before update of capacity on public.events
for each row execute function public.check_event_capacity_update();

alter table public.events enable row level security;
alter table public.registrations enable row level security;
alter table public.event_photos enable row level security;

drop policy if exists "Public can read published events" on public.events;
create policy "Public can read published events"
on public.events for select to anon, authenticated
using (published = true);

drop policy if exists "Public can read photos for published events" on public.event_photos;
create policy "Public can read photos for published events"
on public.event_photos for select to anon, authenticated
using (exists (
    select 1 from public.events e
    where e.id = event_id and e.published = true
));

-- All writes and all registration data access go through the server-side app.
-- The service-role key bypasses RLS; never expose it to browsers or check it in.
revoke all on public.events, public.registrations, public.event_photos
    from anon, authenticated;
revoke all on public.event_registration_counts from anon, authenticated;
grant select on public.events, public.event_photos to anon, authenticated;
grant select, insert, update, delete on public.events, public.registrations, public.event_photos
    to service_role;
grant select on public.event_registration_counts to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'event-photos',
    'event-photos',
    true,
    10485760,
    array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- Public URLs may read objects from this public bucket. Uploads/deletes are
-- performed only by the app server using its service-role key.
drop policy if exists "Public can read event photos" on storage.objects;
create policy "Public can read event photos"
on storage.objects for select to anon, authenticated
using (bucket_id = 'event-photos');
