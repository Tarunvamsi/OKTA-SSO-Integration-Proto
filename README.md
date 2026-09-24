# Automation Anywhere: Okta SSO + FastAPI prototype

This prototype has a plain HTML/CSS/JavaScript sign-in page and a FastAPI backend. Okta hosts the sign-in page. The browser uses OpenID Connect Authorization Code with PKCE, then sends an access token to FastAPI. FastAPI validates that token against the Okta authorization server's signing keys.

The frontend is a public Single-Page Application (SPA), so it uses a **client ID only**. Do not create, copy, or add a client secret to this project.

## What you need from Okta

Collect these values before configuring the project:

| Value | Where to find it | Used in |
|---|---|---|
| Client ID | Your app integration → **General** → **Client Credentials** | `OKTA_CLIENT_ID` in `app.js` |
| Issuer URI | **Security → API → Authorization Servers → default** | `OKTA_ISSUER` in `app.js` and `.env` |
| Audience | The same `default` authorization server details | `OKTA_AUDIENCE` in `.env` |

For the default custom authorization server, the issuer commonly looks like `https://your-org.okta.com/oauth2/default`, and the audience commonly is `api://default`. Use the exact Issuer URI and Audience displayed in your own Okta org. Do not use the Admin Console URL as the issuer.

## 1. Create the Okta OIDC SPA integration

If you already created the integration, check its settings against this list and continue to step 2.

