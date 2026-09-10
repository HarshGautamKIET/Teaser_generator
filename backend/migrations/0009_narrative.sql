-- What the run said about the video as a whole.
--
-- The clips were the only output, which left the product able to show which
-- moments it picked but not what the video was. "Summarize narratives" is one
-- of the things the system is for, and per-clip titles and hooks are not that:
-- they describe the excerpts, not the source.
--
-- On jobs rather than videos, though the video is what is being described. The
-- summary is written for the run's audience -- the same talk summarised for
-- business leaders and for students is two different summaries, and only one of
-- them can live on the video row. Chapters and keywords come back from the same
-- audience-tailored call, so they stay with it rather than being split across
-- two tables on a distinction the model never made.
--
-- JSONB rather than child tables: nothing joins, filters, or updates these --
-- they are written once when the run completes and read back whole. A chapters
-- table would buy referential integrity over rows that only ever appear as a
-- contents list.
--
-- All nullable. A model that returns moments and no summary must produce a run
-- with clips and no summary, never a failed one, so there is nothing here that
-- a completed run is required to have.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.jobs
    add column if not exists summary text;

alter table app.jobs
    add column if not exists chapters jsonb;

alter table app.jobs
    add column if not exists keywords jsonb;

-- Shape guard only, not content validation -- app/services/analysis_service.py
-- does that. This is here so a bug that wrote a scalar into either column
-- surfaces at the write rather than as a type error in the client weeks later.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_narrative_lists'
    ) then
        alter table app.jobs add constraint jobs_narrative_lists
            check ((chapters is null or jsonb_typeof(chapters) = 'array')
               and (keywords is null or jsonb_typeof(keywords) = 'array'));
    end if;
end;
$$;
