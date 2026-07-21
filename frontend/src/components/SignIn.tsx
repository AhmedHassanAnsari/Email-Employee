// src/components/SignIn.tsx
import React from "react";
import { oauthStartUrl } from "../api/client";

const SignIn: React.FC = () => {
  const handleSignIn = () => {
    // Same-tab redirect through our backend consent flow. On success the
    // backend callback redirects back to "/?auth=success&email=...", which
    // OAuthCallback consumes to persist auth and land on the dashboard.
    window.location.href = oauthStartUrl();
  };

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <button className="btn-primary glass" onClick={handleSignIn}>
        Sign in with Google
      </button>
    </div>
  );
};

export default SignIn;
