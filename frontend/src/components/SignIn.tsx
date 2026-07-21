// src/components/SignIn.tsx
import React from "react";
import { oauthStartUrl } from "../api/client";

const GoogleIcon: React.FC = () => (
  <svg className="h-5 w-5" viewBox="0 0 48 48" aria-hidden="true">
    <path
      fill="#EA4335"
      d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
    />
    <path
      fill="#4285F4"
      d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
    />
    <path
      fill="#FBBC05"
      d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
    />
    <path
      fill="#34A853"
      d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
    />
  </svg>
);

const SignIn: React.FC = () => {
  const handleSignIn = () => {
    // Same-tab redirect through our backend consent flow. On success the
    // backend callback redirects back to "/?auth=success&email=...", which
    // OAuthCallback consumes to persist auth and land on the dashboard.
    window.location.href = oauthStartUrl();
  };

  return (
    <div className="relative flex h-screen items-center justify-center overflow-hidden bg-background">
      {/* Ambient gradient glow */}
      <div className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-primary/30 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-accent/20 blur-3xl" />

      <div className="glass relative z-10 flex w-[22rem] flex-col items-center gap-6 px-8 py-10 transition-transform duration-300 hover:-translate-y-1 hover:shadow-2xl">
        {/* Logo */}
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent shadow-lg transition-transform duration-300 hover:scale-105">
          <svg
            className="h-9 w-9 text-white"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="2" y="4" width="20" height="16" rx="2.5" />
            <path d="m3 6 9 7 9-7" />
          </svg>
        </div>

        <div className="text-center">
          <h1 className="text-xl font-semibold text-white">AI Email Employee</h1>
          <p className="mt-1 text-sm text-white/60">
            Sign in to manage your inbox
          </p>
        </div>

        <button
          onClick={handleSignIn}
          className="group flex w-full items-center justify-center gap-3 rounded-lg bg-white px-4 py-2.5 font-medium text-gray-700 shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:bg-cyan-400 hover:text-white hover:shadow-lg hover:shadow-cyan-400/40 active:translate-y-0"
        >
          <GoogleIcon />
          <span>Continue with Google</span>
        </button>

        <p className="text-center text-xs text-white/40">
          Secure OAuth &middot; We never store your password
        </p>
      </div>
    </div>
  );
};

export default SignIn;
