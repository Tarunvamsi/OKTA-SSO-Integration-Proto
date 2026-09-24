// Set this to your Okta org issuer and SPA client ID (see README.md).
const OKTA_ISSUER = "https://integrator-1720004.okta.com/oauth2/default";
const OKTA_CLIENT_ID = "0oa17z0nzb3b7GlKq698";
const OKTA_REDIRECT_URI = "http://localhost:8000/";

const statusEl = document.getElementById("status");
const signInButton = document.getElementById("sign-in");
const oktaConfigured = !OKTA_ISSUER.includes("YOUR_OKTA_DOMAIN") && !OKTA_CLIENT_ID.includes("YOUR_CLIENT_ID");
let auth;

function setStatus(message, error = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", error);
}

function showDashboard(claims) {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-view").classList.remove("hidden");
  const name = claims.name || claims.preferred_username || claims.email || "Okta user";
  document.getElementById("user-name").textContent = name;
  document.getElementById("user-email").textContent = claims.email || claims.preferred_username || "";
  document.getElementById("avatar").textContent = name.charAt(0).toUpperCase();
}

async function loadProtectedData() {
  const accessToken = await auth.getAccessToken();
  const response = await fetch("/api/me", { headers: { Authorization: `Bearer ${accessToken}` } });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "Could not load protected API data.");
  document.getElementById("api-message").textContent = body.message;
}

async function start() {
  if (!oktaConfigured) {
    signInButton.disabled = true;
    setStatus("Add your Okta issuer and client ID in app.js to enable sign-in.", true);
    return;
  }
  if (!window.OktaAuth) {
    setStatus("Okta’s sign-in library did not load. Check your internet connection and reload.", true);
    return;
  }
  auth = new OktaAuth({
    issuer: OKTA_ISSUER,
    clientId: OKTA_CLIENT_ID,
    redirectUri: OKTA_REDIRECT_URI,
    scopes: ["openid", "profile", "email"],
    pkce: true,
    tokenManager: { storage: "sessionStorage" },
    postLogoutRedirectUri: OKTA_REDIRECT_URI
  });

  try {
    if (auth.isLoginRedirect()) await auth.handleRedirect();
    if (await auth.isAuthenticated()) {
      const claims = await auth.getUser();
      showDashboard(claims || {});
      await loadProtectedData();
    }
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Sign-in could not be completed. Please try again.", true);
    if (auth && auth.isLoginRedirect()) history.replaceState({}, document.title, "/");
  }
}

signInButton.addEventListener("click", async () => {
  if (!auth) return;
  signInButton.disabled = true;
  setStatus("Redirecting to Okta…");
  try { await auth.signInWithRedirect(); }
  catch (error) { setStatus(error.message || "Could not start sign-in.", true); signInButton.disabled = false; }
});

document.getElementById("sign-out").addEventListener("click", async () => {
  try { await auth.signOut({ postLogoutRedirectUri: OKTA_REDIRECT_URI }); }
  catch (error) { console.error(error); setStatus("Sign-out failed. Please reload and try again.", true); }
});

start();
