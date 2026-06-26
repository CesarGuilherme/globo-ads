#!/usr/bin/env python3
"""Shared Globo Ads Resultados API client.

One place for: the base URL, loading the platform token + codClient from `.env`,
a `post()` helper (bare `Authorization` header, no "Bearer"), and a generic
`paginate()` over Spring-style responses (content[]/totalElements/totalPages/last).

Used by probe.py, extract.py and report.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import pymysql
import requests
from dotenv import load_dotenv

BASE_URL = "https://api-ads-resultados.mybackstage.globo.com/api/v1"
ENV_PATH = Path(__file__).resolve().parent / ".env"
TIMEOUT = 60

load_dotenv(ENV_PATH)
TOKEN = os.environ.get("api_token", "").strip()
COD_CLIENT = int(os.environ["cod_client"]) if os.environ.get("cod_client") else None


def mysql_conn():
    """Connection to the shared airbyte_secom warehouse (creds from .env)."""
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"], charset="utf8mb4", autocommit=False,
    )

_session = requests.Session()
_session.headers.update({"Content-Type": "application/json", "User-Agent": "secom-gads/1.0"})


class ApiError(RuntimeError):
    def __init__(self, status: int, path: str, body: str):
        self.status, self.path, self.body = status, path, body
        super().__init__(f"HTTP {status} on {path}: {body[:300]}")


def post(path: str, body: dict) -> requests.Response:
    """POST to <BASE_URL><path> with the bare token. Returns the raw Response
    (caller decides how to treat non-2xx); never raises on HTTP status."""
    if not TOKEN:
        raise SystemExit("[setup] no `api_token=` in .env")
    return _session.post(
        f"{BASE_URL}{path}", data=_json(body),
        headers={"Authorization": TOKEN}, timeout=TIMEOUT,
    )


def post_json(path: str, body: dict) -> dict:
    """POST and return parsed JSON, raising ApiError on non-2xx."""
    r = post(path, body)
    if not r.ok:
        raise ApiError(r.status_code, path, r.text)
    return r.json()


def paginate(path: str, body: dict, size: int = 1000):
    """Yield records from every page of a Spring-paginated endpoint.

    Sends `page`/`size` in the body and walks 0..totalPages-1, stopping on the
    `last` flag. Also yields a final per-run dict of integrity counters via the
    `.integrity` attribute set on the generator's closure — read it after the
    loop (see extract.py).
    # ponytail: offset paging can drift if the server re-sorts mid-crawl. For
    # past-dated, already-settled report data this is negligible; revisit with a
    # stable `sort` param only if a live re-pull shows row skew.
    """
    page, received, total = 0, 0, None
    while True:
        payload = post_json(path, {**body, "page": page, "size": size})
        content = payload.get("content", [])
        if total is None:
            total = payload.get("totalElements")
        received += len(content)
        for rec in content:
            yield rec
        paginate.last_run = {"received": received, "totalElements": total}
        if payload.get("last") or not content or page + 1 >= (payload.get("totalPages") or 1):
            break
        page += 1


def _json(body: dict) -> str:
    import json
    return json.dumps(body, ensure_ascii=False)
