import { useCallback, useEffect, useState, type ReactNode } from "react";

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

/** How many things sit behind a destination, for the badge on its row.
 *  Views with nothing countable simply have no entry. */
export type NavCounts = Partial<Record<View, number>>;

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

/** Kept out of the groups above: settings is somewhere you go rarely and
 *  deliberately, not a peer of the day's work. It renders alone, on the floor. */
const SETTINGS_ENTRY: NavEntry = {
  id: "settings",
  label: "Settings",
  icon: "settings",
  hint: "Account and generation defaults",
};

const ALL_ENTRIES: NavEntry[] = [
  ...NAV_GROUPS.flatMap((group) => group.entries),
  SETTINGS_ENTRY,
];

const VIEWS: string[] = ALL_ENTRIES.map((entry) => entry.id);

const hintId = (view: View) => `nav-hint-${view}`;

function viewFromHash(): View {
  const slug = window.location.hash.replace(/^#\/?/, "");
  return VIEWS.includes(slug) ? (slug as View) : "generate";
}

/** The current view, mirrored in the address bar.
 *
 *  The view used to be plain component state, so a reload dropped the reader
 *  back on Generate, Back did nothing, and no page could be linked to.
 *
 *  Hash rather than the History API on purpose: reloading `#/library` needs no
 *  SPA-fallback rule from whatever serves the build. `hashchange` fires for Back
 *  and Forward as well as for our own writes, so one listener covers both and
 *  the hash stays the single source of truth. */
export function useViewRoute(): [View, (next: View) => void] {
  const [view, setView] = useState<View>(viewFromHash);

  useEffect(() => {
    const sync = () => {
      const next = viewFromHash();
      setView(next);
      // An empty or unrecognised hash would leave the address bar disagreeing
      // with the screen. Rewriting rather than pushing keeps a typo out of the
      // history, so Back still goes where the reader expects.
      const canonical = `#/${next}`;
      if (window.location.hash !== canonical) {
        window.history.replaceState(null, "", canonical);
      }
    };

    window.addEventListener("hashchange", sync);
    sync();
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  // Writing the hash fires `hashchange`, which is what actually sets the state.
  const navigate = useCallback((next: View) => {
    window.location.hash = `#/${next}`;
  }, []);

  return [view, navigate];
}

interface NavItemProps {
  entry: NavEntry;
  view: View;
  count?: number;
  onViewChange: (view: View) => void;
}

function NavItem({ entry, view, count, onViewChange }: NavItemProps) {
  const active = entry.id === view;
  return (
    <button
      type="button"
      title={entry.hint}
      aria-current={active ? "page" : undefined}
      aria-describedby={hintId(entry.id)}
      className={`nav-item${active ? " nav-item-active" : ""}`}
      onClick={() => onViewChange(entry.id)}
    >
      <Icon name={entry.icon} size={17} />
      <span className="nav-item-text">{entry.label}</span>
      {/* Zero is left off rather than shown. A badge reading "0" is noise on
          every row of a new account, and the page itself says it is empty. */}
      {count != null && count > 0 && (
        <span className="nav-count o-num">{count}</span>
      )}
    </button>
  );
}

interface Props {
  view: View;
  onViewChange: (view: View) => void;
  counts: NavCounts;
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
  counts,
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

        {/* One landmark for the whole rail. Three separate <nav>s used to be
            announced as three unnamed "navigation" regions. */}
        <nav className="nav-rail" aria-label="Main">
          {NAV_GROUPS.map((group) => (
            <div
              className="nav-group"
              key={group.label}
              role="group"
              aria-labelledby={`nav-group-${group.label}`}
            >
              <div className="nav-label" id={`nav-group-${group.label}`}>
                {group.label}
              </div>
              <div className="nav">
                {group.entries.map((entry) => (
                  <NavItem
                    key={entry.id}
                    entry={entry}
                    view={view}
                    count={counts[entry.id]}
                    onViewChange={onViewChange}
                  />
                ))}
              </div>
            </div>
          ))}

          <div className="nav-group nav-group-end">
            <div className="nav">
              <NavItem
                entry={SETTINGS_ENTRY}
                view={view}
                onViewChange={onViewChange}
              />
            </div>
          </div>
        </nav>

        {/* Outside the rows on purpose. A hint nested inside its button would
            join that button's accessible name ("Videos 3 Sources you have
            uploaded"); described from out here it stays a description, and
            reaches keyboard and touch users that `title` alone never did. */}
        <div className="sr-only">
          {ALL_ENTRIES.map((entry) => (
            <span key={entry.id} id={hintId(entry.id)}>
              {entry.hint}
            </span>
          ))}
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
