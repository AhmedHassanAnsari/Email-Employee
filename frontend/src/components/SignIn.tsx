// src/components/SignIn.tsx
import React from "react";
import { useAuth } from "../context/AuthContext";

const GOOGLE_OAUTH_URL = "https://accounts.google.com/v3/signin/accountchooser?access_type=offline&client_id=115700428800-s6ngmi8555fnq8rrceqa7311dtou8m4l.apps.googleusercontent.com&include_granted_scopes=true&prompt=consent&redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Foauth%2Fgoogle%2Fcallback&response_type=code&scope=openid+email+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.modify&dsh=S1980012211%3A1784484987267360&o2v=2&service=lso&flowName=GeneralOAuthFlow&opparams=%253F&continue=https%3A%2F%2Faccounts.google.com%2Fsignin%2Foauth%2Fconsent%3Fauthuser%3Dunknown%26part%3DAJi8hAPflpENHJiemuBIrYIZIsqqBajsv0CZFzrpmr_vN-IFITR3hMXAjkIR_ZT4HBmG-AfPzId3hqx48GzfS1NVaPg1i-VxT4255LRJM5vbDPLRWvdN2qbFaiWrEQKV9Bn-Kcbvp8tETNSeKcD6Ti0rILyoLs83wdvkc8q6kluhIez9t7qKfbQa-QoR9dtGVzBhEIrLeRpNzGsHDDK-DOEqrkIwi0pH567K7HqPBPEVgQbvZ4qFOVvWROzvjxHhCyGr2mlFh2z_MqqTVegpVg90IyJ9C9pHH4YssqCCCUtzF-mKpAUeGchy2cUqzy5zJSvCF1iGqNj8ZpzE_mkU5jkPmnUFYnNLLLkCjd_X7RHNNgFKsvm8shUycoI4tbtakfx1x-v4Fo2Y2ern6HBRnb0Py3E0Ov5oCYvzNLAr6U8dEctgGMLXiKkQyTbPulX6cy02lZ5yxB0NGNW01azuUO5hy8ZBd1JmK81qzfbu8wuqZmFv6r0Qg-E%26flowName%3DGeneralOAuthFlow%26as%3DS1980012211%253A1784484987267360%26client_id%3D115700428800-s6ngmi8555fnq8rrceqa7311dtou8m4l.apps.googleusercontent.com%26requestPath%3D%252Fsignin%252Foauth%252Fconsent%23&app_domain=http%3A%2F%2Flocalhost%3A8001";

const SignIn: React.FC = () => {
  const { login } = useAuth();

  const handleSignIn = () => {
    // In a real app, this would redirect to Google OAuth.
    // Here we simply open the URL in a new tab and mark the user as logged in.
    window.open(GOOGLE_OAUTH_URL, "_blank", "noopener,noreferrer");
    login();
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
