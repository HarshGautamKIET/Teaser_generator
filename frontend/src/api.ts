/** Backend client. All network access goes through here. */

import { accessToken } from "./supabase";
import {
  ApiError,
  type ApiErrorBody,
  type Audience,
  type GenerateResponse,
  type JobListResponse,
  type JobResponse,
  type LibraryResponse,
  type PipelineOptions,
  type Style,
  type TeaserListResponse,
  type VideoListResponse,
  type VideoResponse,
  type VideoUploadResponse,
} from "./types";

const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

/** Every endpoint requires a verified caller, so a missing session is a client
 *  side error rather than a request that will certainly 401. */
async function authHeader(): Promise<Record<string, string>> {
  const token = await accessToken();
  if (!token) {
    throw new ApiError("NOT_AUTHENTICATED", "Your session has ended. Sign in again.", 401);
  }
  return { Authorization: `Bearer ${token}` };
}

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }

  // Every backend failure uses the same envelope; fall back if something else
  // (a proxy, a crash) responded instead.
  let code = "REQUEST_FAILED";
  let message = `Request failed with status ${response.status}.`;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code;
      message = body.error.message;
    }
  } catch {
    /* keep the fallback message */
  }
  throw new ApiError(code, message, response.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { ...(init?.headers ?? {}), ...(await authHeader()) };

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      "Could not reach the backend. Is the API running?",
      0,
    );
  }
  return parse<T>(response);
}

export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<VideoUploadResponse> {
  const headers = await authHeader();

  // XMLHttpRequest rather than fetch: it reports upload progress, which matters
  // for the large source files this tool accepts (FR-018).
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/videos/upload`);
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body as VideoUploadResponse);
        } else {
          reject(
            new ApiError(
              body?.error?.code ?? "UPLOAD_FAILED",
              body?.error?.message ?? "The upload failed.",
              xhr.status,
            ),
          );
        }
      } catch {
        reject(new ApiError("UPLOAD_FAILED", "The upload failed.", xhr.status));
      }
    };

    xhr.onerror = () =>
      reject(
        new ApiError(
          "NETWORK_ERROR",
          "Could not reach the backend. Is the API running?",
          0,
        ),
      );

    xhr.send(form);
  });
}

/** Fetches a teaser's MP4 and returns an object URL for it.
 *
 *  Teaser media is behind an ownership check, and a <video src> cannot carry an
 *  Authorization header -- so the bytes are fetched here and handed to the
 *  element as a blob. Callers own the returned URL and must revoke it. */
export async function fetchTeaserMedia(path: string): Promise<string> {
  const headers = await authHeader();

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Could not load the teaser video.", 0);
  }
  if (!response.ok) {
    return parse<never>(response);
  }
  return URL.createObjectURL(await response.blob());
}

export function getVideo(videoId: string): Promise<VideoResponse> {
  return request<VideoResponse>(`/videos/${videoId}`);
}

/** Queue a fetch of a video from a URL.
 *
 *  Answers 202 with a video that is still `fetching`: the row exists, the bytes
 *  do not. Callers poll `getVideo` until the status changes. */
export function ingestFromUrl(url: string): Promise<VideoResponse> {
  return request<VideoResponse>("/videos/from-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export function startGeneration(
  videoId: string,
  audience: Audience,
  style: Style,
  options: PipelineOptions = {},
): Promise<GenerateResponse> {
  return request<GenerateResponse>(`/videos/${videoId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audience, style, ...options }),
  });
}

export function getJob(jobId: string): Promise<JobResponse> {
  return request<JobResponse>(`/jobs/${jobId}`);
}

/** Teasers from one run. Without `jobId` the backend answers with the latest
 *  completed run for that video, which is what the generate flow wants. */
export function getTeasers(
  videoId: string,
  jobId?: string,
): Promise<TeaserListResponse> {
  const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return request<TeaserListResponse>(`/videos/${videoId}/teasers${query}`);
}

export function listVideos(): Promise<VideoListResponse> {
  return request<VideoListResponse>("/videos");
}

export function listJobs(videoId?: string): Promise<JobListResponse> {
  const query = videoId ? `?video_id=${encodeURIComponent(videoId)}` : "";
  return request<JobListResponse>(`/jobs${query}`);
}

/** Every clip the caller owns, across every run. */
export function listTeasers(): Promise<LibraryResponse> {
  return request<LibraryResponse>("/teasers");
}

export function checkHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}
