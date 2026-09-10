import { useCallback, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import {
  cancelJob,
  getJob,
  getTeasers,
  getVideo,
  ingestFromUrl,
  listJobs,
  listTeasers,
  listVideos,
  startGeneration,
  uploadVideo,
} from "./api";
import { toFailure, type Failure } from "./async";
import AppShell, {
  useViewRoute,
  type NavCounts,
  type View,
} from "./components/AppShell";
import DashboardScreen from "./components/DashboardScreen";
import LibraryScreen from "./components/LibraryScreen";
import LoginScreen from "./components/LoginScreen";
import NarrativePanel from "./components/NarrativePanel";
import OptionsPanel from "./components/OptionsPanel";
import PreviewCard from "./components/PreviewCard";
import ProgressPanel from "./components/ProgressPanel";
import RunDetailScreen from "./components/RunDetailScreen";
import RunsScreen from "./components/RunsScreen";
import SettingsScreen from "./components/SettingsScreen";
import Stepper, { type Step, type StepId } from "./components/Stepper";
import TeaserCard from "./components/TeaserCard";
import UploadPanel from "./components/UploadPanel";
import VideosScreen from "./components/VideosScreen";
import {
  loadPreferences,
  savePreferences,
  type Preferences,
} from "./preferences";
import { supabase } from "./supabase";
import Icon from "./ui/Icon";
import {
  DEFAULT_RECORDING_TYPE,
  type JobResponse,
  type JobSummary,
  type RecordingType,
  type Teaser,
  type VideoResponse,
  type VideoSummary,
} from "./types";

const POLL_INTERVAL_MS = 1500;
/** A long talk takes minutes to pull, so the fetch poll is slower than the job
 *  poll and gives up rather than hammering the API forever. */
const FETCH_POLL_INTERVAL_MS = 2500;
const FETCH_TIMEOUT_MS = 20 * 60 * 1000;

const STEP_COPY: Record<StepId, { title: string; blurb: string }> = {
  source: {
    title: "Source Video",
    blurb: "Upload the talk or webinar you want teasers from.",
  },
  options: {
    title: "Audience & Style",
    blurb: "Tell the model who these clips are for.",
  },
  processing: {
    title: "Processing",
    blurb: "Finding the strongest moments and cutting them.",
  },
  teasers: {
    title: "Teasers",
    blurb: "Ranked clips, each with the reason it was chosen.",
  },
};

const VIEW_COPY: Record<Exclude<View, "generate">, { title: string; blurb: string }> = {
  videos: {
    title: "Videos",
    blurb: "Sources already uploaded. Generate from one again without re-uploading.",
  },
  library: {
    title: "Library",
    blurb: "Every clip you have produced, across all runs.",
  },
  runs: {
    title: "Runs",
    blurb: "Each generation attempt, and how it turned out.",
  },
  dashboard: {
    title: "Dashboard",
    blurb: "Totals across every run on this account.",
  },
  settings: {
    title: "Settings",
    blurb: "Your account and what a new run starts with.",
  },
};

/** Auth gate. Everything below it can assume a signed-in user. */
export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // getSession() resolves from storage first so a reload does not flash the
    // login screen at an already-signed-in user.
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  if (!ready) {
    return (
      <div className="auth-shell">
        <p className="empty-note">Loading…</p>
      </div>
    );
  }

  if (!session) return <LoginScreen />;

  // Keyed on the user id so switching accounts remounts with clean state
  // rather than carrying the previous user's video and teasers over.
  return (
    <TeaserApp
      key={session.user.id}
      userId={session.user.id}
      email={session.user.email ?? null}
    />
  );
}

interface StepActionsProps {
  step: StepId;
  video: VideoResponse | null;
  job: JobResponse | null;
  teaserCount: number;
  busy: boolean;
  canGenerate: boolean;
  onContinue: () => void;
  onGenerate: () => void;
  onRetry: () => void;
  onViewTeasers: () => void;
  onStartOver: () => void;
  onCancel: () => void;
}

