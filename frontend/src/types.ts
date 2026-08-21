/** Shapes returned by the backend. Mirrors docs/API_DESIGN.md. */

export type Audience = "general" | "developers" | "business_leaders" | "students";
export type Style = "informative" | "promotional" | "emotional";

/** Output shapes a run may ask for. Mirrors backend/app/domain.py AspectRatio;
 *  the backend rejects anything outside this set. */
export type AspectRatio = "16:9" | "9:16" | "1:1" | "4:3" | "4:5";

export const DEFAULT_ASPECT_RATIO: AspectRatio = "16:9";

export type JobStatus =
  | "queued"
  | "validating"
  | "analyzing"
  | "ranking"
  | "generating"
  | "completed"
  | "failed";

export interface VideoUploadResponse {
  video_id: string;
  filename: string;
  status: string;
}

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

/** A video is only usable once it reaches "ready". A URL fetch sits in
 *  "fetching" until the bytes land, which can take minutes for a long talk. */
export type VideoStatus = "fetching" | "uploaded" | "ready" | "failed";

/** Per-run pipeline settings. Omitted fields fall back to the server default. */
export interface PipelineOptions {
  teaser_count?: number;
  clip_max_seconds?: number;
  aspect_ratio?: AspectRatio;
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
  /** Free-text direction given for this run, or null. */
  custom_prompt: string | null;
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
}

export interface TeaserListResponse {
  teasers: Teaser[];
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
};
