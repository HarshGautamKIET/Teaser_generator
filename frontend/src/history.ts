/** Run history, persisted in this browser.
 *
 *  The API exposes no list endpoints — only fetch-by-id — so the dashboard's
 *  aggregates are built from runs this browser has completed. Nothing here is
 *  synthesised: every field is copied from a real job or teaser response.
 *  History is per-browser and disappears if site data is cleared. */

import type { Audience, Style, Teaser } from "./types";

/** Per-user storage key.
 *
 *  Namespaced by user id because two accounts can share a browser: a single
 *  global key would show whoever signed in second the previous user's runs. */
function storageKey(userId: string): string {
  return `teaser-generator/runs/v2/${userId}`;
}

const MAX_RUNS = 100;

export interface RunRecord {
  /** Job id — also the dedupe key, so a run is never counted twice. */
  id: string;
  filename: string;
  /** ISO 8601, stamped when the run reached a terminal state. */
  completedAt: string;
  audience: Audience;
  style: Style;
  status: "completed" | "failed";
  teaserCount: number;
  /** Mean of the teaser scores, or null when the run produced none. */
  averageScore: number | null;
  totalClipSeconds: number;
  sourceSeconds: number | null;
}

function isRunRecord(value: unknown): value is RunRecord {
  if (typeof value !== "object" || value === null) return false;
  const run = value as Partial<RunRecord>;
  return (
    typeof run.id === "string" &&
    typeof run.filename === "string" &&
    typeof run.completedAt === "string" &&
    typeof run.teaserCount === "number" &&
    (run.status === "completed" || run.status === "failed")
  );
}

/** Reads persisted runs, newest first. Storage can be unavailable (private
 *  mode) or hold data from an older shape, so anything unreadable is dropped
 *  rather than crashing the app. */
export function loadRuns(userId: string): RunRecord[] {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(storageKey(userId));
  } catch {
    return [];
  }
  if (!raw) return [];

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRunRecord);
  } catch {
    return [];
  }
}

function save(userId: string, runs: RunRecord[]): void {
  try {
    window.localStorage.setItem(
      storageKey(userId),
      JSON.stringify(runs.slice(0, MAX_RUNS)),
    );
  } catch {
    /* Quota exhausted or storage disabled — history is a convenience, not a
       requirement, so a failed write must not break generation. */
  }
}

/** Prepends a run, replacing any earlier entry with the same job id. */
export function recordRun(userId: string, run: RunRecord): RunRecord[] {
  const next = [
    run,
    ...loadRuns(userId).filter((existing) => existing.id !== run.id),
  ];
  save(userId, next);
  return next.slice(0, MAX_RUNS);
}

export function clearRuns(userId: string): RunRecord[] {
  try {
    window.localStorage.removeItem(storageKey(userId));
  } catch {
    /* nothing to do — the caller resets its state either way */
  }
  return [];
}

/** Builds a run record from a completed job's teaser list. */
export function summariseRun(
  jobId: string,
  filename: string,
  audience: Audience,
  style: Style,
  sourceSeconds: number | null,
  teasers: Teaser[],
  completedAt: string,
): RunRecord {
  const clipSeconds = teasers.reduce(
    (total, teaser) =>
      total + (teaser.duration_seconds ?? teaser.end_seconds - teaser.start_seconds),
    0,
  );
  const averageScore =
    teasers.length > 0
      ? teasers.reduce((total, teaser) => total + teaser.score, 0) / teasers.length
      : null;

  return {
    id: jobId,
    filename,
    completedAt,
    audience,
    style,
    status: "completed",
    teaserCount: teasers.length,
    averageScore,
    totalClipSeconds: clipSeconds,
    sourceSeconds,
  };
}
