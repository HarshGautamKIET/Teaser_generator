-- Output shape chosen per run.
--
-- Aspect ratio was a server setting, which made it a deployment-wide decision:
-- one person wanting a widescreen cut for YouTube and another wanting a
-- vertical cut for Shorts could not both be served without a redeploy between
-- them. It joins teaser_count and clip_max_seconds as a per-job column.
--
-- NULL means "use the server default", for the same reason as those two: a
-- concrete default copied in here would freeze today's value into every future
-- row. Existing rows keep their original behaviour, which was whatever
-- TEASER_ASPECT_RATIO said at the time they ran -- that value is not
-- recoverable now, and backfilling a guess would misreport history.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.jobs
    add column if not exists aspect_ratio text;

-- The set the API accepts (app/domain.py AspectRatio). Constrained here as
-- well because this column reaches an FFmpeg filter expression: the API is the
-- place that should reject a bad value, but it must not be the only one.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_aspect_ratio_known'
    ) then
        alter table app.jobs add constraint jobs_aspect_ratio_known
            check (aspect_ratio is null
                   or aspect_ratio in ('16:9', '9:16', '1:1', '4:3', '4:5'));
    end if;
end;
$$;
