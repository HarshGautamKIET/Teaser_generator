-- The parts of Supabase that backend/migrations/*.sql depend on.
--
-- The test suite runs against a real Postgres because the security model is RLS
-- plus a powerless login role. In CI, standing up the whole self-hosted stack to
-- get that would mean thirteen containers and a set of generated secrets that
-- are deliberately not committed -- for three objects the migrations actually
-- reference.
--
-- So CI runs a plain Postgres and this file supplies those three:
--
--   * the `authenticated` role the RLS policies grant to and the app SET ROLEs
--     into,
--   * `auth.users`, which every app table has an ON DELETE CASCADE foreign key
--     into,
--   * `auth.uid()`, which every policy calls.
--
-- What this is NOT is a Supabase substitute. It has no GoTrue, no JWT
-- verification, and no PostgREST. It exists so the RLS policies under test are
-- the real ones, executing against the real role and the real auth.uid().
--
-- Idempotent: safe to re-run.

-- --------------------------------------------------------------------------
-- Roles
-- --------------------------------------------------------------------------
-- NOLOGIN: these are authorisation identities to SET ROLE into, never
-- connection identities. `teaser_app` is the only role that logs in, and
-- migrations/0002 creates it.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'service_role') then
        create role service_role nologin noinherit bypassrls;
    end if;
end;
$$;

-- --------------------------------------------------------------------------
-- auth schema
-- --------------------------------------------------------------------------
create schema if not exists auth;
grant usage on schema auth to anon, authenticated, service_role;

-- Only the columns this application relies on. Real auth.users is far wider;
-- the app never reads it, it only points foreign keys at the id.
create table if not exists auth.users (
    id         uuid primary key,
    email      text,
    created_at timestamptz not null default now()
);

-- Matches Supabase's definition, including the older singular claim key. The
-- app sets `request.jwt.claims` per transaction (see app/database.py), so the
-- policies resolve the caller from exactly the setting production uses.
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$$;

grant execute on function auth.uid() to anon, authenticated, service_role;
