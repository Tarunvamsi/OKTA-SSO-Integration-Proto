import os
import logging
import time
from pathlib import Path
from uuid import uuid4

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from jwt import PyJWKClient
from starlette.requests import Request

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
OKTA_ISSUER = os.getenv("OKTA_ISSUER", "").rstrip("/")
OKTA_AUDIENCE = os.getenv("OKTA_AUDIENCE", "api://default")

app = FastAPI(title="Automation Anywhere Okta SSO demo")
logger = logging.getLogger("uvicorn.error")
jwks_client = PyJWKClient(f"{OKTA_ISSUER}/v1/keys", timeout=10) if OKTA_ISSUER else None

logger.info(
    "auth.config loaded issuer=%s audience=%s jwks_configured=%s",
    OKTA_ISSUER or "<missing>",
    OKTA_AUDIENCE,
    jwks_client is not None,
)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_id = uuid4().hex[:12]
    request.state.request_id = request_id
    client_host = request.client.host if request.client else "unknown"
    started_at = time.perf_counter()

    # Log the path only. Never log query strings, headers, or bodies: an Okta
    # callback query string can contain a short-lived authorization code.
    logger.info(
        "http.request.start request_id=%s method=%s path=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        client_host,
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logger.exception(
            "http.request.error request_id=%s method=%s path=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http.request.complete request_id=%s method=%s path=%s status=%s elapsed_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


def verify_access_token(authorization: str | None, request_id: str) -> dict:
    if not OKTA_ISSUER:
        logger.error("auth.token.reject request_id=%s reason=issuer_not_configured", request_id)
        raise HTTPException(status_code=503, detail="Set OKTA_ISSUER in the backend environment.")
    if not authorization or not authorization.lower().startswith("bearer "):
        logger.warning("auth.token.reject request_id=%s reason=missing_bearer_token", request_id)
        raise HTTPException(status_code=401, detail="Missing bearer access token.")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        logger.warning("auth.token.reject request_id=%s reason=empty_bearer_token", request_id)
        raise HTTPException(status_code=401, detail="Missing bearer access token.")

    logger.info("auth.token.validation.start request_id=%s", request_id)
    try:
        if jwks_client is None:
            raise HTTPException(status_code=503, detail="Okta JWKS client is not configured.")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OKTA_AUDIENCE,
            issuer=OKTA_ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        logger.info(
            "auth.token.validation.success request_id=%s key_id=%s scopes=%s",
            request_id,
            signing_key.key_id,
            claims.get("scp", []),
        )
        return claims
    except (jwt.PyJWTError, jwt.PyJWKClientError, ValueError) as exc:
        # Log the reason/type, never the bearer token or its claims.
        logger.warning(
            "auth.token.validation.failed request_id=%s error_type=%s reason=%s",
            request_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc


@app.get("/api/health")
def health():
    logger.info("api.health.success")
    return {"status": "ok"}


@app.get("/api/me")
def me(request: Request, authorization: str | None = Header(default=None)):
    request_id = request.state.request_id
    claims = verify_access_token(authorization, request_id)
    payload = {
        "message": f"Hello, {claims.get('name') or claims.get('sub')}! FastAPI verified your Okta access token.",
        "subject": claims["sub"],
        "scopes": claims.get("scp", []),
    }
    logger.info("api.me.success request_id=%s", request_id)
    return payload


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    candidate = (BASE_DIR / path).resolve()
    if candidate.is_file() and BASE_DIR in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(BASE_DIR / "index.html")
