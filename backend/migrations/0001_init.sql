-- App schema for the AI Video Teaser Generator.
--
-- Lives in `app`, not `public`, on purpose: `public` is exposed through
-- PostgREST (PGRST_DB_SCHEMAS), so granting `authenticated` the privileges this
-- backend needs would also publish these tables as a REST API. FastAPI is the
-- only intended consumer, so the schema stays off the Data API entirely and RLS
-- is the second line of defence rather than the only one.
--
-- Idempotent: safe to re-run against an existing database.

create schema if not exists app;

-- The backend connects as `postgres` and drops to `authenticated` per request
-- (SET LOCAL ROLE), so `authenticated` is the role that must hold privileges.
grant usage on schema app to authenticated;

-- ---------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------
create table if not exists app.videos (
    id                text primary key,
    user_id           uuid not null references auth.users (id) on delete cascade,

    original_filename text        not null,
    storage_key       text        not null,
    extension         text        not null,
    size_bytes        bigint      not null,
    content_type      text,

    status            text        not null default 'uploaded',
    error_message     text,

    duration_seconds  double precision,
    width             integer,
    height            integer,
    fps               double precision,

    created_at        timestamptz not null default now()
);

create table if not exists app.jobs (
    id            text primary key,
    user_id       uuid not null references auth.users (id) on delete cascade,
    video_id      text not null references app.videos (id) on delete cascade,

    audience      text        not null,
    style         text        not null,

    status        text        not null default 'queued',
    progress      integer     not null default 0,
    message       text        not null default 'Queued',

    error_code    text,
    error_message text,
    ai_provider   text,

    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    completed_at  timestamptz
);

create table if not exists app.teasers (
    id               text primary key,
    user_id          uuid not null references auth.users (id) on delete cascade,
    job_id           text not null references app.jobs (id) on delete cascade,
    video_id         text not null references app.videos (id) on delete cascade,

    rank             integer     not null default 1,

    title            text        not null,
    hook             text        not null,
    reason           text        not null,

    start_seconds    double precision not null,
    end_seconds      double precision not null,
    score            double precision not null,
    scores           jsonb       not null default '{}'::jsonb,

    storage_key      text        not null,
    size_bytes       bigint      not null default 0,
    width            integer,
    height           integer,
    duration_seconds double precision,

    created_at       timestamptz not null default now()
);

-- Every lookup is "this user's rows", so user_id leads each index.
create index if not exists videos_user_created_idx  on app.videos  (user_id, created_at desc);
create index if not exists jobs_user_created_idx    on app.jobs    (user_id, created_at desc);
create index if not exists jobs_user_video_idx      on app.jobs    (user_id, video_id);
create index if not exists teasers_user_job_idx     on app.teasers (user_id, job_id, rank);
create index if not exists teasers_user_video_idx   on app.teasers (user_id, video_id);

-- ---------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------
-- SECURITY INVOKER (the default): this only touches the row being written, so
-- it needs no privileges beyond the caller's.
create or replace function app.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

drop trigger if exists jobs_touch_updated_at on app.jobs;
create trigger jobs_touch_updated_at
    before update on app.jobs
    for each row execute function app.touch_updated_at();

-- ---------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------
alter table app.videos  enable row level security;
alter table app.jobs    enable row level security;
alter table app.teasers enable row level security;

-- Force RLS so the table owner is not exempt either. Without this, any
-- connection that stays as `postgres` would silently see every user's rows.
alter table app.videos  force row level security;
alter table app.jobs    force row level security;
alter table app.teasers force row level security;

grant select, insert, update, delete on app.videos  to authenticated;
grant select, insert, update, delete on app.jobs    to authenticated;
grant select, insert, update, delete on app.teasers to authenticated;

-- One policy per command rather than FOR ALL: UPDATE needs both USING (which
-- rows may be updated) and WITH CHECK (what they may be updated to). Without
-- WITH CHECK a user could reassign user_id and hand a row to someone else.
do $$
declare
    tbl text;
begin
    foreach tbl in array array['videos', 'jobs', 'teasers'] loop
        execute format('drop policy if exists %I on app.%I', tbl || '_select_own', tbl);
        execute format('drop policy if exists %I on app.%I', tbl || '_insert_own', tbl);
        execute format('drop policy if exists %I on app.%I', tbl || '_update_own', tbl);
        execute format('drop policy if exists %I on app.%I', tbl || '_delete_own', tbl);

        execute format(
            'create policy %I on app.%I for select to authenticated
               using ((select auth.uid()) = user_id)',
            tbl || '_select_own', tbl);

        execute format(
            'create policy %I on app.%I for insert to authenticated
               with check ((select auth.uid()) = user_id)',
            tbl || '_insert_own', tbl);

        execute format(
            'create policy %I on app.%I for update to authenticated
               using ((select auth.uid()) = user_id)
               with check ((select auth.uid()) = user_id)',
            tbl || '_update_own', tbl);

        execute format(
            'create policy %I on app.%I for delete to authenticated
               using ((select auth.uid()) = user_id)',
            tbl || '_delete_own', tbl);
    end loop;
end;
$$;
