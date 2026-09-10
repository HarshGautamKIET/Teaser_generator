# Evaluation fixtures

What the CI gate reads. Three directories, all committed, all small.

```
ground_truth/<asset>.json   spans a good run should have selected
runs/<asset>.json           spans a recorded run actually selected
thresholds.json             what the gate requires
```

The gate scores `runs/` against `ground_truth/` and fails the build when the
result misses a threshold. It reads only these files -- no database, no media,
no FFmpeg, no API key -- which is what lets it run on every pull request.

```bash
cd backend && python -m app.evaluation gate
```

## Adding an asset

1. Annotate the source. One entry per moment that should have been selected:

   ```json
   {
     "asset_id": "webinar-2026-platform",
     "duration_seconds": 3200.0,
     "origin": "annotation",
     "spans": [
       { "start": 412.0, "end": 455.0, "why": "the migration cost figure", "strength": 3 }
     ]
   }
   ```

   `strength` is 1-3 confidence. It is stored but not yet used: a weighted
   variant should cost more for missing a 3 than a 1, and that is impossible to
   add later if the distinction was never recorded.

2. Record a run against it. Point the CLI at a real job and paste the spans:

   ```json
   { "asset_id": "webinar-2026-platform", "spans": [{ "start": 410.5, "end": 452.0 }] }
   ```

   Rank order, not chronological. Precision@K takes the first K, so the list has
   to carry the pipeline's own confidence.

3. Re-run the gate and update `thresholds.json` **only if the new number is an
   improvement**. Lowering a threshold to make a red build green is how a gate
   stops meaning anything; if the score dropped, the prompt regressed.

An asset with annotations and no recorded run scores zero rather than being
skipped. Skipping it would let a change that stops producing output for one
asset raise the corpus average.

## Why the fixtures are recorded rather than generated

A gate that re-ran the pipeline would need a Gemini key in CI, would cost a call
per pull request, and would produce a different number every run for reasons
that have nothing to do with the change under review. Recorded predictions make
the gate deterministic: the same commit always scores the same, so a moved
number is always the diff's fault.

The cost is that the gate measures the *selection and ranking* rules against a
frozen set of candidates, not the prompt that produced them. Changing the prompt
requires re-recording `runs/` by hand -- deliberately, since that is a change
whose effect somebody should look at rather than have averaged into a pass.
