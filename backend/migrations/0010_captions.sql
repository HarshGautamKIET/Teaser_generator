-- The spoken lines burned into a clip.
--
-- Stored as well as burned because the picture is the one place the text
-- cannot be read by anything but a person. A row here makes the same words
-- available to the API, to search, and to anyone who needs the clip's content
-- without decoding it -- and it is what lets the suite check that captions were
-- produced without reading pixels back out of an MP4.
--
-- Timed from the start of the clip, not of the source video, matching what was
-- rendered. A cue's numbers therefore mean the same thing as the file it was
-- burned into, and stay correct if the clip is ever re-cut from a different
-- point in the source.
--
-- On teasers rather than jobs: unlike the run's summary, these differ per clip,
-- because each clip is a different minute of speech.
--
-- Nullable. Captions are off by default (ENABLE_CAPTIONS), a clip may contain
-- no speech at all, and neither case is a failure -- so there is nothing here
-- that a completed teaser is required to have.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.teasers
    add column if not exists captions jsonb;

-- Shape guard only, not content validation -- app/services/caption_service.py
-- does that. Here so a bug that wrote a scalar surfaces at the write rather
-- than as a type error in the client weeks later.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'teasers_captions_list'
    ) then
        alter table app.teasers add constraint teasers_captions_list
            check (captions is null or jsonb_typeof(captions) = 'array');
    end if;
end;
$$;
