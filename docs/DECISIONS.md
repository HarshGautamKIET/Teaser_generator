# Decisions

Every non-obvious choice in this project, why it was made, what the alternatives
were, and why they were not taken.

This exists because a judge, a reviewer, or a future maintainer can read the
code and see *what* it does; none of them can see what it nearly did instead.
An option rejected for a good reason is worth as much as the one that was taken,
and it is the first thing lost when nobody writes it down.

**Read this before changing anything it covers.** A decision reversed without
reading its entry is a decision made twice, and the second time without the
reasoning.

**This file is appended to on every substantive change.** See
[Keeping this file current](#keeping-this-file-current) at the end.

---

## Contents

- [1. Architecture](#1-architecture)
- [2. The AI boundary](#2-the-ai-boundary)
- [3. Selection and cutting](#3-selection-and-cutting)
- [4. Evaluation](#4-evaluation) — added 2026-08-23; [4.13](#413-first-real-run-2026-08-23) is the first real-asset result, [4.14](#414-dead-code-deleted-2026-08-23) removes what went unused
- [5. Data model](#5-data-model)
- [6. Security](#6-security)
- [7. Testing and CI](#7-testing-and-ci)
- [8. Rejected wholesale](#8-rejected-wholesale)
- [9. Documentation](#9-documentation) — added 2026-08-23
- [10. Frontend](#10-frontend) — added 2026-08-23
- [Keeping this file current](#keeping-this-file-current)

---

## 1. Architecture

### 1.1 In-process jobs, not a queue

**Decision.** Generation runs in a FastAPI background task in the API process.
Jobs interrupted by a restart are reconciled to `failed` at startup.

**Why.** The unit of work is one video, it takes minutes, and there is one
process. A queue solves fan-out across workers and durable retry; neither is a
problem this system has.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| Celery + Redis | Two more services to run, configure and explain, for a workload of one job at a time. The demo would spend its first minute on infrastructure. |
| Kubernetes Jobs | Same, plus a cluster. |
| A database-backed queue table | Closer to justifiable, but the only thing it buys over the current design is surviving a restart mid-run — and a run that survives a restart still has to re-download the video and re-call Gemini, so it is a retry either way. |

**What this costs.** A restart during a run loses it. Accepted, and made
visible: the reconciliation marks those jobs `failed` rather than leaving them
`analyzing` forever.

### 1.2 A provider interface in front of Gemini

**Decision.** `app/ai/base.py` defines the interface; `gemini.py` and `fake.py`
implement it. `AI_PROVIDER` selects one.

**Why.** Not for the usual reason (swapping vendors). It is so the entire test
suite and the whole demo can run with no network and no key, and so that
happening is a deliberate choice rather than an accident.

**The rule that makes it worth having.** `fake` is **never a silent fallback**.
A missing key fails the run with `AI_ANALYSIS_FAILED`; it does not quietly
produce placeholder clips. A fallback that fabricates output is worse than an
error, because the demo continues and nobody knows the model was never called.

**Alternative rejected.** Mocking the Gemini SDK in tests. That tests the mock's
shape rather than the parsing code, and gives the demo nothing.

### 1.3 Storage behind an abstraction

**Decision.** `app/storage` resolves keys to paths; nothing above it knows where
the bytes are.

**Why.** Local files become S3 without touching the frontend contract.

**Honest note.** There is exactly one implementation. This is the kind of
single-caller abstraction usually worth deleting; it survives because the media
routes already need a key-to-path indirection for the ownership check, so the
seam exists whether or not it is named.

---

## 2. The AI boundary

### 2.1 The model proposes, the backend disposes

**Decision.** Every candidate moment is schema-checked and every timestamp
bounded against the real (FFprobe-measured) duration before FFmpeg is invoked.
Invalid candidates are **dropped, never repaired**.

**Why not repair.** A silently-corrected hallucination is still a
hallucination, and repairing it destroys the signal that says the prompt is
broken. A run whose candidates are all being clamped into range is a run whose
prompt is wrong, and clamping makes that indistinguishable from a run that
worked.

**Alternative rejected.** Asking the model to fix its own output. Costs a second
call, and the retry is drawn from the same distribution that produced the error.

### 2.2 Narrative fails differently from candidates

**Decision.** The summary, chapters and keywords go through the same validation
as the moments, and a different consequence: a malformed chapter is dropped
from a contents list; a malformed candidate costs the run a clip.

**Why.** They are additive. A run that produced good clips and a broken chapter
list is a run with good clips, and failing it would trade the product's actual
output for a table of contents.

**Alternative rejected.** A second Gemini call for the narrative. It doubles the
cost of the most expensive step to separate two things one call already
returns, and the model has already watched the whole video to find the moments.

### 2.3 One analysis call, not one per stage

**Decision.** Moments, scores, summary, chapters and keywords come from a single
call.

**Why.** The expensive part is the model watching a two-hour video. Everything
else is text generation over context it already holds.

**What this costs.** No independent second opinion on the moments, and no
caching across audiences — the call is audience-conditioned, so regenerating
for a different audience pays for the whole watch again. See
[4.8](#48-what-came-from-comparing-against-prism).

### 2.4 The run direction is taste, never instructions

**Decision.** `custom_prompt` is bounded at 500 characters, fenced inside an
`ADDITIONAL DIRECTION` block, and the system instruction says in advance what
text arriving there is: *a viewer's preference about which moments to favour,*
to be treated as taste and never as instructions that could change the rules,
the duration limits, or the response format.

**Why.** It is untrusted user text interpolated into a model prompt. The
defence is not detection — you cannot reliably tell an instruction from a
preference in free text — but position and framing, backed by the fact that the
response is schema-forced and every timestamp is bounds-checked afterwards. An
injection that succeeds in changing the model's mind still has to produce output
that survives [2.1](#21-the-model-proposes-the-backend-disposes).

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| Strip or escape suspicious phrases | An arms race against paraphrase, and it false-positives on legitimate direction — "ignore the introduction" is a reasonable thing to ask a teaser generator for |
| Put the direction in the system instruction | That is precisely the position that would lend it authority over the rules |
| Drop the feature | The field earns its place: it is the only way a user steers selection without a new pipeline setting |

**What this costs.** A determined injection can still bias *which* moments are
chosen — which is what the field is for, so the line between use and abuse is
genuinely not sharp here. What it cannot do is change the response schema, widen
the duration bounds, or put an unvalidated value in front of FFmpeg, and those
are the properties that were worth defending.

### 2.5 The analysis stage is bounded, measured, and taken one at a time (2026-08-24)

**Decision.** Four changes to the same stage, from one incident:

1. Every Gemini HTTP request carries a timeout — 300s for a chunk, a poll or a
   delete, 900s for the analysis call. Set on the client, because the Files API
   builds its own per-request options with the timeout unset and the SDK falls
   back to the client's; setting it only per call leaves the uploads unbounded.
2. The upload reports progress. The stage now spans 25–45%, and the source is
   uploaded through a wrapped file handle because the SDK exposes no other hook.
3. Raising from that progress callback abandons the transfer, which is how a
   cancelled run stops uploading.
4. One run holds the stage at a time (`analysis_max_concurrent`).

**This narrows an existing rule.** "A cancelled run stops at the next stage
boundary" was never written down here — it lived in `cancel_job`'s docstring and
in `test_cancel.py` — but it was a real decision, and this changes it for one
stage. Cancellation is still checked at stage boundaries everywhere else; the
upload is now the one place a run can be stopped partway through a stage,
because it is the only stage long enough for the difference to matter. The
analysis call itself is still uninterruptible: once the bytes are delivered, a
cancel waits for the model to answer.

**Why.** On 2026-08-24 four runs entered this stage within twenty-six minutes.
Each was uploading its source over one uplink at roughly 68 KB/s — 14 of the 22
chunks of a 173 MB file in the first half hour — and all four sat at 25% until
every connection dropped at 05:00:24 with three different socket errors. Two of
them had been cancelled twelve minutes earlier and were still transferring.

Each change answers a specific part of that. The timeout means a dead transfer
is reported rather than waited on forever. The progress means a slow transfer
can be told apart from a hung one, which is the whole reason the runs looked
broken: 25% covered upload, file processing *and* analysis, so the longest part
of the run was also the only part that could not move. The slot means the
uplink is not divided; concurrent uploads on one connection do not finish
sooner than sequential ones, they finish later or not at all.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| A total-upload timeout instead of a per-request one | Forces a choice between killing a slow but healthy transfer and never noticing a dead one. Per chunk distinguishes them: a chunk that has moved no bytes in 300s is stalled, whatever the total elapsed time |
| Leave concurrency alone and only add progress | Honest, and still broken. The four runs did not fail because nobody could see them; they failed because they were strangling each other |
| A real job queue with a worker pool | The concurrency limit here is one semaphore. A queue is [1.1](#11-in-process-jobs-not-a-queue) again, and rejected for the same reasons |
| Compress or downscale the source before upload | A second full FFmpeg pass over a two-hour file to save an upload the model needs at usable quality. Worth revisiting if uploads stay the bottleneck |
| Report progress by timer rather than by bytes | Invents a number. A bar that advances on a clock while the socket is dead is worse than one that does not move |

**What this costs.** Runs now queue behind each other, and a second user waits
out the first user's upload with nothing but a message saying so — throughput
for one video is unchanged, but two simultaneous users see the wait moved into
the open rather than shared out. `analysis_max_concurrent` exists to raise this
where the uplink can carry it; it is deliberately not raised by default,
because the failure it prevents is silent and the cost it imposes is visible.

Passing a stream rather than a path also gives up the `X-Goog-Upload-File-Name`
header the SDK sets for paths, and requires the MIME type to be supplied
explicitly — the SDK guesses it from a filename it no longer sees.

The per-chunk write is roughly 22 extra `UPDATE`s on `app.jobs` for a 173 MB
source. That is the price of the cancellation check being the same statement as
the progress report, and it is a round trip the run was already making at every
stage boundary.

---

## 3. Selection and cutting

### 3.1 Self-containment is a filter, not a weight

**Decision.** A candidate scoring below `TEASER_MIN_SELF_CONTAINED` is removed
from contention entirely.

**Why.** It used to be 10% of the ranking score. Hook carries 30%, so a fragment
with a brilliant opening still won. A teaser that begins mid-thought is not a
slightly worse teaser — it is not a teaser — so it must not be able to out-score
its way in.

**Alternative rejected.** Raising the weight. Any weight below 100% still lets a
strong enough hook buy its way past, which is the exact failure.

**Measured, as of this document.** See [4.12](#412-what-the-first-numbers-say).

### 3.2 Recording type is a pipeline profile, not a label

**Decision.** `webinar` / `demo` / `training` each set the self-containment
floor, clip spacing, preferred length, prompt guidance, and crop-versus-pad.
The webinar profile overrides nothing.

**Why.** The constants were tuned for a talk. Applied to the other two they lose
clips rather than weakening them: a demo's payoff depends on the steps that set
it up and training material is cumulative, so both score low on self-containment
and are discarded during validation. The pipeline returned nothing for two of
the three source types it claimed to serve.

**Why the webinar profile overrides nothing.** Introducing profiles must not
silently retune the path the settings were already tuned for.

**Alternative rejected.** Letting the user set the floor directly. It exposes an
internal threshold as a product control and asks them to answer a question
about the pipeline rather than about their video.

### 3.3 Cut points snap to silence, not to a transcript

**Decision.** Boundaries move onto nearby pauses found with FFmpeg
`silencedetect`. A clip starts where speech *resumes* and ends where it
*pauses*. Either end declines to move if there is no pause within 2 seconds.

**Why not a transcript.** Locating pauses is enough to cut between two words
instead of through one, and FFmpeg is already a hard dependency. An ASR model
would be a new one, for a strictly smaller question.

**Why the two ends snap to opposite things.** Snapping both to the same kind of
boundary reliably clips the first or last syllable.

**Why declining is a real answer.** A boundary with no pause near it is one the
model placed inside continuous speech; dragging it several seconds to the
nearest pause would cut more than it fixed.

**Measured, as of this document.** See [4.4](#44-cut-quality-measured-without-a-human)
for how, and [4.13](#413-first-real-run-2026-08-23) for the first real result —
on a music-bedded source the detector finds no pauses at any threshold, so the
whole feature is inert and the clip opens mid-programme. That category is not
yet handled.

### 3.4 A minimum gap between selected moments

**Decision.** Selected moments must be separated by a configurable gap,
shrunk automatically when the video is too short to afford it.

**Why.** Non-overlap is not enough. Two adjacent moments never show the same
frame twice and are still one continuous passage cut in half, so the second
opens on the back of a sentence the viewer did not hear.

**Why it shrinks.** A fixed 15s gap is nothing in a forty-minute talk and fatal
in a ninety-second one — three 25s clips plus two 15s gaps need 105 seconds, so
the run silently returned one clip and the reason was buried in a debug log.

### 3.5 Captions are ASS, not SubRip

**Decision.** Burned-in captions are written as an ASS script whose
`PlayResX`/`PlayResY` are set to the clip's real output resolution.

**Why.** SubRip carries no styling, so the style has to be supplied at burn time
through the `subtitles` filter's `force_style` — and libass then interprets
those numbers against a virtual canvas of its own, 288 lines tall, rather than
against the video. `Fontsize=44` came out at roughly 290 pixels on a 1080x1920
clip, and `MarginV=90` placed the text across the middle of the frame. Because
an ASS script declares its own resolution, setting it to the real one makes
every number in the file a pixel.

**Alternative rejected.** SRT plus `force_style`, which is the more obvious
choice and the one that produced the numbers above. Making it work means
computing every style value against libass's canvas instead of the video, which
is the same arithmetic in a place nobody would think to look for it.

**What this costs.** ASS is a heavier format to generate and to read than SRT,
and the escaping rules are its own. Transcription output is also untrusted in
the way candidate moments are — a bad timestamp here does not reach FFmpeg as an
argument, it becomes a line in a file FFmpeg renders, so the failure is a cue at
the wrong moment rather than a broken cut. Overlaps and cues running past the
end of a clip are still corrected, because libass will happily stack them.

### 3.6 The preview is deliberately not a teaser

**Decision.** Each run also assembles one preview spot: the opening seconds of
several selected moments, joined by a title card, the moment's own title over
each beat, and an end card. On by default.

**Why.** Everything else the pipeline makes is an excerpt that has to stand
alone, which is right for repurposing a talk and wrong for answering "what is
this course?" — three disconnected extracts leave the viewer to assemble the
answer. The text is what makes the beats a sequence rather than a supercut: it
supplies exactly the context that [3.1](#31-self-containment-is-a-filter-not-a-weight)
spends its time insisting an individual clip must not need.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| A model call to write the linking copy | The moments, their titles and the summary all came out of the analysis that already ran, so the preview costs one FFmpeg pass and no tokens |
| Store it as a `teasers` row | It has no window in the source, no rank and no score. See [5.2](#52-the-preview-lives-on-jobs-not-in-teasers) |
| Off by default, like captions | Captions cost a model call per clip; this costs neither a call nor a key |

**What this costs.** It re-shows the opening of clips the user already has, and
every run pays the extra FFmpeg pass whether or not anyone plays it. When it
cannot be built the run says so — `no_preview_too_few_moments` or
`preview_assembly_failed` — rather than completing silently without one.

---

## 4. Evaluation

*Added 2026-08-23. Everything in this section was built in one pass; the
motivating comparison was against [Prism](#48-what-came-from-comparing-against-prism),
a CLI-shaped implementation of the same problem.*

### 4.0 Why evaluation at all

Before this, the project had no way to answer "did that prompt change make the
clips better?" Every test could pass while the output got worse. The test suite
verifies that the pipeline does what it was told; nothing verified that what it
was told was right.

The work is organised in tiers by what each one costs to obtain, because the
cheapest tier is worth more than the expensive ones and is the one most projects
skip.

### 4.1 Tier 0 first: count what you already discard

**Decision.** Before any annotation, count the decisions the pipeline was
already making. Drop reasons, snap outcomes, cut quality, and honest
degradation, recorded on every run.

**Why this first.** It is free. Every one of these decisions was already being
made correctly and written to a log line nobody reads. A run that proposed eight
moments and kept one was indistinguishable from a run that kept all eight —
both showed "Generated 1 teaser".

**Alternative rejected.** Starting with the retrieval metrics, which is the
impressive-sounding tier. They need labelled data, so starting there means
weeks before the first number, and the first number would still not explain
*why* a run returned one clip.

### 4.2 Drop reasons are slugs, counted; details are sentences, logged

**Decision.** `_reject_reason` returns `(slug, detail)`. The slug is counted
across runs; the detail goes in the log.

**Why.** "length 4.20s is below the 20s minimum" is the right thing to put in a
log, where a human is diagnosing one candidate. As a dictionary key it produces
one entry per candidate with a count of one, which is not a tally.

**Sub-decision: first failure wins.** A candidate that is both out of bounds and
too short is counted once, under the more fundamental reason. Counting both
makes the per-reason totals uninterpretable — they would no longer sum to the
number of dropped candidates.

**Sub-decision: outranked and too-close are counted alongside rejections.**
Losing on rank is not a failure — the moment was valid — but "why did I only get
one clip" has one answer shape whether the moment was rejected or merely beaten.

### 4.3 One `pipeline_report` jsonb column, not a column per counter

**Decision.** `app.jobs.pipeline_report jsonb`, with a CHECK that it is an
object or SQL NULL.

**Why.** This is the opposite of how `preview_*` was added in migration 0011,
deliberately. The preview fields are three fixed facts about an artifact that
either exists or does not. This is an open set of diagnostics that grows every
time a check is added to the pipeline, and a migration per metric makes adding a
metric expensive enough that nobody does.

**Why it is not a loss.** jsonb is queryable in Postgres, so
`pipeline_report->'candidates'->>'drop_rate'` is available to SQL for the
cross-run aggregate that matters.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| A column per counter | A migration per metric. The friction lands exactly on the activity being encouraged. |
| A separate `run_metrics` table | A row per run in a one-to-one relationship with `jobs` is a table pretending to be a column. |
| A log aggregator | Correct at scale, and this is a single process with a Postgres already holding every run. |

**Why NULL and `{}` must stay distinct.** NULL means no report — the run
predates the column or failed before analysis. `{}` means a run that produced an
empty one. The CHECK enforces object-or-NULL so the distinction survives.

### 4.4 Cut quality: measured without a human

**Decision.** After each clip is cut, measure the mean volume of its first
150ms and of the whole clip. The difference is the cut's quality. Clean is
6dB below the clip's own average.

**Why this is the most valuable metric here.** It is the only quality signal in
the project that needs no annotator, no model call and no user, so a corpus
accumulates whether or not anybody labels anything. It also measures the
snapping feature directly, which was previously believed on the strength of its
tests.

**Why relative, not absolute.** An absolute dB floor would measure the
recording's gain rather than the cut — a quietly-recorded talk would score
all-clean and a loud one all-broken. A clip that opens mid-word opens at
roughly the speech level of the rest of it; one that opens on a pause opens well
below it. The *difference* is the cut.

**Why on the finished clip, not the source window.** The finished clip is what a
viewer plays. It has been re-encoded, and if a boundary moved between ranking
and rendering, the clip is the only place both numbers describe the same audio.

**Why `volumedetect`.** No filter chain, one number, present in every FFmpeg
build. `ebur128` measures perceived loudness over long windows, which is the
wrong instrument for a 150ms question.

**Alternative rejected.** Detecting a word boundary with ASR. It answers the
question more precisely and costs a model call per clip, and the cheap version
already separates "opens on a pause" from "opens mid-word", which is the whole
decision.

### 4.5 Tier 1: labels collected from the product, not from an annotation sprint

**Decision.** A "Would you post this?" keep/discard control on every teaser
card. Verdicts become ground truth via `harness.ground_truth_from_feedback`.

**Why this is better data than annotation.** The usual approach sits a team down
with a stranger's webinar and marks the spans that should have been chosen. The
annotator does not know the material, has no stake, and is guessing at what a
teaser of this video is for. Here the person who uploaded the source judges
their own content at the moment they are deciding whether to post it — and the
answer they are already forming is exactly the label.

**This is the one structural advantage this project has over a CLI
implementation of the same pipeline.** It has users, sessions, and a database.

**Sub-decision: binary, not a scale.** "Would you post this?" has two answers. A
five-point scale collects a middle that no ranking change can be derived from.

**Sub-decision: `keep` becomes an annotation; `discard` does not.** These
metrics score what a run returned against what it should have returned. A
"should not" is already counted — as a prediction that matched nothing — and
adding it as a negative annotation would count it twice.

**Sub-decision: upsert, not append.** Someone who watches again and changes
their mind has produced a better label, not a second one. Appending would let a
single annotator weight their own clip twice in every metric. Enforced by a
unique index, not only by the service.

**Known limitation, stated rather than hidden.** Feedback can only describe
clips the pipeline already produced. It can prove a selected clip was wrong; it
can never prove an unselected moment was missed. So **recall against feedback is
not meaningful**, and `AssetResult.origin` records which source produced each
row so a table cannot silently average the two.

**Alternative rejected.** A separate review screen. It asks the user to do
evaluation work as a distinct activity, which nobody does twice.

### 4.6 A separate `teaser_feedback` table, not two columns on `teasers`

**Decision.** Its own table with its own RLS block.

**Why.** Feedback is evaluation data; a teaser is product data. Separating them
means the evaluation subsystem owns one table and could be dropped entirely
without touching the pipeline's schema. A verdict also has its own timestamps —
*when* somebody judged a clip is a different fact from when it was cut — and a
nullable column on `teasers` would conflate "not yet judged" with "judged, no
opinion".

**The honest counter-argument.** Two columns on `teasers` would be the smaller
diff: no new table, no new RLS block, no new policies. That was the closer call
in this section.

### 4.7 Tier 2 and 3: the metric definitions that are not the obvious ones

Three definitions were taken deliberately against their most natural reading.
Each has a test that fails if someone "simplifies" it back.

**Precision@K divides by K, not by the number of predictions.** A run asked for
five clips that returns two is penalised, not scored as though it answered
perfectly with a short list. Dividing by the prediction count makes "return one
clip you are sure of" the highest-scoring strategy available, which is not a
teaser generator.

**A match requires tIoU ≥ 0.5.** Overlapping by a second is not "found the
moment". Without a threshold, any prediction landing near a busy region of the
video counts as a hit.

**Each annotation can be claimed once.** Without this, a system returning the
same strong moment five times scores a perfect Precision@5 — precisely the
degenerate strategy the metric exists not to reward.

**Recall is reported but not optimised.** A teaser set containing every worthy
moment in a two-hour talk is a summary, not a teaser set. A run scoring 1.0 on
recall has probably failed at the task. Precision is the headline.

**Greedy matching, not Hungarian.** The optimal assignment differs only when two
predictions contest the same annotation — and in that case the run has
duplicated a moment, which should cost it rather than be optimised away.

**Ties broken by index.** These numbers go in a CI gate; a metric that moves
between identical runs is a metric that gets switched off.

#### The baselines are the point

An F1 of 0.6 proves nothing. Four alternatives are scored on identical ground
truth: `uniform`, `random` (seeded), `keyword`, `audio_peak`.

**`audio_peak` is the one that matters.** It approximates what highlight tools
did before language models: find where the speaker got loud, cut there. If
Gemini watching the entire video does not beat measuring volume, the expensive
part of this pipeline is decorating a heuristic — and that is worth knowing
before presenting it as video understanding.

**Everything is deterministic, `random` included.** A baseline that moved
between runs would turn every prompt-change comparison into noise.

**A baseline that could not be computed is named, not omitted.** `unavailable`
carries the reason. An absent row reads as "the pipeline beat every baseline";
a named one reads as "we did not measure this". The summary also states how many
assets each baseline covered, because one computed on one asset out of five is
not comparable with one computed on all five.

### 4.8 What came from comparing against Prism

The evaluation work was prompted by comparing this project against a separate
implementation of the same use case. Taken from it: the metric definitions above,
the baseline set, the ablation "unavailable" discipline, and honest degradation
reporting.

**Deliberately not taken: the curiosity gap.** Prism asserts that a clip must cut
*before* the payoff — `elision_point < resolution_ts`. This project's
self-containment floor drops fragments for the opposite reason. These are
contradictory product theses, and adopting theirs means reversing ours, not
adding a feature.

**Deliberately not taken: quote grounding.** Prism requires the model's quoted
text to match the transcript at ≥0.90 similarity. It is a strictly stronger gate
than bounds-checking and catches a plausible hallucination pointing at a real
timestamp. It is not here because this pipeline is multimodal: Gemini watches
the video, so it can legitimately cite on-screen text nobody spoke, and a hard
drop would false-positive on exactly the demo and training sources recording
profiles exist to serve. **This is the strongest known gap in the current
validation.** The cheap path, if taken: add a `quote` field, transcribe only
the 3 selected windows using the machinery captions already uses, and start it
advisory before making it a gate.

**Deliberately not taken: content-hash caching.** Prism caches because it mines
once and fans out over personas. This call is audience-conditioned, so there is
nothing audience-neutral to cache until mining is split from selection.

**Deliberately not taken: cassettes.** `AI_PROVIDER=fake` already gives the
offline loop; cassettes would add real response shapes over placeholders — a
modest fidelity gain for a new mechanism.

### 4.9 Tier 4: ablation over cached candidates only

**Decision.** The ablation re-runs *selection only*, against candidates a real
run already produced. Rows that need a fresh analysis report as **unavailable
with a reason**, never as a delta of zero.

**Why unavailable rather than zero.** A delta of zero reads as "this component
does not matter", which is the opposite claim from "we did not test it". That
confusion is how a component gets deleted for looking useless.

**What this cannot measure, stated in the output.** The prompt, the
recording-type guidance, and audience conditioning all shape the analysis call,
so ablating them needs new Gemini calls. Snapping needs the clips re-cut — it is
measured instead by `clean_cut_rate` in the run report.

**Sub-decision: the weights ablation clones its candidates.** `rank_candidates`
writes `Candidate.score` in place, so ablating on shared objects would leave
every later row scoring against the ablated values — the ablation would
contaminate its own control. There is a test for this.

**Known limitation.** Discarded candidates are not stored, so the
`self_contained_floor` row run against live data compares the clips that shipped
against the clips that shipped. The CLI states this in its output. Fixing it
properly means persisting rejected candidates, which is a schema change not yet
taken.

### 4.10 Tier 5: the gate scores recorded fixtures, not live runs

**Decision.** `python -m app.evaluation gate` reads committed annotations and
committed predictions. No database, no media, no FFmpeg, no API key. Runs on
every pull request.

**Why recorded, not live.** A gate that re-ran the pipeline would need a Gemini
key in CI, cost a call per pull request, and produce a different number every
run for reasons unrelated to the change under review. Recorded predictions make
it deterministic: the same commit always scores the same, so a moved number is
always the diff's fault.

**What this costs, deliberately.** The gate measures selection and ranking
against a frozen candidate set, not the prompt that produced them. Changing the
prompt requires re-recording `runs/` by hand — which is right, because that is a
change somebody should look at rather than have averaged into a pass.

**Sub-decision: an empty corpus fails.** Every threshold is trivially satisfied
when there is nothing to score. A gate that goes green when its own inputs
vanish is worse than no gate.

**Sub-decision: an asset with annotations and no run scores zero, not skipped.**
Skipping lets a change that stops producing output for one asset *raise* the
corpus average.

**Sub-decision: a baseline that could not be computed fails the check that names
it.** Not treated as beaten.

**Sub-decision: two thresholds, and `beat_baselines` is the durable one.**
`min_precision` is an absolute floor that has to be re-tuned as the corpus
grows. "Better than picking spans by the clock" does not.

**Sub-decision: `GATE_K = 3`.** The product cuts three clips by default.
Scoring at a K it never returns would measure a configuration nobody runs.

### 4.11 The current fixtures are synthetic, and say so

The two committed assets are hand-built, not annotated from real video. This is
stated in each file's `note` field and in the fixtures README.

**Why ship them anyway.** The gate's own failure modes need testing, and a gate
with no corpus cannot be tested at all. They are scaffolding for the mechanism,
not evidence about the pipeline.

**What must happen next.** Replace them with real annotated sources. Until then
the gate protects the selection and ranking rules against regression, and proves
nothing about clip quality.

### 4.12 What the first numbers say

Run `python -m app.evaluation gate` for the current figures. As committed:

| | Precision@3 |
| --- | --- |
| Pipeline | 0.833 |
| `uniform` baseline | 0.000 |
| `random` baseline | 0.000 |

Both media-dependent baselines report as unavailable in the gate, because it has
no video files. See [4.13](#413-first-real-run-2026-08-23) for what happened when
they were run against one.

### 4.13 First real run (2026-08-23)

*Amends [4.12](#412-what-the-first-numbers-say), which said `audio_peak` had
never been run against a real asset. It has now. The result did not settle the
question, for a reason worth recording.*

**The asset.** NASA "Artemis II: Mission Overview", ingested by URL through
yt-dlp, analysed by `gemini-3.6-flash`, one run, general/informative/webinar.
60.1s, 1920x1080, VP9. The run completed in 57s and produced one clip
(22.0–60.1s). Everything below came out of the run's own report; none of it
needed an annotator.

**Finding 1: snapping cannot run on this source, and the report said so
correctly.** `silencedetect` found **zero** silences — not at the configured
-30dB, and not at -40, -50 or -60dB either. It is a trailer with wall-to-wall
music, so there is no pause anywhere in it to cut on.

This is the case [3.3](#33-cut-points-snap-to-silence-not-to-a-transcript) was
built to handle and the case its tests could never reach. The important part is
what the report printed: `snap.move_rate 0.0` over **zero** considered
boundaries, which the UI renders as *"not attempted"*. The deliberate choice in
`media_service.snap_window` not to count "no silences at all" as two boundaries
that declined to move is what keeps that distinct from *"attempted, 0% success"*
— and those call for opposite responses. Confirmed independently by
`clean_cut_rate 0.0`: the clip's opening measured +0.3dB against its own
average, meaning it opens at full programme level.

**Consequence, not yet acted on.** Music-bedded sources are a real category —
trailers, sizzle reels, promotional cuts — and for all of them the snapping
feature is inert. Cutting them well needs a different signal than silence.
Recording it here rather than fixing it: the fix is a new detector, which is a
larger decision than this entry.

**Finding 2: `audio_peak` ran, and the source was too short for the answer to
mean anything.** Against the pipeline's own pick, best tIoU was:

| | tIoU vs the pipeline's clip |
| --- | --- |
| `uniform` | 0.953 |
| `audio_peak` | 0.852 |
| `random` | 0.653 |

Read naively, that says picking a window by the clock matches Gemini better than
Gemini matches itself, which would be devastating. It says no such thing. A
38.1s clip in a 60.1s video can only start somewhere in a 22-second range, and
across *every* position in that range the tIoU against the pipeline's pick runs
0.268–1.000 with a mean of 0.579 — **58% of all possible clip positions score
above the 0.5 match threshold**. The same clip length in a one-hour source:
0.7%.

So on a 60-second asset the metric has almost no discriminating power, and all
three baselines score highly for arithmetic reasons rather than for finding
anything. The comparison is not evidence either way.

**Decision this forces: evaluation assets need a minimum duration.** An asset
where most positions trivially match is an asset that inflates every score in
the table, including the pipeline's. The corpus should require sources long
enough that a clip occupies a small fraction of them — as a rule of thumb, at
least 20× the clip length, which puts the trivial-match rate under about 5%.
Not yet enforced in `load_fixtures`; recorded here so the next person adding an
asset does not add a short one.

**What this run did establish.** URL ingestion, real Gemini analysis, validation,
ranking, cutting, and the report all work end to end on real third-party input.
The report earned its place on its first real run by surfacing two things
nothing else in the system would have shown: that snapping was inert, and that
the resulting cut was measurably not clean. Both were true before this work and
both were invisible.

**Still unanswered.** Whether the pipeline beats `audio_peak` on a source long
enough to tell. That remains the strongest open question about this project, and
it now needs one long annotated asset rather than any more code.

### 4.14 Dead code deleted (2026-08-23)

**Decision.** Six unreferenced things removed: `divergence()`,
`silence_boundary_spans()`, `labelled_spans()`, the whole of
`frontend/src/history.ts`, and the unused `checkHealth()` /
`getFeedbackSummary()` API clients with their now-orphaned types.

**Why.** Each had zero callers. Two of them had passing tests, which is what
made them invisible: a green suite over code nothing invokes reads as coverage.
Unreferenced code is also unaudited — nobody reviews the branch that never runs
— so it is a liability rather than an asset in waiting.

`history.ts` is the interesting one. Its own docstring explained that it existed
because "the API exposes no list endpoints", building the dashboard's totals
from browser localStorage. That stopped being true when `/api/videos`,
`/api/jobs` and `/api/teasers` landed, and the module was orphaned by that
change without anyone noticing. It was 133 lines of per-user storage handling
with quota fallbacks and a runtime type guard, all of it unreachable.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| Wire `divergence` into the harness instead | It answers a real question — does the audience setting change the output, or only the prompt? — but wiring it needs several runs of the same video across audiences, which is a feature, not a hookup. Deleting it now and rebuilding it against a real requirement beats leaving a function nothing calls. `git log` is the archive. |
| Keep `silence_boundary_spans` as a fifth baseline | It was written to isolate the snapping feature. [4.13](#413-first-real-run-2026-08-23) then showed snapping is already measured directly by `clean_cut_rate`, on every run, with no baseline needed. |
| Keep the API clients for a future UI | A client function with no caller is a guess about a screen nobody has designed. Both endpoints still exist and are tested; re-adding four lines when a screen needs them is cheaper than carrying them. |
| Leave `history.ts` in place | Superseded, not merely unused. Keeping it invites someone to wire it back up and reintroduce browser-local totals alongside the server-side ones. |

**What this costs.** Cross-audience divergence is now unmeasured, and it was the
only thing in the codebase that could have caught "the audience selector is
decorative". That gap is real and is recorded here rather than papered over. The
feedback summary endpoint is now server-only: `GET /api/teasers/feedback/summary`
works and is tested, but no screen shows how much of the corpus has been judged,
so a user cannot see their own labelling progress.

**How they were found.** Two AST sweeps — one for symbols referenced only from
`backend/tests`, one for exported TypeScript with no importer — rather than by
reading. Route handlers, pydantic validators and SQLAlchemy attributes are
invoked by name from a framework and never appear as plain references, so both
sweeps exclude them and every remaining hit was checked by hand.

---

## 5. Data model

### 5.1 Nullable per-run columns mean "use the server default"

**Decision.** `teaser_count`, `clip_max_seconds`, `aspect_ratio`,
`recording_type` are nullable; NULL means the default.

**Why not copy the default in at write time.** A run recorded before a setting
existed would then be indistinguishable from one that explicitly chose the value
that happened to be the default. Changing a server default must not rewrite
history.

### 5.2 The preview lives on `jobs`, not in `teasers`

**Decision.** Three flat columns, with a CHECK that all three are present or all
three are NULL.

**Why.** A preview has no window in the source, no rank and no score. As a
`teasers` row it would leave half the table NULL and change what the other half
means. It belongs to the run, not to any moment.

**Why the CHECK.** A row carrying a key with no size means the write was
interrupted, not that a preview exists.

### 5.3 `none_as_null` on every JSONB column

**Decision.** Spelled out explicitly on `chapters`, `keywords`, `captions`,
`pipeline_report`.

**Why.** SQLAlchemy's JSONB writes a Python `None` as the JSON value `null`
rather than SQL NULL by default. Those are different things to every reader of
the column and to the CHECK constraints, which allow an array or SQL NULL and
nothing else.

---

## 6. Security

### 6.1 A powerless login role, not `postgres`

**Decision.** The backend connects as `teaser_app`: `NOBYPASSRLS`, `NOINHERIT`,
no privileges of its own on `app.*`. It must `SET ROLE authenticated` to read
anything.

**Why.** Under `postgres`, RLS holds only as long as the application remembers
to scope every transaction — one missed path and the leak is silent. Under
`teaser_app` an unscoped transaction gets "permission denied". Fail closed.

### 6.2 SSRF checked at `connect()`, not at parse time

**Decision.** URL ingestion validates the address when the socket is opened, and
the check is thread-local.

**Why at connect.** Parse-time validation is defeated by a redirect to a
link-local metadata endpoint and by DNS rebinding.

**Why thread-local.** The app legitimately dials private addresses — the
database — constantly.

### 6.3 Media behind an ownership check, not a static mount

**Decision.** Clips are served by a route that resolves them through the
caller's own RLS-scoped session. Someone else's clip is **not found**, not
forbidden.

**Why not forbidden.** A 403 confirms the id is real.

### 6.4 Feedback follows the same rules

Migration 0012 gives `teaser_feedback` the same treatment as the tables in 0001:
`enable` plus `force row level security`, one policy per command, and `UPDATE`
carrying both `USING` and `WITH CHECK` — without the latter a user could
reassign `user_id` and hand a row to someone else. There is a test that another
account cannot judge, or even see, a clip it does not own.

### 6.5 Scoping is re-applied per transaction, not per session

**Decision.** `SET LOCAL ROLE authenticated` and the caller's JWT claims are
bound to SQLAlchemy's `after_begin` event, so they are issued at the start of
every transaction on a session rather than once when it is opened.

**Why.** `SET LOCAL` and `set_config(..., is_local => true)` are
transaction-scoped by definition, and the service layer commits several times
during a single job. Setting the scope once means it survives until the first
commit and then silently stops applying — and what it falls back to is the login
role, so the failure is not an error but a quietly unscoped connection. Binding
to transaction start also means the scope is torn down when the transaction
ends, which is what stops a pooled connection carrying one user's identity into
the next user's request.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| Set the role once per session | Fails after the first commit, and fails open rather than loudly. This is the bug the decision exists to prevent |
| A fresh connection per user | Correct, and throws away pooling for a property two statements already give |
| `SET ROLE` without `LOCAL` | Persists past the transaction and onto the pooled connection, which is the leak stated above with the sign reversed |

**What this costs.** Two extra statements at the start of every transaction.
The user id goes in as a bound parameter rather than interpolated, so it cannot
reach SQL as text; the role name is a module constant for the same reason, since
`SET ROLE` takes an identifier and not a parameter.

---

## 7. Testing and CI

### 7.1 Real Postgres, not SQLite

**Decision.** The suite runs against a real Postgres.

**Why.** The security model is RLS plus a powerless login role. Neither exists
in SQLite, so a suite that mocked them would pass while the property it claims
to protect was broken.

**What this costs.** Contributors need Docker. Accepted; the alternative is a
green suite over an untested security boundary.

### 7.2 The suite refuses to guess a database

**Decision.** `TEST_DATABASE_URL` and `TEST_ADMIN_DSN` are both required, with
no defaults.

**Why.** Every test truncates `app.videos`, `app.jobs`, `app.teasers` and now
`app.teaser_feedback`. They once defaulted to the development database and a
local `pytest` run wiped a working account's entire history. Both are required
because the admin DSN issues the TRUNCATE — letting it fall back while the app
URL was set would send writes to a scratch database and the truncation to the
real one.

### 7.3 The gate is a separate CI job

**Decision.** `evaluation` runs alongside `backend` and `frontend`, with no
Postgres service and no FFmpeg install.

**Why separate.** It answers a different question. Every test in the backend
suite can pass while the clips get worse; the gate is the only thing that
catches that. Keeping it separate also keeps it fast — no database, no apt
install — which is what makes running it on every pull request reasonable.

---

## 8. Rejected wholesale

Things deliberately not in this project, recorded so the absence reads as a
decision rather than an oversight.

| Not built | Why |
| --- | --- |
| Kafka / Kubernetes / Celery | One process, one job at a time. See [1.1](#11-in-process-jobs-not-a-queue). |
| A vector database | Nothing here does similarity search. Moments are found by a model watching the video, not by retrieval. |
| Speaker diarization | Would improve moment boundaries on panels. Real work, no current demand. |
| Slide / screen OCR | Would help the demo profile. Gemini already sees the frames, so the marginal value is unclear. |
| Multi-language output | The prompt and the caption pipeline are English-shaped. |
| LLM-as-judge scoring | Tempting for scale. Not built because the obvious implementation judges with the model that generated the output, which measures self-consistency. If added: a different model, and treated as triage for human review rather than as ground truth. |
| Quote grounding | See [4.8](#48-what-came-from-comparing-against-prism). The strongest known gap. |

---

## 9. Documentation

### 9.1 A hand-written API reference, alongside the generated schema (2026-08-23)

**Decision.** [API.md](API.md) is the committed HTTP contract: endpoints,
request payloads, the error envelope, the status vocabularies, the
`pipeline_report` shape, and the outbound connections. Written by hand and kept
next to the generated OpenAPI schema at `/docs`, not instead of it — the file
says so in its opening lines and defers to the schema on field types.

**Why.** Two reasons, and the second is the one that decided it.

The first is that the reference the code already cited did not exist.
`schemas.py`, `errors.py` and `models.py` each point a reader at an
`API_DESIGN.md` that is not in this repository, so the authoritative description
of the API was a filename. That is worse than no reference, because it reads as
one.

The second is that the things a caller actually gets wrong are things a schema
cannot express. That a missing row is `404` and never `403`, and that this is a
deliberate refusal to confirm an id rather than an oversight. That `202` on two
routes means "poll, the bytes do not exist yet", and which field to poll on.
That `preview_url` is the single test for whether there is anything to play,
because it is present only alongside its two companions. That a null
`aspect_ratio` means "show the server default", not "16:9 was chosen". And above
all that **the run-time failure codes never appear as an HTTP status at all** —
`AI_ANALYSIS_FAILED`, `NO_SELF_CONTAINED_MOMENTS` and the rest land on
`error_code` in a job body long after the request that started the run returned
`202`. A client written against the OpenAPI schema alone would not know those
codes exist.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| The generated OpenAPI schema alone | It is always in sync, which is a real advantage this file gives up. But it can only describe shapes: every property in the paragraph above is invisible to it, and the run-time codes are not in it at any point because they are not response statuses. |
| Recreate `API_DESIGN.md` under its old name | The content behind that name is not in git history at that path. Recreating the name means writing a new document and presenting it as the one the code has been citing, which makes the citation retroactively true rather than honest. A new file under a new name leaves the dangling references visible as what they are. |
| Generate the prose from the schema at build time | A generator plus a CI step, and the output would omit exactly the reasoning that motivated writing anything. The parts worth documenting are the parts no generator can see. |
| Fold it into README.md | README answers "what is this and why would I run it". Sixteen endpoints, seven drop-reason slugs and an error-code table would bury that. |

**What this costs.** A second place to update when a route changes, with nothing
enforcing that it happens — no test asserts that API.md matches the routes, and
the honest expectation is that it will drift before anything notices. The
generated schema does not have this problem and is the one to trust when the two
disagree; API.md says so itself.

**Deliberately not done: the dangling `API_DESIGN.md` references were left in
place.** Four source files still cite a document that does not exist —
`backend/app/schemas.py`, `backend/app/errors.py`, `backend/app/models.py`, and
`frontend/src/types.ts`, the last of which names a path (`docs/API_DESIGN.md`)
rather than only a filename. Repointing them at API.md is a four-line change and
it is not in this one, because it edits source in a task scoped to
documentation. Recorded here so the next person reads it as pending rather than
as missed.

---

## 10. Frontend

*Added 2026-08-23. The frontend had no section in this file until now, which is
why several of these entries describe choices made a long time before they were
written down. Where that is the case the entry says so rather than implying the
reasoning is contemporary.*

### 10.1 Four runtime dependencies, and no framework above them

**Decision.** `react`, `react-dom`, `@supabase/supabase-js`, `lucide`. No
router, no state library, no data-fetching library, no component kit, no CSS
framework. Screens are plain components, state lives in `App.tsx`, styling is
one hand-written `styles.css`.

**Why.** The application is one flow — source, options, processing, teasers —
plus four listing pages over four endpoints. That is a shape where a router and
a query cache are more concept than the app contains, and the two things they
would genuinely have solved are solved in about seventy lines by `useViewRoute`
and `useAsync`.

**Alternatives rejected.**

| Option | Why not |
| --- | --- |
| React Router | Six destinations with no nested routes, no params and no loaders. `useViewRoute` is a `hashchange` listener |
| TanStack Query | Its value is caching, invalidation and background refetch across many overlapping queries. Here each page loads one thing, and the run poll is a deliberate interval rather than something to be managed |
| Redux / Zustand | The state is one screen's worth and it already lives at the top of the tree |
| A component library | It would arrive with its own design language, and the visual system here is deliberate |

**What this costs.** `App.tsx` is 850 lines and carries the whole run flow,
which is the honest price: nothing forces it to be split, so it grows by
default. A second flow of comparable weight is the point at which this decision
should be revisited rather than defended.

### 10.2 The run is polled, not pushed

**Decision.** A 1.5s interval on the job while a run is in flight, and a
separate 2.5s interval on the video row during URL ingestion, which gives up
after 20 minutes.

**Why.** The backend runs jobs in-process ([1.1](#11-in-process-jobs-not-a-queue)),
so there is no broker to publish from and a socket would need its own
authenticated lifecycle for a status integer that changes six times. The two
intervals differ because the two waits do: a fetch is a slow server-side
download, and polling it as fast as a run would triple the requests to learn
the same thing later.

**Why the fetch poll gives up and the job poll does not.** A timed-out fetch
says the download *may still be running* and points the reader at the Videos
page — this tab stopped watching, which is not the same as the work failing, and
claiming failure would be a lie about server state the client cannot see.

**Alternatives rejected.** Server-sent events or a websocket, for the reasons
above; and a single shared interval for both waits, which would make one of the
two wrong.

**What this costs.** Up to 1.5 seconds of staleness on the progress bar, and a
request every 1.5 seconds for the minutes a run takes. Both timers are cleared
on unmount, because a poll outliving its component sets state on nothing and
keeps hitting the API.

### 10.3 Authenticated media is fetched and handed over as a blob

**Decision.** `useAuthedMedia` fetches the clip with the access token and gives
the `<video>` element an object URL, revoking it on unmount. One hook, shared by
teaser clips and the run preview.

**Why.** Media sits behind an ownership check
([6.3](#63-media-behind-an-ownership-check-not-a-static-mount)) and a
`<video src>` cannot carry an `Authorization` header. Without the revoke, every
re-render of a list leaks a copy of the video.

**Why one hook for two artifacts.** They are different routes serving different
things, but the loading problem is identical and the leak is easy to reintroduce
by writing it a second time.

**Alternatives rejected.** A signed URL with a short expiry, which would let the
element load the bytes directly — it means a second auth mechanism alongside the
access token, and a URL that works for whoever holds it is exactly the property
the ownership check exists to remove. Reverting to a static mount is
[6.3](#63-media-behind-an-ownership-check-not-a-static-mount) in reverse.

**What this costs.** The whole clip is in memory before the first frame plays,
so there is no range-request streaming and no seeking ahead of the download.
Acceptable for clips capped at 180 seconds; it would not be for the source video.

### 10.4 `data === null` means not loaded, never loaded-and-empty

**Decision.** `useAsync` distinguishes the three states every listing page has,
and `AsyncBoundary` renders them. Children are a function, so a page receives
data that is already non-null.

**Why.** Without something shared, pages drift: one shows a spinner forever on a
401, another renders an empty list and implies the account has no work in it.
"You have no clips" and "we could not ask" look identical, and only one of them
is the reader's fault to fix — so a failure renders as a failure, with the error
code and a retry.

**Sub-decision: a failed reload drops the stale data.** Showing last week's list
beside an error message invites the reader to trust it.

**Sub-decision: the loading state keys on `data`, not on `loading`.** A refresh
therefore leaves the current page on screen instead of blanking something the
reader is in the middle of using.

**What this costs.** Every page pays a render-prop indirection, and `useAsync`
takes an explicit dependency array because `load` is a fresh closure each render
— a wrong array is a stale fetch, and nothing catches it.

### 10.5 Generation defaults live in `localStorage`, per user

**Decision.** Audience, style, aspect ratio, clip count and clip length are
remembered in the browser, namespaced by user id. Every field is revalidated on
read, and each falls back independently.

**Why.** These decide which radio button starts selected. A preference that
needs a migration, a column and an endpoint to change the initial value of a
form is not worth any of the three. Namespaced by user because two accounts can
share a browser.

**Why revalidate.** `localStorage` is user-writable, so a stored value is not
trusted to be in range or to be a number at all. The bounds mirror the API's, so
a stored value can never be one the server would reject. Checking each field
separately means a value left over from an older build falls back on its own
instead of discarding the others with it.

**Alternatives rejected.** A `user_preferences` table — the schema and endpoint
cost above, for defaults nobody needs on a second device; and trusting the
stored JSON, which hands form state to whatever is in the browser.

**What this costs.** Defaults do not follow a user across browsers or devices,
and clearing site data resets them. A failed write is swallowed, because a full
or disabled storage must not break the settings screen or generation.

### 10.6 A verdict is optimistic and reverts

**Decision.** Keep/discard updates the button immediately, writes in the
background, and rolls back if the write fails. Clicking the active verdict
withdraws it.

**Why.** This is the evaluation corpus being collected one click at a time
([4.5](#45-tier-1-labels-collected-from-the-product-not-from-an-annotation-sprint)),
and a spinner between the click and the state change is enough friction to stop
people giving verdicts at all. The initial value comes from the clip's own
`feedback` field, so the control is correct on first paint rather than flicking
from unjudged to judged.

**Why a toggle rather than a third button.** Someone who mis-clicked should be
able to undo without a separate control, and a withdrawn verdict is better
ground truth than one they did not mean.

**What this costs.** For the moment between click and response the UI states
something the server has not confirmed. The failure path reverts, but a user who
navigates away in that window keeps a verdict that was never stored.

### 10.7 The run report shows "not attempted" and "not measured" as first-class answers

**Decision.** `RunReportPanel` computes the number of boundaries snapping
actually considered and prints *not attempted* when it is zero, rather than
`0%`. The same distinction is made for cut quality. The panel does not render at
all on runs from before the report existed.

**Why.** Zero considered boundaries and zero successful moves call for opposite
responses — the first means the feature never ran, the second means it ran and
found nothing. [4.13](#413-first-real-run-2026-08-23) is the run where that
distinction was the finding, and a UI that collapsed them would have hidden it.
Absent rather than empty for old runs, because a panel headed "nothing was
discarded" is a claim, and the truthful statement about those runs is that
nobody counted.

**Sub-decision: unknown slugs fall through to their raw value.** A drop reason
or degradation tag added on the server is visible here before anyone updates the
label map, so the backend can add a counter without a coordinated frontend
change.

**Alternatives rejected.** A chart — these are small integers read against each
other, and seven bars add a legend without adding a fact.

**What this costs.** Two label maps that drift from the server's vocabulary and
show slugs until someone notices. That is the intended failure, but it is still
a thing to notice.

---

## Keeping this file current

**This file is updated as part of every substantive change to the project, in
the same commit as the change.** Not afterwards, and not in a separate
documentation pass — a decision recorded a week later is recorded from memory.

### What counts as substantive

Add or amend an entry when a change:

- introduces a new capability, subsystem, or dependency;
- changes a schema, an API shape, or a stored format;
- alters a tuned constant, a threshold, or a scoring rule;
- picks one approach where a reasonable person would have picked another;
- **reverses or narrows an existing entry** — amend that entry in place, and
  state what changed the answer;
- deliberately does *not* do something an obvious reading of the task implies.

Do not add an entry for a typo, a rename, a formatting change, or a fix whose
reasoning is visible in the diff.

### The shape of an entry

Four things, in this order. An entry missing the third is not finished.

1. **Decision** — what the code now does, in one or two sentences.
2. **Why** — the reasoning, including the specific failure it prevents.
3. **Alternatives rejected** — what else was considered and the reason against
   each. A table when there are three or more.
4. **What this costs** — what was given up. Every real decision has a cost; an
   entry claiming none is usually an entry that has not found it yet.

Write the reason, not the rule. "Dropped, never repaired, because a silently
corrected hallucination destroys the drop-rate signal" is useful; "we drop
invalid candidates" restates the code.

State limitations plainly, in the entry rather than in a footnote. Section
[4.12](#412-what-the-first-numbers-say) says the headline claim is not yet
supported; that sentence is worth more than the table above it.

### Instructions for Claude Code

This is a standing instruction for every session in this repository, restated in
`CLAUDE.md` and injected at session start by a hook in `.claude/settings.json`.

Before finishing any task that changed code:

1. Re-read the section of this file covering what you touched.
2. If the change meets the criteria above, add or amend an entry in the same
   commit, using the four-part shape.
3. Date new top-level sections. Amendments to an existing entry note what
   changed and why, rather than silently overwriting the earlier reasoning.
4. If a change contradicts an existing entry, **say so in your reply to the
   user** rather than quietly rewriting it. A reversal is a decision, and the
   user should know one was made.
5. If the change was not substantive, say in your reply that no entry was needed
   — so the reader knows the file was considered rather than forgotten.
