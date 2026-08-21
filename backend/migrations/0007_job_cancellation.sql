-- Job cancellation.
--
-- Adds `cancelled` as a fourth terminal status. `status` is plain text with no
-- check constraint, so the value itself needs no schema change -- but the
-- startup sweep does.
--
-- reconcile_stranded_jobs() (0003) fails every row that is not `completed` or
-- `failed`, on the assumption that any other status means a worker died
-- mid-flight. A cancelled job is neither: it stopped exactly as asked. Without
-- this change the first restart after a cancellation would relabel it
-- "The server restarted while this job was running", which is untrue and
-- turns a clean stop into a phantom failure in the dashboard's error rate.
--
-- Idempotent: safe to re-run.

create or replace function app.reconcile_stranded_jobs()
returns integer
language plpgsql
security definer
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
     where status not in ('completed', 'failed', 'cancelled');

    get diagnostics affected = row_count;
    return affected;
end;
$$;

revoke all on function app.reconcile_stranded_jobs() from public;
grant execute on function app.reconcile_stranded_jobs() to teaser_app;
