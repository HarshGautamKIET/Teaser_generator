-- What kind of recording the source is.
--
-- The pipeline had one set of tuning constants -- self-containment threshold,
-- clip separation, preferred length, crop behaviour -- and they were chosen for
-- a talk: one person moving through distinct topics. Demos and training
-- sessions are not that shape. A demo's payoff depends on the steps that set it
-- up, and training material is cumulative by design, so both score low on
-- self-containment and are discarded during validation rather than merely
-- ranked below a webinar's moments. The result was an empty run, not a weaker
-- one.
--
-- The type is stored; the tuning is not. Profiles live in app/domain.py, so
-- retuning a recording type is a code change rather than a backfill, and the rows
-- keep saying what the source was rather than what the constants happened to be
-- on the day it ran.
--
-- NULL means "the default recording type", matching teaser_count, clip_max_seconds
-- and aspect_ratio. Every existing row therefore keeps its exact behaviour: the
-- webinar profile overrides none of the server settings those runs used.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.jobs
    add column if not exists recording_type text;

-- The set the API accepts (app/domain.py RecordingType). Constrained here as well
-- because the value selects a pipeline profile, and an unknown one would raise
-- a KeyError inside a background worker where nobody is waiting to see it.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_recording_type_known'
    ) then
        alter table app.jobs add constraint jobs_recording_type_known
            check (recording_type is null
                   or recording_type in ('webinar', 'demo', 'training'));
    end if;
end;
$$;
