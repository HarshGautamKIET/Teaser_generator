/** Loading one thing from the API, and saying honestly how it went.
 *
 *  Every listing page has the same three states and the same obligation to show
 *  which one it is in. Without something shared they drift: one page shows a
 *  spinner forever on a 401, another renders an empty list and implies the
 *  account has no work in it. `data === null` here means "not loaded yet", never
 *  "loaded and empty" — an empty list is a real value.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "./types";

export interface Failure {
  code: string;
  message: string;
}

export function toFailure(error: unknown): Failure {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message };
  }
  return {
    code: "UNEXPECTED_ERROR",
    message: error instanceof Error ? error.message : "Something went wrong.",
  };
}

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Failure | null;
  reload: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Failure | null>(null);
  const [nonce, setNonce] = useState(0);

  // `load` is a fresh closure on every render, so depending on it directly would
  // refetch forever. The caller states what the request actually varies with.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    run()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        // The stale value is dropped: showing last week's list beside a failure
        // message invites the reader to trust it.
        setData(null);
        setError(toFailure(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [run, nonce]);

  return { data, loading, error, reload: () => setNonce((n) => n + 1) };
}