/** The primary action for wherever the run currently is.
 *
 *  Every step now answers "what do I do next?" in the same place. Processing
 *  in particular had nothing at all: a finished run left the reader on a
 *  completed progress bar with no way forward, and a failed one offered no way
 *  to try again — the only exit was the sidebar, which abandons the run.
 */
function StepActions({
  step,
  video,
  job,
  teaserCount,
  busy,
  canGenerate,
  onContinue,
  onGenerate,
  onRetry,
  onViewTeasers,
  onStartOver,
  onCancel,
}: StepActionsProps) {
  if (step === "source") {
    // Uploading is the action here; this only appears once it has produced
    // something, and moves the reader on rather than making them find the tab.
    return video ? (
      <button type="button" className="btn btn-primary btn-lg" onClick={onContinue}>
        Continue
        <Icon name="chevron-right" size={15} />
      </button>
    ) : null;
  }

  if (step === "options") {
    return (
      <button
        type="button"
        className="btn btn-primary btn-lg"
        onClick={onGenerate}
        disabled={!canGenerate}
        title={video === null ? "Add a source video first." : undefined}
      >
        <Icon name="sparkles" size={15} />
        {busy ? "Working" : "Generate Teasers"}
      </button>
    );
  }

  if (step === "processing") {
    if (job?.status === "failed" || job?.status === "cancelled") {
      return (
        <>
          <button
            type="button"
            className="btn btn-outline btn-lg"
            onClick={onStartOver}
          >
            <Icon name="rotate-ccw" size={15} />
            Start Over
          </button>
          <button type="button" className="btn btn-primary btn-lg" onClick={onRetry}>
            <Icon name="refresh-cw" size={15} />
            {job.status === "cancelled" ? "Run Again" : "Try Again"}
          </button>
        </>
      );
    }
    if (job?.status === "completed" && teaserCount > 0) {
      return (
        <button
          type="button"
          className="btn btn-primary btn-lg"
          onClick={onViewTeasers}
        >
          <Icon name="layout-grid" size={15} />
          View {teaserCount} Teaser{teaserCount === 1 ? "" : "s"}
        </button>
      );
    }
    // Still running. Cancel stops the run server-side rather than just walking
    // away from it: abandoning the page used to leave the worker analysing and
    // cutting clips for a run nobody was waiting for.
    return (
      <button
        type="button"
        className="btn btn-outline btn-lg"
        onClick={onCancel}
        disabled={busy && job === null}
      >
        <Icon name="x" size={15} />
        Cancel Run
      </button>
    );
  }

  return (
    <button type="button" className="btn btn-primary btn-lg" onClick={onStartOver}>
      <Icon name="plus" size={15} />
      New Teaser
    </button>
  );
}

interface TeaserAppProps {
  userId: string;
  email: string | null;
}

