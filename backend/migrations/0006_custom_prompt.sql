-- Free-text direction supplied by the user for one run.
--
-- Audience and style are a fixed vocabulary, which is what makes them useful
-- for scoring but also what limits them: "focus on the pricing discussion" is
-- not an audience. This column holds that extra direction, per run, so it shows
-- up in history and a retry reproduces the run it is retrying rather than a
-- differently-steered one.
--
-- NULL means no extra direction was given, which is the behaviour every
-- existing row had.
--
-- Idempotent, like the rest of the migrations: safe to re-run.

alter table app.jobs
    add column if not exists custom_prompt text;

-- Bounded at the database as well as the API. The value is interpolated into a
-- model prompt, and an unbounded one would be a cheap way to push the real
-- instructions out of the context window.
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'jobs_custom_prompt_length'
    ) then
        alter table app.jobs add constraint jobs_custom_prompt_length
            check (custom_prompt is null or char_length(custom_prompt) <= 500);
    end if;
end;
$$;
