import type { ReactNode } from "react";

import { formatDuration } from "../format";
import type { VideoResponse } from "../types";
import Icon, { type IconName } from "../ui/Icon";

export type View =
  | "generate"
  | "videos"
  | "library"
  | "runs"
  | "dashboard"
  | "settings";

interface NavEntry {
  id: View;
  label: string;
  icon: IconName;
  hint: string;
}

/** The sidebar lists destinations, and nothing else.
 *
 *  It once carried a second "Workflow" group whose entries only scrolled the
 *  current page, so "Generate" and "Source Video" appeared to be two places and
 *  were one. Progress through the flow is a stepper on the page itself.
 *
 *  Grouped by what the reader came to do rather than alphabetically: making a
 *  thing, looking at things already made, then checking how it went. */
const NAV_GROUPS: { label: string; entries: NavEntry[] }[] = [
  {
    label: "Create",
    entries: [
      {
        id: "generate",
        label: "Generate",
        icon: "sparkles",
        hint: "Turn a video into teasers",
      },
    ],
  },
  {
    label: "Content",
    entries: [
      {
        id: "videos",
        label: "Videos",
        icon: "video",
        hint: "Sources you have uploaded",
      },
      {
        id: "library",
        label: "Library",
        icon: "layout-grid",
        hint: "Every clip you have produced",
      },
    ],
  },
  {
    label: "Activity",
    entries: [
      {
        id: "runs",
        label: "Runs",
        icon: "history",
        hint: "Past generation runs",
      },
      {
        id: "dashboard",
        label: "Dashboard",
        icon: "chart-pie",
        hint: "Totals across every run",
      },
    ],
  },
];

interface Props {
  view: View;
  onViewChange: (view: View) => void;
  video: VideoResponse | null;
  onReset: () => void;
  canReset: boolean;
  email: string | null;
  onSignOut: () => void;
  children: ReactNode;
}

export default function AppShell({
  view,
  onViewChange,
  video,
  onReset,
  canReset,
  email,
  onSignOut,
  children,
}: Props) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-lockup">
            <span className="brand-mark">
              <Icon name="clapperboard" size={16} />
            </span>
            <span className="brand-name">Teaser</span>
          </div>
        </div>

        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-label">{group.label}</div>
            <nav className="nav">
              {group.entries.map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  title={entry.hint}
                  aria-current={entry.id === view ? "page" : undefined}
                  className={`nav-item${entry.id === view ? " nav-item-active" : ""}`}
                  onClick={() => onViewChange(entry.id)}
                >
                  <Icon name={entry.icon} size={17} />
                  <span className="nav-item-text">{entry.label}</span>
                </button>
              ))}
            </nav>
          </div>
        ))}

        {/* Pushed to the bottom: settings is somewhere you go rarely and
            deliberately, not a peer of the day's work. */}
        <div className="nav-group nav-group-end">
          <nav className="nav">
            <button
              type="button"
              title="Account and generation defaults"
              aria-current={view === "settings" ? "page" : undefined}
              className={`nav-item${view === "settings" ? " nav-item-active" : ""}`}
              onClick={() => onViewChange("settings")}
            >
              <Icon name="settings" size={17} />
              <span className="nav-item-text">Settings</span>
            </button>
          </nav>
        </div>

        {/* The one saturated block in the product, pinned last. */}
        <div className="promo">
          <div className="promo-title">Gemini + FFmpeg</div>
          <p className="promo-body">
            Gemini finds the moments. FFmpeg cuts the clips.
          </p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          {video ? (
            <span className="source-chip">
              <Icon name="film" size={13} />
              <span className="source-chip-name">{video.filename}</span>
              <span className="source-chip-meta o-num">
                {formatDuration(video.duration_seconds)}
              </span>
            </span>
          ) : (
            <span className="source-chip source-chip-empty">
              <Icon name="film" size={13} />
              No source video
            </span>
          )}

          <div className="topbar-right">
            {email && (
              <button
                type="button"
                className="account-email account-email-btn"
                title="Account settings"
                onClick={() => onViewChange("settings")}
              >
                {email}
              </button>
            )}
            <button
              type="button"
              className="icon-btn"
              aria-label="Start over"
              title="Start over"
              disabled={!canReset}
              onClick={onReset}
            >
              <Icon name="rotate-ccw" size={16} />
            </button>
            <button
              type="button"
              className="icon-btn"
              aria-label="Sign out"
              title="Sign out"
              onClick={onSignOut}
            >
              <Icon name="log-out" size={16} />
            </button>
          </div>
        </header>

        <div className="content">{children}</div>
      </main>
    </div>
  );
}
