#!/usr/bin/env python3
"""Validate the Globo Ads Resultados API token in .env.

Loads `access_token` from .env and calls the agency "clients_accrediteds"
endpoint (the lightest authenticated route). A valid token returns HTTP 200
with a JSON list of accredited clients; an invalid/expired one returns 401.

Per the API docs, the platform-issued token goes straight into the
`Authorization` header (the doc's examples omit the "Bearer " prefix), so the
bare token is tried first, falling back to "Bearer <token>".

Usage:
    python3 check_token.py

Exit codes: 0 = valid token, 1 = invalid/rejected, 2 = setup/network error.
Stdlib only — no dependencies required.
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api-ads-resultados.mybackstage.globo.com/api/v1/agency/clients_accrediteds"
ENV_PATH = Path(__file__).resolve().parent / ".env"
TIMEOUT = 30


TOKEN_KEY = "access_token"


def load_token(env_path: Path) -> str:
    """Read the `access_token` value from a simple KEY=VALUE .env file."""
    if not env_path.exists():
        sys.exit(f"[setup] {env_path} not found.")
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == TOKEN_KEY:
            return value.strip().strip("'\"")
    sys.exit(f"[setup] No `{TOKEN_KEY}=` entry found in .env.")


def describe_token(token: str) -> None:
    """Best-effort hint about the token's shape (a real one is a 3-part JWT)."""
    segments = token.count(".") + 1
    note = "looks like a JWT" if segments == 3 else "NOT a 3-part JWT — likely malformed"
    print(f"  token: {len(token)} chars, {segments} segment(s) — {note}")
    if segments != 3:
        # The decoded base64 may reveal it's a client descriptor, not a credential.
        import urllib.parse

        candidate = urllib.parse.unquote(token)
        candidate += "=" * (-len(candidate) % 4)
        try:
            payload = base64.urlsafe_b64decode(candidate).decode("utf-8")
            data = json.loads(payload)
            print(f"  ⚠ decodes to JSON, not a credential: {json.dumps(data, ensure_ascii=False)}")
        except (ValueError, UnicodeDecodeError):
            pass


def _request(auth_value: str) -> tuple[int | None, str]:
    """POST to the endpoint with the given Authorization value. Returns
    (status, body); status is None on a network failure."""
    request = urllib.request.Request(
        API_URL,
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_value,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        print(f"[network] request failed: {exc.reason}")
        return None, ""


def check(token: str) -> int:
    # The docs put the raw token in Authorization (no "Bearer "), so try that
    # first and fall back to the Bearer-prefixed form before giving a verdict.
    last_status: int | None = None
    for auth_value, label in ((token, "bare token"), (f"Bearer {token}", "Bearer <token>")):
        status, body = _request(auth_value)
        if status is None:
            return 2

        print(f"  [{label}] HTTP {status} <- {API_URL}")
        snippet = body[:300] + ("…" if len(body) > 300 else "")
        print(f"  response: {snippet}")
        last_status = status

        if status == 200:
            print(f"\n✅ Token is VALID (accepted as: {label}).")
            return 0
        if status == 403:
            print(f"\n⚠ Token authenticated but FORBIDDEN for this route (403, as {label}) — "
                  "check that this is an Agency-profile token.")
            return 1

    if last_status == 401:
        print("\n❌ Token is INVALID (401: invalid or missing token) for both header forms.")
        return 1
    print(f"\n⚠ Unexpected status {last_status}; token validity inconclusive.")
    return 1


def main() -> int:
    token = load_token(ENV_PATH)
    describe_token(token)
    return check(token)


if __name__ == "__main__":
    raise SystemExit(main())
