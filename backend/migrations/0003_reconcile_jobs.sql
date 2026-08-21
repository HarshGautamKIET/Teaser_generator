-- Startup reconciliation for jobs stranded mid-flight.
--
-- Processing runs in-process (ADR-008). If the API restarts while a job is
-- analyzing or generating, the worker dies but the row keeps its non-terminal
-- status forever, and the frontend polls it forever. On boot the app marks any
-- such row failed so the user sees an honest outcome.
--
-- This is inherently a cross-user operation, and the app's connection is
-- deliberately confined to one user by RLS. Rather than open a second,
-- BYPASSRLS connection as `postgres` just for this -- which would put an
-- unscoped, all-rows connection into the application for the rest of time --
-- the sweep is a SECURITY DEFINER function with a narrow contract: it only
-- flips status on already-stranded rows and returns a count. It never returns
-- row data, so it cannot be used to read across users.
--
-- Idempotent: safe to re-run.

create or replace function app.reconcile_stranded_jobs()
returns integer
language plpgsql
security definer
-- Empty search_path: every object below is schema-qualified, so a caller
-- cannot shadow one with a temp table and redirect the writes.
set search_path = ''
as $$
declare
    affected integer;
begin
    update app.jobs
       set status        = 'failed',
           message       = 'Failed',
           error_code    = 'INTERRUPTED',
           error_message = 'The server restarted while this job was running.',
           completed_at  = now()
     where status not in ('completed', 'failed');

    get diagnostics affected = row_count;
    return affected;
end;
$$;

-- Postgres grants EXECUTE to PUBLIC by default, which for a SECURITY DEFINER
-- function means anon and authenticated can call it. Lock it to the app role.
revoke all on function app.reconcile_stranded_jobs() from public;
grant execute on function app.reconcile_stranded_jobs() to teaser_app;