function TeaserApp({ userId, email }: TeaserAppProps) {
  const [view, setView] = useViewRoute();
  const [step, setStep] = useState<StepId>("source");

  const [counts, setCounts] = useState<NavCounts>({});

  const [video, setVideo] = useState<VideoResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState<string | null>(null);

  const [preferences, setPreferences] = useState<Preferences>(() =>
    loadPreferences(userId),
  );
  // The run's own choice, seeded from the default but not bound to it: changing
  // audience for one run must not silently rewrite the account's default.
  const [audience, setAudience] = useState(preferences.audience);
  const [style, setStyle] = useState(preferences.style);
  const [aspectRatio, setAspectRatio] = useState(preferences.aspectRatio);
  // Per-run only, deliberately not a saved preference: what kind of recording
  // this is describes the video on screen, not a standing choice. Someone who
  // uploads a webinar today and a demo tomorrow would have to correct a
  // remembered value both times.
  const [recordingType, setRecordingType] = useState<RecordingType>(
    DEFAULT_RECORDING_TYPE,
  );
  // Per-run only for the same reason: a steer like "focus on the pricing
  // discussion" is about one video, not about every future one.
  const [customPrompt, setCustomPrompt] = useState("");

  const [job, setJob] = useState<JobResponse | null>(null);
  const [teasers, setTeasers] = useState<Teaser[]>([]);
  const [failure, setFailure] = useState<Failure | null>(null);

  /** The run opened from Runs or Dashboard. Non-null means the detail page. */
  const [openRun, setOpenRun] = useState<JobSummary | null>(null);
  /** Narrows the Runs page to one video, set by the Videos page. */
  const [runsFilter, setRunsFilter] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);
  const fetchPollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const stopFetchPolling = useCallback(() => {
    if (fetchPollRef.current !== null) {
      window.clearInterval(fetchPollRef.current);
      fetchPollRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Both timers must die with the component; a poll that outlives it would
    // set state on something unmounted and keep hitting the API.
    return () => {
      stopPolling();
      stopFetchPolling();
    };
  }, [stopPolling, stopFetchPolling]);

  // ------------------------------------------------------------------
  const handleUpload = async (file: File) => {
    setFailure(null);
    setUploading(true);
    setUploadPercent(0);
    setJob(null);
    setTeasers([]);
    stopPolling();

    try {
      const uploaded = await uploadVideo(file, setUploadPercent);
      // Fetch the full record so probed media facts are shown.
      setVideo(await getVideo(uploaded.video_id));
      // Move the user on rather than leaving them on a screen whose work is done.
      setStep("options");
    } catch (error) {
      setVideo(null);
      setFailure(toFailure(error));
    } finally {
      setUploading(false);
    }
  };

  /** Hand a URL to the backend and watch the video until it is usable.
   *
   *  The download happens server-side and can take minutes, so this polls the
   *  video row rather than holding a request open. */
  const handleSubmitUrl = async (url: string) => {
    setFailure(null);
    setJob(null);
    setTeasers([]);
    stopPolling();
    stopFetchPolling();
    setFetching(true);
    setFetchStatus("Contacting the source…");

    let queued: VideoResponse;
    try {
      queued = await ingestFromUrl(url);
    } catch (error) {
      setFetching(false);
      setFetchStatus(null);
      setFailure(toFailure(error));
      return;
    }

    setFetchStatus("Downloading the video…");
    const startedAt = Date.now();

    fetchPollRef.current = window.setInterval(async () => {
      try {
        const current = await getVideo(queued.video_id);

        if (current.status === "ready") {
          stopFetchPolling();
          setFetching(false);
          setFetchStatus(null);
          setVideo(current);
          setStep("options");
        } else if (current.status === "failed") {
          stopFetchPolling();
          setFetching(false);
          setFetchStatus(null);
          setFailure({
            code: "SOURCE_FETCH_FAILED",
            message:
              current.error_message ??
              "The video could not be fetched from that link.",
          });
        } else if (Date.now() - startedAt > FETCH_TIMEOUT_MS) {
          // The fetch may well still be running server-side; this only stops
          // this tab from polling, and says so rather than claiming failure.
          stopFetchPolling();
          setFetching(false);
          setFetchStatus(null);
          setFailure({
            code: "SOURCE_FETCH_TIMEOUT",
            message:
              "This is taking unusually long. The download may still finish — " +
              "check the Videos page in a few minutes.",
          });
        }
      } catch (error) {
        stopFetchPolling();
        setFetching(false);
        setFetchStatus(null);
        setFailure(toFailure(error));
      }
    }, FETCH_POLL_INTERVAL_MS);
  };

  const handleGenerate = async () => {
    if (!video) return;
    setFailure(null);
    setTeasers([]);
    stopPolling();

    try {
      const started = await startGeneration(video.video_id, audience, style, {
        teaser_count: preferences.teaserCount,
        clip_max_seconds: preferences.clipMaxSeconds,
        aspect_ratio: aspectRatio,
        recording_type: recordingType,
        custom_prompt: customPrompt.trim() || undefined,
      });
      const initial = await getJob(started.job_id);
      setJob(initial);
      setStep("processing");

      pollRef.current = window.setInterval(async () => {
        try {
          const current = await getJob(started.job_id);
          setJob(current);

          if (current.status === "completed") {
            stopPolling();
            const result = await getTeasers(current.video_id, current.job_id);
            setTeasers(result.teasers);
            if (result.teasers.length > 0) setStep("teasers");
          } else if (current.status === "cancelled") {
            // Stopped on purpose, so it is not surfaced as a failure.
            stopPolling();
          } else if (current.status === "failed") {
            stopPolling();
            setFailure({
              code: current.error_code ?? "GENERATION_FAILED",
              message:
                current.error_message ?? "Teaser generation failed. Check the API logs.",
            });
          }
        } catch (error) {
          stopPolling();
          setFailure(toFailure(error));
        }
      }, POLL_INTERVAL_MS);
    } catch (error) {
      setFailure(toFailure(error));
    }
  };

  /** Stop the run on the server, not just in this tab.
   *
   *  Polling stops on the response rather than waiting for the next tick, so the
   *  panel settles immediately instead of showing one more stage first. */
  const handleCancelRun = async () => {
    if (!job) return;
    setFailure(null);
    try {
      const stopped = await cancelJob(job.job_id);
      stopPolling();
      setJob(stopped);
    } catch (error) {
      // A run that finished between the last poll and the click is a 409. That
      // is not worth an error banner -- refresh and let the panel show the
      // outcome it actually reached.
      const failed = toFailure(error);
      if (failed.code === "JOB_NOT_CANCELLABLE") {
        try {
          setJob(await getJob(job.job_id));
        } catch {
          /* the next poll will catch up */
        }
        return;
      }
      setFailure(failed);
    }
  };

  const handleReset = () => {
    stopPolling();
    stopFetchPolling();
    setVideo(null);
    setUploadPercent(0);
    setFetching(false);
    setFetchStatus(null);
    setJob(null);
    setTeasers([]);
    setFailure(null);
    setCustomPrompt("");
    setStep("source");
  };

  const handleSignOut = () => {
    stopPolling();
    stopFetchPolling();
    void supabase.auth.signOut();
  };

  const handlePreferencesChange = (next: Preferences) => {
    setPreferences(next);
    savePreferences(userId, next);
  };

  /** Adopt an already-uploaded video as the source and go straight to options.
   *  The whole point of the Videos page: no second upload of the same file. */
  const handleGenerateFromExisting = (chosen: VideoSummary) => {
    stopPolling();
    setJob(null);
    setTeasers([]);
    setFailure(null);
    setVideo(chosen);
    // A fresh run starts from the saved defaults, not from whatever the last
    // run in this tab happened to use.
    setAudience(preferences.audience);
    setStyle(preferences.style);
    setAspectRatio(preferences.aspectRatio);
    setRecordingType(DEFAULT_RECORDING_TYPE);
    setCustomPrompt("");
    setStep("options");
    setView("generate");
  };

  const handleOpenRun = (run: JobSummary) => {
    setOpenRun(run);
    setView("runs");
  };

  /** Re-run a past job's exact settings against the same source.
   *
   *  Queued through the ordinary generate endpoint rather than a dedicated
   *  retry one: a retry *is* a new run, and giving it its own row keeps the
   *  history of what was attempted intact. */
  const handleRetryRun = async (run: JobSummary) => {
    setFailure(null);
    try {
      await startGeneration(run.video_id, run.audience, run.style, {
        teaser_count: preferences.teaserCount,
        clip_max_seconds: preferences.clipMaxSeconds,
        // The original run's shape and direction, so a retry reproduces the run
        // it is retrying rather than a differently-steered one.
        aspect_ratio: (run.aspect_ratio as typeof aspectRatio) ?? aspectRatio,
        recording_type: (run.recording_type as RecordingType) ?? undefined,
        custom_prompt: run.custom_prompt ?? undefined,
      });
    } catch (error) {
      setFailure(toFailure(error));
      throw error;
    }
  };

  // Leaving Runs closes the detail page, so coming back lands on the list
  // rather than on a run the reader has since stopped caring about. Keyed on
  // the view rather than done in the click handler because Back and Forward
  // change the view too, and those never pass through a handler of ours.
  useEffect(() => {
    if (view !== "runs") setOpenRun(null);
  }, [view]);

  // ------------------------------------------------------------------
  const jobFinished =
    job !== null &&
    (job.status === "completed" ||
      job.status === "failed" ||
      job.status === "cancelled");

  const busy = uploading || fetching || (job !== null && !jobFinished);
  const canGenerate = video !== null && !busy;

  /** The badge numbers on the sidebar rows.
   *
   *  There is no aggregate endpoint, so this is the three list calls the
   *  Videos, Library and Runs screens each make on their own. Refetched
   *  whenever this tab does something that moves those totals — a new source,
   *  a new run, or a run reaching its end — rather than on every view change. */
  useEffect(() => {
    let live = true;
    Promise.all([listVideos(), listTeasers(), listJobs()])
      .then(([videos, library, runs]) => {
        if (!live) return;
        setCounts({
          videos: videos.videos.length,
          library: library.teasers.length,
          runs: runs.jobs.length,
        });
      })
      .catch(() => {
        // Counts decorate the nav. Failing to load them is not worth an error
        // banner over the work the reader is actually doing.
      });
    return () => {
      live = false;
    };
  }, [video?.video_id, job?.job_id, jobFinished]);

  const steps: Step[] = [
    {
      id: "source",
      label: "Source Video",
      icon: "upload",
      enabled: true,
      complete: video !== null,
    },
    {
      // Not gated on the upload: audience and style are a preference form that
      // does not depend on the video, so there is no reason to lock it. Only
      // the Generate action itself needs a source.
      id: "options",
      label: "Audience",
      icon: "users",
      enabled: true,
      complete: job !== null,
    },
    {
      id: "processing",
      label: "Processing",
      icon: "layers",
      enabled: job !== null,
      complete: jobFinished,
      blockedReason: "Start a generation run to see progress.",
    },
    {
      id: "teasers",
      label: "Teasers",
      icon: "layout-grid",
      count: teasers.length || undefined,
      enabled: teasers.length > 0,
      complete: teasers.length > 0,
      blockedReason: "No teasers yet — finish a run first.",
    },
  ];

  const copy =
    view === "generate"
      ? STEP_COPY[step]
      : view === "runs" && openRun
        ? { title: "Run Detail", blurb: "One run, and every clip it produced." }
        : VIEW_COPY[view];

  return (
    <AppShell
      view={view}
      onViewChange={setView}
      counts={counts}
      video={video}
      onReset={handleReset}
      canReset={!busy && (video !== null || job !== null || failure !== null)}
      email={email}
      onSignOut={handleSignOut}
    >
      <div className="pagehead">
        <div className="pagehead-text">
          <h1>{copy.title}</h1>
          <p>{copy.blurb}</p>
        </div>
        <div className="pagehead-actions">
          {view === "generate" ? (
            <StepActions
              step={step}
              video={video}
              job={job}
              teaserCount={teasers.length}
              busy={busy}
              canGenerate={canGenerate}
              onContinue={() => setStep("options")}
              onGenerate={handleGenerate}
              onRetry={handleGenerate}
              onViewTeasers={() => setStep("teasers")}
              onStartOver={handleReset}
              onCancel={handleCancelRun}
            />
          ) : view !== "settings" ? (
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={() => {
                handleReset();
                setView("generate");
              }}
            >
              <Icon name="sparkles" size={15} />
              New Teaser
            </button>
          ) : null}
        </div>
      </div>

      {failure && (
        <div className="alert" role="alert">
          <span className="icon-tile icon-tile-danger">
            <Icon name="x" size={15} strokeWidth={2.2} />
          </span>
          <div className="alert-text">
            <div className="alert-message">{failure.message}</div>
            <span className="alert-code">{failure.code}</span>
          </div>
          <button
            type="button"
            className="icon-btn icon-btn-ghost"
            aria-label="Dismiss"
            onClick={() => setFailure(null)}
          >
            <Icon name="x" size={16} />
          </button>
        </div>
      )}

      {view === "videos" && (
        <VideosScreen
          onGenerate={handleGenerateFromExisting}
          onOpenRuns={(videoId) => {
            setRunsFilter(videoId);
            setOpenRun(null);
            setView("runs");
          }}
          onUpload={() => {
            handleReset();
            setView("generate");
          }}
        />
      )}

      {view === "library" && <LibraryScreen />}

      {view === "runs" &&
        (openRun ? (
          <RunDetailScreen job={openRun} onBack={() => setOpenRun(null)} />
        ) : (
          <RunsScreen
            videoId={runsFilter}
            onClearFilter={() => setRunsFilter(null)}
            onOpenRun={handleOpenRun}
            onRetry={handleRetryRun}
          />
        ))}

      {view === "dashboard" && <DashboardScreen onOpenRun={handleOpenRun} />}

      {view === "settings" && (
        <SettingsScreen
          email={email}
          preferences={preferences}
          onPreferencesChange={handlePreferencesChange}
          onSignOut={handleSignOut}
        />
      )}

      {view === "generate" && (
        <>
          <Stepper steps={steps} current={step} onSelect={setStep} />

          {/* One screen per step. Announced politely so a screen reader user
              hears the view change instead of silently losing their place. */}
          <div className="step-panel" role="region" aria-live="polite">
            {step === "source" && (
              <UploadPanel
                video={video}
                uploading={uploading}
                uploadPercent={uploadPercent}
                fetching={fetching}
                fetchStatus={fetchStatus}
                onSelect={handleUpload}
                onSubmitUrl={handleSubmitUrl}
                disabled={busy && !fetching}
              />
            )}

            {step === "options" && (
              <OptionsPanel
                audience={audience}
                style={style}
                aspectRatio={aspectRatio}
                recordingType={recordingType}
                customPrompt={customPrompt}
                onAudienceChange={setAudience}
                onStyleChange={setStyle}
                onAspectRatioChange={setAspectRatio}
                onRecordingTypeChange={setRecordingType}
                onCustomPromptChange={setCustomPrompt}
                disabled={busy}
              />
            )}

            {step === "processing" && job && <ProgressPanel job={job} />}

            {step === "teasers" && job && (
              <NarrativePanel
                summary={job.summary}
                chapters={job.chapters}
                keywords={job.keywords}
              />
            )}

            {/* Above the clip grid: it is the run's single assembled output,
                and the grid is the raw material it was built from. */}
            {step === "teasers" && job && <PreviewCard job={job} />}

            {step === "teasers" && teasers.length > 0 && (
              <section className="card" id="teasers">
                <div className="card-header">
                  <span className="icon-tile">
                    <Icon name="layout-grid" size={15} strokeWidth={2.2} />
                  </span>
                  <h2>Teasers</h2>
                  <div className="card-header-actions">
                    <span className="badge badge-brand">
                      {audience.replace("_", " ")} · {style}
                    </span>
                    <span className="badge o-num">{aspectRatio}</span>
                    <span className="badge o-num">{teasers.length}</span>
                  </div>
                </div>
                <div className="teaser-grid">
                  {teasers.map((teaser) => (
                    <TeaserCard key={teaser.id} teaser={teaser} />
                  ))}
                </div>
              </section>
            )}

            {step === "teasers" && teasers.length === 0 && (
              <section className="card">
                <p className="empty-note">
                  The job completed but no teasers were returned.
                </p>
              </section>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}
