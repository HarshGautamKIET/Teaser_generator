/** Supabase browser client.
 *
 *  Only the publishable key belongs here. It identifies the project, not the
 *  caller -- every request is authorised by the user's access token, and the
 *  backend enforces row level security on top. The secret key is server-side
 *  only and must never reach this bundle.
 */

import { createClient } from "@supabase/supabase-js";

const url: string = import.meta.env.VITE_SUPABASE_URL ?? "http://localhost:8000";
const publishableKey: string = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? "";

if (!publishableKey) {
  // A blank key fails later with an opaque 401 from the Auth service; say so here.
  console.error(
    "VITE_SUPABASE_PUBLISHABLE_KEY is not set. Copy it from `sh run.sh secrets` " +
      "in docker/supabase and put it in the repository-root .env.",
  );
}

export const supabase = createClient(url, publishableKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
  },
});

/** The current access token, refreshed if it is close to expiry.
 *
 *  Read per request rather than cached: tokens are short-lived (JWT_EXPIRY,
 *  one hour by default) and supabase-js rotates them in the background, so a
 *  captured copy goes stale mid-session. */
export async function accessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
