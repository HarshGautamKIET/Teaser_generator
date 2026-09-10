/** Shapes returned by the backend. Mirrors docs/API_DESIGN.md. */

export type Audience = "general" | "developers" | "business_leaders" | "students";
export type Style = "informative" | "promotional" | "emotional";

/** Output shapes a run may ask for. Mirrors backend/app/domain.py AspectRatio;
 *  the backend rejects anything outside this set. */
export type AspectRatio = "16:9" | "9:16" | "1:1" | "4:3" | "4:5";

export const DEFAULT_ASPECT_RATIO: AspectRatio = "16:9";

/** What kind of recording the source is. Mirrors backend/app/domain.py
 *  RecordingType, and selects a pipeline profile there: how self-contained a
 *  moment has to be, how far apart clips are spaced, and whether a frame is
 *  cropped or padded to reach the output shape.
 *
 *  Distinct from `SourceType` below, which is how the bytes arrived. */
export type RecordingType = "webinar" | "demo" | "training";

/** The shape the pipeline's defaults were tuned for. */
export const DEFAULT_RECORDING_TYPE: RecordingType = "webinar";

export type JobStatus =
  | "queued"
  | "validating"
  | "analyzing"
  | "ranking"
  | "generating"
  | "completed"
  | "failed"
  | "cancelled";

export interface VideoUploadResponse {
  video_id: string;
  filename: string;
  status: string;
}

/** How a video's bytes arrived. Not to be confused with `RecordingType`. */
export type SourceType = "upload" | "url";

export interface VideoResponse extends VideoUploadResponse {
  size_bytes: number;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  error_message: string | null;
  source_type: SourceType;
  source_url: string | null;
}

/** Per-run pipeline settings. Omitted fields fall back to the server default. */
export interface PipelineOptions {
  teaser_count?: number;
  clip_max_seconds?: number;
  aspect_ratio?: AspectRatio;
  recording_type?: RecordingType;
  custom_prompt?: string;
}

/** Matches the backend's max_length on GenerateRequest.custom_prompt. */
export const MAX_CUSTOM_PROMPT_CHARS = 500;

/** A source video as it appears in a listing: the detail shape plus the totals
 *  that only make sense once other runs exist. */
export interface VideoSummary extends VideoResponse {
  created_at: string;
  job_count: number;
  teaser_count: number;
}

export interface VideoListResponse {
  videos: VideoSummary[];
}

export interface GenerateResponse {
  video_id: string;
  job_id: string;
  status: JobStatus;
}

/** One caption line burned into a clip, timed from that clip's own start
 *  rather than from the source video. Empty on clips cut with captions off. */
