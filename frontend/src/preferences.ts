/** Generation defaults, remembered per user in this browser.
 *
 *  Deliberately not server state: these only decide which radio button starts
 *  selected, and a preference that needs a migration and an endpoint to change
 *  the initial value of a form is not worth either. Namespaced by user id
 *  because two accounts can share a browser.
 */

import { DEFAULT_ASPECT_RATIO, type AspectRatio, type Audience, type Style } from "./types";

export interface Preferences {
  audience: Audience;
  style: Style;
  aspectRatio: AspectRatio;
  /** Clips per run, and the longest a clip may be. */
  teaserCount: number;
  clipMaxSeconds: number;
}

/** Bounds mirror the API's own validation (backend/app/schemas.py) so a value
 *  stored here can never be one the server will reject. */
export const TEASER_COUNT_RANGE = { min: 1, max: 10 } as const;
export const CLIP_SECONDS_RANGE = { min: 5, max: 180 } as const;

export const DEFAULT_PREFERENCES: Preferences = {
  audience: "developers",
  style: "promotional",
  aspectRatio: DEFAULT_ASPECT_RATIO,
  teaserCount: 3,
  clipMaxSeconds: 60,
};

const VALID_AUDIENCES: Audience[] = [
  "general",
  "developers",
  "business_leaders",
  "students",
];
const VALID_STYLES: Style[] = ["informative", "promotional", "emotional"];
const VALID_RATIOS: AspectRatio[] = ["16:9", "9:16", "1:1", "4:3", "4:5"];

function storageKey(userId: string): string {
  return `teaser-generator/preferences/v1/${userId}`;
}

export function loadPreferences(userId: string): Preferences {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(storageKey(userId));
  } catch {
    return DEFAULT_PREFERENCES;
  }
  if (!raw) return DEFAULT_PREFERENCES;

  try {
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return {
      // Each field is checked separately so a stored value from an older build
      // falls back on its own rather than discarding the other one with it.
      audience: VALID_AUDIENCES.includes(parsed.audience as Audience)
        ? (parsed.audience as Audience)
        : DEFAULT_PREFERENCES.audience,
      style: VALID_STYLES.includes(parsed.style as Style)
        ? (parsed.style as Style)
        : DEFAULT_PREFERENCES.style,
      aspectRatio: VALID_RATIOS.includes(parsed.aspectRatio as AspectRatio)
        ? (parsed.aspectRatio as AspectRatio)
        : DEFAULT_PREFERENCES.aspectRatio,
      teaserCount: clamp(
        parsed.teaserCount,
        TEASER_COUNT_RANGE,
        DEFAULT_PREFERENCES.teaserCount,
      ),
      clipMaxSeconds: clamp(
        parsed.clipMaxSeconds,
        CLIP_SECONDS_RANGE,
        DEFAULT_PREFERENCES.clipMaxSeconds,
      ),
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

/** Storage is user-writable, so a stored number is not trusted to be in range
 *  or to be a number at all. */
function clamp(
  value: unknown,
  range: { min: number; max: number },
  fallback: number,
): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(range.max, Math.max(range.min, Math.round(value)));
}

export function savePreferences(userId: string, preferences: Preferences): void {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(preferences));
  } catch {
    /* Storage disabled or full. Defaults are a convenience, so a failed write
       must not break the settings screen or generation. */
  }
}
