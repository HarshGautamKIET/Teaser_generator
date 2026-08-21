-- URL ingestion, and per-run pipeline overrides.
--
-- Two changes that arrive together because both widen what a request may ask
-- for:
--
--   * a video can now arrive by URL rather than by upload, so a row has to
--     record where it came from and survive the window while it is still being
--     fetched;
--   * teaser count and clip length were server-wide settings, so two users of
--     one deployment could not want different ones. They become per-job, with
--     NULL meaning "whatever the server default is" -- existing rows keep
--     behaving exactly as they did.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

-- ---------------------------------------------------------------------
-- Videos: where the source came from
-- ---------------------------------------------------------------------
-- 'upload' | 'url'. Defaulted so every existing row is correctly described as
-- an upload without a backfill.
alter table app.videos
    add column if not exists source_type text not null default 'upload';

-- The URL a fetched video came from. Kept for display and for re-fetching, and
-- NULL for uploads. Not unique: the same talk may legitimately be pulled twice.
alter table app.videos
    add column if not exists source_url text;

-- Title as reported by the source site, when it gives one. Shown instead of the
-- filename, which for a fetched video is derived rather than chosen.
alter table app.videos
    add column if not exists source_title text;

-- `status` gains 'fetching' (bytes on the way) alongside the existing
-- 'uploaded' / 'ready' / 'failed'. No constraint change is needed -- status has
-- always been a free text column -- but the set is recorded here because
-- app/models.py VideoStatus is the only other place it is written down.

-- ---------------------------------------------------------------------
-- Jobs: pipeline settings chosen per run
-- ---------------------------------------------------------------------
-- NULL means "use the server default" (Settings.teaser_count /
-- Settings.teaser_max_seconds). Nullable rather than defaulted on purpose: a
-- concrete default copied in here would freeze today's value into every future
-- row, so changing the server setting would stop affecting new runs.
alter table app.jobs
    add column if not exists teaser_count integer;

alter table app.jobs
    add column if not exists clip_max_seconds integer;

-- Guard rails at the storage layer as well as in the API. A request that got
-- past validation must still not be able to ask for 500 clips.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_teaser_count_sane'
    ) then
        alter table app.jobs add constraint jobs_teaser_count_sane
            check (teaser_count is null or teaser_count between 1 and 10);
    end if;

    if not exists (
        select 1 from pg_constraint where conname = 'jobs_clip_max_seconds_sane'
    ) then
        alter table app.jobs add constraint jobs_clip_max_seconds_sane
            check (clip_max_seconds is null or clip_max_seconds between 5 and 180);
    end if;
end;
$$;

-- Fetches in flight are polled until they finish, so that lookup gets an index.
create index if not exists videos_user_status_idx on app.videos (user_id, status);
