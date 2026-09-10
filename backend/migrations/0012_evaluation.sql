-- Evaluation: what the pipeline discarded, and what the user thought of what
-- survived.
--
-- Two additions, for two different questions.
--
-- `pipeline_report` answers "what did this run throw away, and why". The
-- pipeline has always discarded candidates -- out-of-bounds timestamps, moments
-- that needed surrounding context, boundaries with no pause to snap to -- and
-- has always written the reason to a log line nobody reads. A discard rate is
-- the single most informative number this system produces about its own prompt:
-- a run that proposed eight moments and kept one is a run whose prompt is
-- wrong, and until now that was indistinguishable from a run that kept all
-- eight.
--
-- One jsonb column rather than a column per counter, which is the opposite of
-- how `preview_*` was added in 0011. The preview fields are three fixed facts
-- about an artifact that either exists or does not. This is an open set of
-- diagnostics that will grow every time a new check is added to the pipeline,
-- and a migration per metric would make adding a metric expensive enough that
-- nobody would. jsonb is queryable in Postgres, so the aggregate that matters
-- (`pipeline_report->'candidates'->>'drop_rate'`) is still available to SQL.
--
-- `teaser_feedback` answers "was the clip any good". A separate table rather
-- than two columns on app.teasers, because a verdict is evaluation data and a
-- teaser is product data: keeping them apart means the evaluation subsystem
-- owns one table and can be dropped entirely without touching the pipeline's
-- own schema. It also carries its own timestamps -- when someone judged a clip
-- is a different fact from when the clip was cut, and a nullable column on
-- teasers would conflate "not yet judged" with "judged, no opinion".
--
-- Idempotent, like the rest of the migrations: safe to re-run.

-- ---------------------------------------------------------------------
-- What the run discarded
-- ---------------------------------------------------------------------
alter table app.jobs
    add column if not exists pipeline_report jsonb;

-- An object or SQL NULL, never a bare scalar or an array. NULL means the run
-- predates this column or failed before analysis; those are the same thing to a
-- reader (there is no report) and both must stay distinguishable from `{}`,
-- which means a run that produced an empty one.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_pipeline_report_object'
    ) then
        alter table app.jobs add constraint jobs_pipeline_report_object
            check (pipeline_report is null
                   or jsonb_typeof(pipeline_report) = 'object');
    end if;
end;
$$;

-- ---------------------------------------------------------------------
-- What the user thought of the clip
-- ---------------------------------------------------------------------
create table if not exists app.teaser_feedback (
    id         text primary key,
    user_id    uuid not null references auth.users (id)   on delete cascade,
    teaser_id  text not null references app.teasers (id)  on delete cascade,

    -- 'keep' or 'discard'. Deliberately binary: "would you post this?" is the
    -- question the product actually asks, and a five-point scale would collect
    -- a middle nobody can act on. Constrained here as well as in the API so a
    -- direct write cannot introduce a third value the harness has no rule for.
    verdict    text        not null,
    -- Optional free text. Capped in the API, not here: this is a note, and a
    -- length limit belongs where the input arrives.
    note       text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'teaser_feedback_verdict_known'
    ) then
        alter table app.teaser_feedback add constraint teaser_feedback_verdict_known
            check (verdict in ('keep', 'discard'));
    end if;
end;
$$;

-- One verdict per person per clip, changeable. Without this a user who clicked
-- twice would appear in the corpus twice and weight their own clip double.
create unique index if not exists teaser_feedback_one_per_user
    on app.teaser_feedback (user_id, teaser_id);

-- Every lookup is "this user's rows", so user_id leads, matching 0001.
create index if not exists teaser_feedback_user_created_idx
    on app.teaser_feedback (user_id, created_at desc);

drop trigger if exists teaser_feedback_touch_updated_at on app.teaser_feedback;
create trigger teaser_feedback_touch_updated_at
    before update on app.teaser_feedback
    for each row execute function app.touch_updated_at();

-- ---------------------------------------------------------------------
-- Row level security -- identical treatment to the tables in 0001
-- ---------------------------------------------------------------------
alter table app.teaser_feedback enable  row level security;
alter table app.teaser_feedback force   row level security;

grant select, insert, update, delete on app.teaser_feedback to authenticated;

drop policy if exists teaser_feedback_select_own on app.teaser_feedback;
drop policy if exists teaser_feedback_insert_own on app.teaser_feedback;
drop policy if exists teaser_feedback_update_own on app.teaser_feedback;
drop policy if exists teaser_feedback_delete_own on app.teaser_feedback;

create policy teaser_feedback_select_own on app.teaser_feedback
    for select to authenticated
    using ((select auth.uid()) = user_id);

create policy teaser_feedback_insert_own on app.teaser_feedback
    for insert to authenticated
    with check ((select auth.uid()) = user_id);

create policy teaser_feedback_update_own on app.teaser_feedback
    for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create policy teaser_feedback_delete_own on app.teaser_feedback
    for delete to authenticated
    using ((select auth.uid()) = user_id);
