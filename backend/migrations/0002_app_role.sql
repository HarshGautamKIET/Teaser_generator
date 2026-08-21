-- The login role the backend connects as.
--
-- Why not just connect as `postgres`: that role carries BYPASSRLS, so it reads
-- and writes every user's rows regardless of the policies in 0001, and even
-- `force row level security` does not constrain it. Under `postgres`, the RLS
-- boundary would hold only as long as the application remembered to SET ROLE on
-- every single transaction -- one missed code path and the leak is silent.
--
-- `teaser_app` inverts that failure mode:
--   * NOBYPASSRLS  - policies always apply once it becomes `authenticated`.
--   * NOINHERIT    - it does NOT passively acquire `authenticated`'s rights; it
--                    must SET ROLE explicitly.
--   * no grants of its own on app.* - so a transaction that fails to scope
--                    itself gets "permission denied", not somebody else's data.
--
-- Fail closed, not fail open.
--
-- Requires: psql -v app_password=... (see docker-compose.yml, migrate service).
-- Idempotent: safe to re-run.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'teaser_app') then
        create role teaser_app login noinherit;
    end if;
end;
$$;

-- NOSUPERUSER/NOCREATEDB are the CREATE ROLE defaults and are deliberately not
-- restated: `postgres` is not a superuser in Supabase and is refused permission
-- to alter superuser-related attributes at all.
alter role teaser_app with login noinherit nobypassrls password :'app_password';

-- Membership is what allows SET ROLE authenticated. It is not inherited
-- (NOINHERIT above), so it confers nothing until the app asks for it.
grant authenticated to teaser_app;

-- Connecting at all requires CONNECT on the database.
grant connect on database postgres to teaser_app;

-- USAGE on the schema, so the role can reach the SECURITY DEFINER maintenance
-- routines it is granted (migrations/0003). This confers nothing on the tables:
-- they have no grants to teaser_app, so unscoped data access is still refused.
grant usage on schema app to teaser_app;