export interface CaptionLine {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

/** One section of the source video, as the run described it. */
export interface Chapter {
  start_seconds: number;
  end_seconds: number;
  title: string;
}

/** What one run discarded, and how cleanly it cut what it kept.
 *
 *  Mirrors backend/app/services/pipeline_report.py. Loosely typed on purpose:
 *  the backend stores an open set of diagnostics that grows whenever a check is
 *  added to the pipeline, so `dropped` is an index signature rather than a
 *  closed union — a new reason should appear in the UI without a frontend
 *  change. */
export interface CandidateReport {
  proposed: number;
  kept: number;
  dropped: Record<string, number>;
  drop_rate: number;
}

export interface SnapReport {
  starts_moved: number;
  starts_kept: number;
  ends_moved: number;
  ends_kept: number;
  move_rate: number;
  mean_abs_shift_seconds: number;
}

/** How cleanly one clip begins. `delta_db` is the opening relative to the
 *  clip's own average loudness, so it measures the cut rather than the
 *  recording's gain. Strongly negative is good. */
export interface CutQuality {
  teaser_id: string;
  opening_db: number;
  clip_db: number;
  delta_db: number;
  clean: boolean;
}

export interface PipelineReport {
  candidates: Partial<CandidateReport>;
  snap: Partial<SnapReport>;
  cuts: CutQuality[];
  clean_cut_rate: number;
  /** Anything the run could not do but carried on without. */
  degraded: string[];
}

/** Human wording for the drop reasons the backend emits. An unknown key falls
 *  back to the slug rather than being hidden, so a reason added on the server
 *  is visible here before anyone updates this map. */
export const DROP_REASON_LABELS: Record<string, string> = {
  bounds: "Timestamps outside the video",
  too_short: "Shorter than the minimum",
  too_long: "Longer than the maximum",
  empty_text: "Missing title, hook, or reason",
  not_self_contained: "Needed surrounding context",
  too_close: "Too near a stronger moment",
  outranked: "Valid, but outranked",
};

/** Wording for the degradation tags. Same fallback rule as above. */
export const DEGRADED_LABELS: Record<string, string> = {
  no_summary: "The model returned no usable summary",
  fewer_clips_than_requested: "Fewer clips than requested were available",
  no_audio_track: "The source has no audio, so cut points were not snapped",
  no_preview_too_few_moments: "Too few moments to assemble a preview",
  preview_assembly_failed: "The preview could not be assembled",
};

export interface JobResponse {
  job_id: string;
  video_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  audience: Audience;
  style: Style;
  /** null on runs from before the shape was selectable. */
  aspect_ratio: AspectRatio | null;
  /** null on runs from before recording types existed, which the backend
   *  resolves to the default rather than backfilling a guess. */
  recording_type: RecordingType | null;
  /** Free-text direction given for this run, or null. */
  custom_prompt: string | null;
  /** What the run said about the video as a whole, written for its audience.
   *  null on runs that failed before analysis and on runs from before this
   *  existed; the two lists are empty rather than null in both cases. */
  summary: string | null;
  chapters: Chapter[];
  keywords: string[];
  /** The run's assembled preview: several moments joined with title cards,
   *  rather than one excerpt. null when the run made none — a preview needs at
   *  least two moments. The three fields are present together or not at all. */
  preview_url: string | null;
  preview_duration_seconds: number | null;
  preview_size_bytes: number | null;
  /** What this run threw away and why. null on runs from before the report
   *  existed, and on runs that failed before they had anything to report. */
  pipeline_report: PipelineReport | null;
  ai_provider: string | null;
  error_code: string | null;
  error_message: string | null;
}

/** A past run. Carries the source filename and timestamps that the polling
 *  shape has no use for but a history table cannot do without. */
export interface JobSummary extends JobResponse {
  filename: string;
  teaser_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface JobListResponse {
  jobs: JobSummary[];
}

export interface Teaser {
  id: string;
  title: string;
  hook: string;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number | null;
  score: number;
  scores: Record<string, number>;
  reason: string;
  rank: number;
  width: number | null;
  height: number | null;
  size_bytes: number;
  video_url: string;
  /** The words burned into the picture, readable without decoding the clip. */
  captions: CaptionLine[];
  /** The caller's own verdict on this clip, or null if they have not given
   *  one. Carried on the clip so the control renders in its correct state on
   *  first paint rather than flicking after a second request. */
  feedback: Verdict | null;
}

export interface TeaserListResponse {
  teasers: Teaser[];
}

/** Would you post this? Binary on purpose — a five-point scale collects a
 *  middle that no ranking change can be derived from. */
export type Verdict = "keep" | "discard";

export interface FeedbackResponse {
  teaser_id: string;
  verdict: Verdict;
  note: string | null;
  created_at: string;
  updated_at: string;
}


/** A clip in the cross-run library. `rank` alone says nothing once clips from
 *  different runs sit side by side, so each states where it came from. */
export interface LibraryTeaser extends Teaser {
  job_id: string;
  video_id: string;
  filename: string;
  audience: Audience;
  style: Style;
  created_at: string;
}

export interface LibraryResponse {
  teasers: LibraryTeaser[];
}

/** The uniform error envelope every failing endpoint returns. */
export interface ApiErrorBody {
  error: { code: string; message: string };
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const AUDIENCE_OPTIONS: { value: Audience; label: string; blurb: string }[] = [
  { value: "general", label: "General", blurb: "Broadly understandable moments" },
  { value: "developers", label: "Developers", blurb: "Technical insight and demos" },
  { value: "business_leaders", label: "Business Leaders", blurb: "Impact, ROI, strategy" },
  { value: "students", label: "Students", blurb: "Learning value and clarity" },
];

/** `frame` is the picker's preview box, sized to the ratio at a common height
 *  so the shapes are comparable at a glance. */
export const ASPECT_RATIO_OPTIONS: {
  value: AspectRatio;
  label: string;
  blurb: string;
  frame: { width: number; height: number };
}[] = [
  {
    value: "16:9",
    label: "Widescreen",
    blurb: "YouTube, web, presentations",
    frame: { width: 56, height: 32 },
  },
  {
    value: "9:16",
    label: "Vertical",
    blurb: "Shorts, Reels, TikTok",
    frame: { width: 20, height: 36 },
  },
  {
    value: "1:1",
    label: "Square",
    blurb: "Feed posts",
    frame: { width: 34, height: 34 },
  },
  {
    value: "4:5",
    label: "Portrait",
    blurb: "Instagram portrait",
    frame: { width: 28, height: 35 },
  },
  {
    value: "4:3",
    label: "Classic",
    blurb: "Slides and archive footage",
    frame: { width: 44, height: 33 },
  },
];

export const RECORDING_TYPE_OPTIONS: {
  value: RecordingType;
  label: string;
  blurb: string;
}[] = [
  { value: "webinar", label: "Talk or Webinar", blurb: "A speaker, distinct topics" },
  { value: "demo", label: "Product Demo", blurb: "Screen recording, shown results" },
  { value: "training", label: "Training", blurb: "Course taught in modules" },
];

export const STYLE_OPTIONS: { value: Style; label: string; blurb: string }[] = [
  { value: "informative", label: "Informative", blurb: "Facts and explanations" },
  { value: "promotional", label: "Promotional", blurb: "Curiosity and strong hooks" },
  { value: "emotional", label: "Emotional", blurb: "Story, surprise, reaction" },
];

/** Human-readable stage labels for the progress display (FR-018). */
export const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  validating: "Checking the video",
  analyzing: "Analysing with AI",
  ranking: "Ranking moments",
  generating: "Generating teasers",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};
