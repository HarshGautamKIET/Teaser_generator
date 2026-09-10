import { useEffect, useState } from "react";

import { fetchTeaserMedia } from "./api";

/** Loads ownership-checked media and yields a blob URL to play it from.
 *
 *  Generated media sits behind an access-token check, and a <video src> cannot
 *  carry an Authorization header — so the bytes are fetched with the token and
 *  handed to the element as a blob. The URL is revoked on unmount; without that
 *  every re-render of a list leaks a copy of the video.
 *
 *  Shared by teaser clips and the run's assembled preview. They are different
 *  artifacts served by different routes, but the loading problem is the same
 *  one, and the leak this avoids is easy to reintroduce by writing it twice.
 */
export function useAuthedMedia(path: string): {
  url: string | null;
  failed: boolean;
} {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setUrl(null);
    setFailed(false);

    // An empty path means there is nothing to load. Handled here rather than by
    // the caller skipping the hook, because a conditional hook is not allowed —
    // and fetching "" would request the API root and report it as a failure.
    if (!path) return;

    fetchTeaserMedia(path)
      .then((created) => {
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setUrl(created);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return { url, failed };
}
