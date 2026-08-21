import { useState, type FormEvent } from "react";

import productShot from "../assets/product-dashboard.png";
import { supabase } from "../supabase";
import Icon from "../ui/Icon";

type Mode = "signin" | "signup";

const PIPELINE = ["Gemini", "FFmpeg", "FastAPI", "Supabase", "React"];

export default function LoginScreen() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);

    try {
      if (mode === "signup") {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
        });
        if (signUpError) throw signUpError;

        // With email confirmation switched on, signUp returns a user but no
        // session -- say so rather than leaving the form looking inert.
        if (!data.session) {
          setNotice("Check your email to confirm the account, then sign in.");
          setMode("signin");
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (signInError) throw signInError;
      }
      // A successful sign-in fires onAuthStateChange; App swaps this screen out.
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  /** Requires SMTP on the Auth service. The self-hosted stack ships without a
   *  mail sender, so this reports whatever Auth says rather than pretending a
   *  message went out. */
  const requestReset = async () => {
    if (!email) {
      setError("Enter your email address first, then request a reset.");
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email);
      if (resetError) throw resetError;
      // Deliberately not "we sent you an email": confirming which addresses are
      // registered turns this into an account-enumeration oracle.
      setNotice("If that address has an account, a reset link is on its way.");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not send a reset email.",
      );
    } finally {
      setBusy(false);
    }
  };

  const isSignIn = mode === "signin";

  return (
    <div className="auth-shell">
      <div className="auth-split">
        {/* ---------------- Form ---------------- */}
        <div className="auth-pane auth-pane-form">
          <div className="brand-lockup auth-logo">
            <span className="brand-mark">
              <Icon name="clapperboard" size={16} />
            </span>
            <span className="brand-name">Teaser</span>
          </div>

          <div className="auth-form-block">
            <h1 className="auth-title">{isSignIn ? "Log in" : "Sign up"}</h1>
            <p className="auth-subtitle">
              {isSignIn
                ? "Welcome back! Please enter your email."
                : "Create an account to start generating teasers."}
            </p>

            <form className="auth-form" onSubmit={submit}>
              <label className="field">
                <span className="field-label">Email</span>
                <span className="input-wrap">
                  <input
                    className="input"
                    type="email"
                    placeholder="Your Email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    autoComplete="email"
                    required
                    disabled={busy}
                  />
                  <Icon name="mail" size={15} />
                </span>
              </label>

              <label className="field">
                <span className="field-label">Password</span>
                <span className="input-wrap">
                  <input
                    className="input"
                    type={showPassword ? "text" : "password"}
                    placeholder="Password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete={isSignIn ? "current-password" : "new-password"}
                    minLength={8}
                    required
                    disabled={busy}
                  />
                  <button
                    type="button"
                    className="input-affix-btn"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((shown) => !shown)}
                  >
                    <Icon name={showPassword ? "eye-off" : "eye"} size={15} />
                  </button>
                </span>
                {isSignIn ? (
                  <span className="field-row">
                    <button
                      type="button"
                      className="link-btn link-btn-quiet"
                      disabled={busy}
                      onClick={requestReset}
                    >
                      forgot password?
                    </button>
                  </span>
                ) : (
                  <span className="field-hint">At least 8 characters.</span>
                )}
              </label>

              {error && (
                <div className="alert" role="alert">
                  <span className="icon-tile icon-tile-danger">
                    <Icon name="x" size={15} strokeWidth={2.2} />
                  </span>
                  <div className="alert-text">
                    <div className="alert-message">{error}</div>
                  </div>
                </div>
              )}

              {notice && (
                <p className="empty-note" role="status">
                  {notice}
                </p>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-lg btn-full auth-submit"
                disabled={busy}
              >
                {busy ? "Working…" : isSignIn ? "LOGIN" : "CREATE ACCOUNT"}
              </button>
            </form>

            <p className="auth-switch">
              {isSignIn ? "Don't have an account?" : "Already have an account?"}{" "}
              <button
                type="button"
                className="link-btn"
                disabled={busy}
                onClick={() => {
                  setMode(isSignIn ? "signup" : "signin");
                  setError(null);
                  setNotice(null);
                }}
              >
                {isSignIn ? "Sign up" : "Log in"}
              </button>
            </p>
          </div>

          <p className="auth-footnote">© Teaser Generator 2026</p>
        </div>

        {/* ---------------- Marketing ---------------- */}
        <aside className="auth-pane auth-pane-brand" aria-hidden="true">
          <div className="auth-pitch">
            <h2 className="auth-pitch-title">
              The simplest way to cut teasers from long video
            </h2>
            <p className="auth-pitch-body">
              Upload a talk, pick an audience, get ranked vertical clips.
            </p>
          </div>

          {/* A real capture of the dashboard, not a mockup. Re-shoot it by
              signing in, completing a run, and screenshotting /dashboard at
              1440x900; crop to 1440x760 to drop the empty area below the table. */}
          <img
            className="auth-preview"
            src={productShot}
            width={1440}
            height={760}
            alt=""
            loading="eager"
            decoding="async"
          />

          <ul className="auth-stack">
            {PIPELINE.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
