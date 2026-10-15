"""Grok sign-in. Device-code flow from the public Grok CLI client, same as skgate.

Tokens stay in the user config directory. Nothing here prints them.
"""

from __future__ import annotations

import base64
import json
import os
import time
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hearth.net import secure_context
from hearth.paths import config_dir

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
SCOPES = "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write"
ISSUER = "https://auth.x.ai"
FALLBACK_BASE = "https://cli-chat-proxy.grok.com/v1"
CLI_HEADERS = {
    "x-xai-token-auth": "xai-grok-cli",
    "x-grok-client-identifier": "grok-shell",
    "x-grok-client-version": "0.2.93",
}
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"

_poll_cancel = Event()


def _token_path():
    return config_dir() / "grok-oauth.json"


def _fallback_endpoints() -> dict:
    root = ISSUER.rstrip("/")
    return {
        "authorization": root + "/oauth2/authorize",
        "device": root + "/oauth2/device/code",
        "token": root + "/oauth2/token",
    }


def endpoints() -> dict:
    found = _fallback_endpoints()
    try:
        request = Request(ISSUER + "/.well-known/openid-configuration", headers={"Accept": "application/json"})
        with urlopen(request, timeout=8, context=secure_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError, TimeoutError):
        return found
    if isinstance(payload, dict):
        if isinstance(payload.get("device_authorization_endpoint"), str):
            found["device"] = payload["device_authorization_endpoint"]
        if isinstance(payload.get("token_endpoint"), str):
            found["token"] = payload["token_endpoint"]
    return found


def signed_in() -> bool:
    data = _load()
    return bool(data.get("access_token") and data.get("refresh_token"))


def sign_out() -> None:
    _poll_cancel.set()
    _token_path().unlink(missing_ok=True)


def access_token() -> str:
    data = _load()
    if not data.get("refresh_token"):
        raise RuntimeError("Sign in to Grok.")
    if float(data.get("expires_at") or 0) - time.time() < 120:
        data = _refresh(data)
    token = data.get("access_token") or ""
    if not token:
        raise RuntimeError("Sign in to Grok.")
    return token


def start_device() -> dict:
    """Begin a device-code sign-in. The returned dict includes the device code; do not show that field."""
    _poll_cancel.clear()
    status, payload = _post_form(endpoints()["device"], {"client_id": CLIENT_ID, "scope": SCOPES})
    flow = _device_from_payload(status, payload)
    if flow.get("error"):
        raise RuntimeError(flow["error"])
    return flow


def poll(flow: dict, cancel: Event) -> str:
    """Block until the sign-in finishes. Returns 'ok' or 'cancelled'."""
    interval = max(1, int(flow.get("interval") or 5))
    deadline = float(flow["expires_at"])
    token_url = endpoints()["token"]
    while time.time() < deadline:
        if cancel.is_set() or _poll_cancel.is_set():
            return "cancelled"
        time.sleep(interval)
        if cancel.is_set() or _poll_cancel.is_set():
            return "cancelled"
        status, payload = _post_form(token_url, {
            "grant_type": DEVICE_GRANT,
            "client_id": CLIENT_ID,
            "device_code": flow["device_code"],
        })
        outcome = _token_outcome(status, payload)
        if outcome == "pending":
            continue
        if outcome == "slow":
            interval = min(interval + 5, 30)
            continue
        if isinstance(outcome, str):
            raise RuntimeError(outcome)
        _save(outcome)
        return "ok"
    raise RuntimeError("The sign-in code expired. Start again.")


def _device_from_payload(status: int, payload: dict) -> dict:
    if status // 100 != 2 or not payload.get("device_code"):
        code = payload.get("error") or ""
        return {"error": f"Could not start Grok sign-in ({status}{(' ' + code) if code else ''})."}
    expires = int(payload.get("expires_in") or 900)
    interval = int(payload.get("interval") or 5)
    return {
        "device_code": payload["device_code"],
        "user_code": str(payload.get("user_code") or ""),
        "verification_uri": str(payload.get("verification_uri") or payload.get("verification_url") or ""),
        "verification_uri_complete": str(payload.get("verification_uri_complete") or ""),
        "interval": max(interval, 1),
        "expires_at": time.time() + max(expires, 30),
    }


def _token_outcome(status: int, payload: dict):
    error = str(payload.get("error") or "")
    if error == "authorization_pending":
        return "pending"
    if error == "slow_down":
        return "slow"
    if error in ("access_denied", "authorization_denied"):
        return "Grok sign-in was denied."
    if error == "expired_token":
        return "The sign-in code expired. Start again."
    if status == 403:
        return "This Grok account cannot use sign-in here."
    if error:
        return "Grok sign-in failed."
    if status // 100 != 2 or not payload.get("access_token") or not payload.get("refresh_token"):
        return "Grok sign-in did not return a token."
    return _tokens_from_response(payload)


def _tokens_from_response(payload: dict, previous: dict | None = None) -> dict:
    refresh = payload.get("refresh_token") or (previous or {}).get("refresh_token") or ""
    expires = _expires_at(payload.get("expires_in"), payload.get("access_token") or "")
    return {
        "access_token": payload["access_token"],
        "refresh_token": refresh,
        "expires_at": expires,
    }


def _expires_at(expires_in, access: str) -> float:
    seconds = 0.0
    if isinstance(expires_in, (int, float)):
        seconds = float(expires_in)
    elif isinstance(expires_in, str):
        try:
            seconds = float(expires_in)
        except ValueError:
            seconds = 0.0
    if seconds > 0:
        return time.time() + seconds
    exp = _jwt_exp(access)
    if exp:
        return exp
    return time.time() + 15 * 60


def _jwt_exp(token: str) -> float:
    parts = token.split(".")
    if len(parts) != 3:
        return 0.0
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return 0.0
    exp = payload.get("exp") if isinstance(payload, dict) else None
    return float(exp) if isinstance(exp, (int, float)) else 0.0


def _refresh(previous: dict) -> dict:
    status, payload = _post_form(endpoints()["token"], {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": previous["refresh_token"],
    })
    error = str(payload.get("error") or "")
    if status in (400, 401) or error == "invalid_grant":
        sign_out()
        raise RuntimeError("Grok sign-in expired. Sign in again.")
    if status == 403:
        raise RuntimeError("This Grok account cannot use sign-in here.")
    if status // 100 != 2 or not payload.get("access_token"):
        raise RuntimeError("Could not refresh the Grok sign-in.")
    saved = _tokens_from_response(payload, previous)
    if not saved["refresh_token"]:
        saved["refresh_token"] = previous["refresh_token"]
    _save(saved)
    return saved


def _load() -> dict:
    path = _token_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(tokens: dict) -> None:
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
    }) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def _post_form(url: str, form: dict) -> tuple[int, dict]:
    data = urlencode(form).encode("utf-8")
    request = Request(url, data=data, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "iphone-layout",
    })
    try:
        with urlopen(request, timeout=30, context=secure_context()) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except (OSError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach Grok sign-in. {exc}") from exc
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {}
    return status, payload if isinstance(payload, dict) else {}
