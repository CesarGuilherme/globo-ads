#!/usr/bin/env python3
"""Phase 2 — extract the Digital platform into a local SQLite snapshot.

Append-only model (Phase 0 proved there is NO unique dimensional grain — rows can
match on every visible field yet differ only in a hidden impression segment, and
~2% are byte-identical). So we store every row verbatim, tagged with a `run_id`,
and never upsert. Re-running a range appends a new run = full audit history.
Reports read the latest run per range.

Scope (from probe.py): this account is Digital-only. TV/audience groups are empty.

Run: python3 extract.py            # default date range below
DB:  gads.db
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from client import ApiError, COD_CLIENT, paginate, post_json

DB = "gads.db"
RANGE = {"startDate": "2024-05-01", "endDate": "2025-07-31"}


def flatten(rec: dict, prefix: str = "") -> dict:
    """Dot/underscore-flatten nested dicts; arrays stored as JSON text."""
    out: dict = {}
    for k, v in rec.items():
        col = f"{prefix}{k}".replace(".", "_")
        if isinstance(v, dict):
            out.update(flatten(v, col + "_"))
        elif isinstance(v, list):
            out[col] = json.dumps(v, ensure_ascii=False)
        else:
            out[col] = v
    return out


def ensure_runs(con):
    con.execute(
        "CREATE TABLE IF NOT EXISTS runs ("
        " run_id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT, start_date TEXT,"
        " end_date TEXT, extracted_at TEXT, total_elements INTEGER, received INTEGER)"
    )


def load(con, table: str, endpoint: str, rows: list[dict], total: int | None,
         start: str | None, end: str | None) -> int:
    flat = [flatten(r) for r in rows]
    cols = sorted({c for f in flat for c in f})
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    coldefs = ", ".join(f'"{c}"' for c in cols)
    con.execute(
        f'CREATE TABLE IF NOT EXISTS "{table}" '
        f'(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, source_endpoint TEXT,'
        f' extracted_at TEXT{"," if cols else ""} {coldefs})'
    )
    # widen table if a later run introduces new columns
    existing = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
    for c in cols:
        if c not in existing:
            con.execute(f'ALTER TABLE "{table}" ADD COLUMN "{c}"')

    cur = con.execute(
        "INSERT INTO runs (endpoint, start_date, end_date, extracted_at, total_elements, received)"
        " VALUES (?,?,?,?,?,?)",
        (endpoint, start, end, extracted_at, total, len(rows)),
    )
    run_id = cur.lastrowid

    insert_cols = ["run_id", "source_endpoint", "extracted_at"] + cols
    placeholders = ",".join("?" * len(insert_cols))
    quoted = ",".join(f'"{c}"' for c in insert_cols)
    con.executemany(
        f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
        [[run_id, endpoint, extracted_at] + [f.get(c) for c in cols] for f in flat],
    )
    con.commit()

    mark = "ok" if total is None or total == len(rows) else "WARN mismatch"
    print(f"  {table:22} run {run_id}: {len(rows)} rows"
          f"{'' if total is None else f' / totalElements {total}'}  [{mark}]")
    return run_id


def fetch_paginated(path, body):
    rows = list(paginate(path, body, size=1000))
    return rows, paginate.last_run["totalElements"]


def main():
    body = {"codClient": COD_CLIENT} if COD_CLIENT else {}
    con = sqlite3.connect(DB)
    ensure_runs(con)
    print(f"DB={DB}  codClient={COD_CLIENT}  range={RANGE['startDate']}..{RANGE['endDate']}")

    # 1. items — paginated spine
    rows, total = fetch_paginated("/digital/items", {**body, **RANGE})
    load(con, "digital_items", "/digital/items", rows, total, RANGE["startDate"], RANGE["endDate"])

    # 2. campaigns — bare list, drives demographic
    camps = post_json("/digital/campaigns", {**body, **RANGE})
    load(con, "digital_campaigns", "/digital/campaigns", camps, None,
         RANGE["startDate"], RANGE["endDate"])
    names = [c.get("nameCampaign") for c in camps if c.get("nameCampaign")]

    # 3. demographic — who saw the ads. Per-campaign: 29-at-once 504s the gateway.
    demo_rows = []
    for name in names:
        try:
            d = post_json("/digital/demographic", {**body, "campaigns": [name]})
        except ApiError as e:
            print(f"  demographic skip '{name[:40]}': HTTP {e.status}")
            continue
        recs = d.get("content", d) if isinstance(d, dict) else d
        demo_rows.extend([recs] if isinstance(recs, dict) else recs)
    if demo_rows:
        load(con, "digital_demographic", "/digital/demographic", demo_rows, None,
             RANGE["startDate"], RANGE["endDate"])

    # 4. exclusive-dai — region/time-slot breakdown (may be empty)
    try:
        dai = post_json("/digital/exclusive-dai", {**body, **RANGE})
        dai_rows = dai.get("content", dai) if isinstance(dai, dict) else dai
        if isinstance(dai_rows, dict):
            dai_rows = [dai_rows]
        if dai_rows:
            load(con, "digital_exclusive_dai", "/digital/exclusive-dai", dai_rows, None,
                 RANGE["startDate"], RANGE["endDate"])
        else:
            print("  digital_exclusive_dai: empty, skipped")
    except ApiError as e:
        print(f"  exclusive-dai skip: HTTP {e.status}")

    con.close()
    print("done.")


if __name__ == "__main__":
    main()
