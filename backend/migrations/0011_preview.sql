-- The assembled preview for a run.
--
-- Every output so far has been an excerpt: a clip that has to stand alone, cut
-- from one moment. That is the right shape for repurposing a talk and the wrong
-- one for answering "what is this course?" -- three disconnected extracts leave
-- the viewer to assemble the answer themselves, which is the job the artifact
-- was supposed to do.
--
-- So a run may also produce one file made of the opening seconds of several
-- moments, held together by title cards. The cards are the point: they supply
-- the context each fragment is missing, which is the same context the
-- self-containment rules spend their time insisting individual clips must not
-- need.
--
-- Flat columns on jobs rather than a row in teasers. A preview has no window in
-- the source, no rank and no score, so it would leave half of that table null
-- and change what the other half means. It belongs to the run rather than to
-- any one moment.
--
-- All nullable: a preview needs at least two moments, so a run that selected
-- one produces none, and that is not a failure.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.jobs
    add column if not exists preview_storage_key text;

alter table app.jobs
    add column if not exists preview_size_bytes integer;

alter table app.jobs
    add column if not exists preview_duration_seconds double precision;

-- The three are written together or not at all, so a row carrying a key with no
-- size means the write was interrupted rather than that a preview exists.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_preview_complete'
    ) then
        alter table app.jobs add constraint jobs_preview_complete
            check (num_nulls(preview_storage_key, preview_size_bytes,
                             preview_duration_seconds) in (0, 3));
    end if;
end;
$$;