1. Sign in to the Okta Admin Console. Use an existing org where you can administer apps, or create an [Okta Integrator Free Plan org](https://developer.okta.com/signup/) for development.
2. Open **Applications → Applications → Create App Integration**.
3. Choose **SSO (OIDC)** / **OIDC - OpenID Connect**, then choose **Single-Page Application (SPA)**. This is a private app integration for your own prototype; don't create or publish an OIN Catalog listing.
4. Give it a name, such as `SSO Proto`.
5. In grant types, enable **Authorization Code**. This project uses PKCE. **Refresh Token** is optional and isn't needed for this demo. Leave **Proof of Possession / DPoP** unchecked.
6. Set the URLs exactly:
   - **Sign-in redirect URI:** `http://localhost:8000/`
   - **Sign-out redirect URI:** `http://localhost:8000/`
7. For **Controlled access**, choose **Allow everyone in your organization to access** for a broad internal demo, or assign only your test users/groups. Leave **Enable immediate access with Federation Broker Mode** unchecked; it isn't needed here.
8. Save the integration. Copy its **Client ID** from **General → Client Credentials**.

The sign-in URI must match the configured callback exactly, including scheme, hostname, port, and trailing slash. The code currently sets it explicitly to `http://localhost:8000/` in `app.js` as `OKTA_REDIRECT_URI`.

## 2. Add a Trusted Origin

This is separate from the sign-in and sign-out redirect URI fields.

1. Open **Security → API → Trusted Origins → Add Origin**.
2. Name it, for example, `Automation Anywhere local`.
3. Set **Origin URL** to `http://localhost:8000` (no trailing slash).
4. Enable **CORS** and **Redirect**, then save. Do not enable iFrame embedding.

## 3. Assign your test user

If you selected **Allow everyone in your organization to access**, confirm the intended account belongs to this Okta org. Otherwise, open the app's **Assignments** tab and assign your test user or group. The user signing in must be in this same org and have app access.

## 4. Configure the authorization server policy

The backend validates access tokens issued by a custom authorization server. A new Integrator Free Plan org's `default` server may not have an access policy. Without a matching policy and rule, sign-in can fail with **“Policy evaluation failed for this request.”**

1. Open **Security → API → Authorization Servers → default**.
2. Note the **Issuer URI** and **Audience** for use in step 5. Confirm the server is active.
3. Open **Access Policies**. If there isn't already a policy for this app, choose **Add Policy**. Name it (for example, `SSO Proto policy`), select **The following clients**, choose your OIDC SPA app, and create the policy.
4. Open the policy and choose **Add Rule**. Configure a rule that matches:
   - **Grant type:** Authorization Code
   - **User:** Any user assigned to the app
   - **Scopes requested:** Any scopes
5. Save the rule. The app requests `openid`, `profile`, and `email`; those standard OIDC scopes don't need custom scope definitions. Ensure the policy/rule is active and matches the SPA client.

App assignment and authorization server policies are separate controls: a user can be assigned to the app while token issuance is still blocked by a missing or non-matching policy rule.

## 5. Configure the project values

Edit the constants near the top of `app.js` with your issuer and client ID. Keep the callback URI set to the URL registered in Okta:

```js
const OKTA_ISSUER = "https://your-org.okta.com/oauth2/default";
const OKTA_CLIENT_ID = "paste-your-client-id-here";
const OKTA_REDIRECT_URI = "http://localhost:8000/";
```

Copy `.env.example` to `.env`, then edit `.env` to use the issuer and audience copied from the authorization server:

```env
OKTA_ISSUER=https://your-org.okta.com/oauth2/default
OKTA_AUDIENCE=api://default
```

Do not commit `.env`; it is excluded by `.gitignore`. It contains backend configuration, not a client secret.

## 6. Install and start FastAPI

Use Python 3.10 or newer. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

Edit `.env` with your Okta values, then install dependencies and start the server:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --no-access-log --port 8000
```

On Windows PowerShell, activate the virtual environment with `.venv\Scripts\Activate.ps1` and copy the example with `Copy-Item .env.example .env`.

Open **http://localhost:8000/** in your browser. Use this exact hostname; `127.0.0.1`, another port, or opening `index.html` as a file is a different origin/callback.

## 7. Verify the sign-in

1. Click **Continue with Okta**.
2. Sign in as the Okta user assigned to the app (or a user covered by the Everyone assignment).
3. Okta should redirect to `http://localhost:8000/`, where the dashboard displays the signed-in profile.
4. The dashboard calls `GET /api/me` with `Authorization: Bearer <access-token>`. A success message confirms FastAPI validated the access token.
5. **Sign out** redirects through Okta and returns to the same local page.

`http://localhost:8000/api/health` is a public backend health check. `/api/me` requires a valid access token.

## Backend logs

Keep the terminal running Uvicorn open while using the demo. The backend logs configuration at startup, request start/completion with a request ID, method, path, status, client IP, and duration, plus the stages and outcome of `/api/me` token validation. Responses also include an `X-Request-ID` header so a browser request can be matched to its terminal log entries.

The app intentionally does not log request query strings, headers, request bodies, bearer tokens, or user profile claims. Start Uvicorn with `--no-access-log` as shown above so its default access logger doesn't print Okta callback query parameters (which can contain a one-time authorization code).

## Troubleshooting

- **`redirect_uri` must be a Login redirect URI**: confirm you opened `http://localhost:8000/`, the app's Sign-in redirect URI is exactly `http://localhost:8000/`, and `OKTA_REDIRECT_URI` in `app.js` matches. Hard-refresh after editing JavaScript.
- **“You are not allowed to access this app”**: assign the user on the app's **Assignments** tab or confirm the user is in the app's Everyone assignment and belongs to this Okta org.
- **“Policy evaluation failed for this request”**: in **Security → API → Authorization Servers → default → Access Policies**, ensure a policy targets this SPA and has an active rule matching **Authorization Code**, the assigned user, and **Any scopes**.
- **401 from `/api/me`**: confirm the backend's `.env` issuer and audience match the exact values shown for the same authorization server that issued the token.
- **Issuer/JWKS error**: use the complete Issuer URI from the authorization server, typically ending in `/oauth2/default`, not the Admin Console URL.
- **`PyJWKClientConnectionError` with `CERTIFICATE_VERIFY_FAILED` / “unable to get local issuer certificate”**: Python can't verify the HTTPS certificate when fetching Okta's JWKS signing keys. Install/use a trusted CA bundle; do not disable TLS certificate verification.

  **macOS:** In a terminal, stop Uvicorn with Ctrl+C, activate the project's virtual environment, install/update Certifi, then restart Uvicorn with Certifi's CA bundle configured:

  ```bash
  source .venv/bin/activate
  python -m pip install --upgrade certifi
  SSL_CERT_FILE="$(python -m certifi)" uvicorn main:app --reload --no-access-log --port 8000
  ```

  If you installed Python from python.org, you can instead run **Install Certificates.command** in the matching `/Applications/Python 3.x/` folder, then reopen the terminal and restart Uvicorn.

  **Windows PowerShell:** Stop Uvicorn with Ctrl+C, activate the virtual environment, install/update Certifi, set `SSL_CERT_FILE` for this terminal session, then restart Uvicorn:

  ```powershell
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade certifi
  $env:SSL_CERT_FILE = (python -m certifi)
  uvicorn main:app --reload --no-access-log --port 8000
  ```

  Keep that terminal open while Uvicorn is running. If your network uses HTTPS inspection, Certifi may not contain your organization's root certificate; ask your IT administrator for the approved CA certificate and trust configuration.
- **Sign-out error**: confirm `http://localhost:8000` is listed as a Trusted Origin with Redirect enabled and is also in the app's Sign-out redirect URIs.
- **Okta CDN/font load error**: this demo loads Okta Auth JS from `global.oktacdn.com` and fonts from Google Fonts, so the browser needs access to those hosts.

## Prototype notes

This is a local demo. For production, use HTTPS, review token storage and XSS protections, create a dedicated authorization server and least-privilege API scopes, and add role-based authorization and normal deployment controls. This example verifies token identity and validity; it does not implement roles.
