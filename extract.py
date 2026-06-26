#!/usr/bin/env python3
"""Extract /digital/items into the shared MySQL warehouse (airbyte_secom).

Designed to run from n8n: Schedule -> Execute Command -> `python3 extract.py [start] [end]`.

Append-only model (Phase 0 proved /digital/items has NO unique dimensional grain — rows
can match on every visible field yet differ only in a hidden impression segment, and ~2%
are byte-identical). So we never upsert: each run inserts a verbatim snapshot tagged with
a `run_id` + `extracted_at`; downstream reads MAX(run_id). The `globoAds_runs` ledger
records each run (refresh_log style) for monitoring.

Scope (from probe.py): SECOM is Digital-only; only /digital/items carries value
(demographic arrays empty, campaigns is just names, DAI empty).

Tables: airbyte_secom.globoAds_campaigns  +  airbyte_secom.globoAds_runs
"""
from __future__ import annotations

import sys
from datetime import datetime

from client import COD_CLIENT, mysql_conn, paginate

DEFAULT_RANGE = ("2024-05-01", "2025-07-31")

# (column, MySQL type, caster) — ordered; drives both DDL and INSERT. Names preserved
# from the API (incl. the `codCampaing` typo) per project convention.
_int = lambda v: int(round(v)) if v is not None else None        # noqa: E731
_dec = lambda v: v                                                # noqa: E731  (float -> DECIMAL)
_str = lambda v: v                                                # noqa: E731
COLUMNS = [
    ("date", "DATE", _str),
    ("codLineItem", "BIGINT", _int),
    ("lineItem", "VARCHAR(500)", _str),
    ("creative", "VARCHAR(500)", _str),
    ("project", "VARCHAR(255)", _str),
    ("codCampaing", "VARCHAR(50)", _str),
    ("campaign", "VARCHAR(500)", _str),
    ("codClient", "BIGINT", _int),
    ("nameClient", "VARCHAR(255)", _str),
    ("codAgency", "BIGINT", _int),
    ("nameAgency", "VARCHAR(255)", _str),
    ("product", "VARCHAR(100)", _str),
    ("format", "VARCHAR(100)", _str),
    ("campaignType", "VARCHAR(50)", _str),
    ("platform", "VARCHAR(255)", _str),
    ("clicks", "BIGINT", _int),
    ("impression_impressionsContracted", "BIGINT", _int),
    ("impression_impressionsDelivered", "BIGINT", _int),
    ("video_viewAll", "BIGINT", _int),
    ("video_viewTwentyFive", "BIGINT", _int),
    ("video_viewFifty", "BIGINT", _int),
    ("video_viewSeventyFive", "BIGINT", _int),
    ("video_vtr", "BIGINT", _int),
    ("seconds", "VARCHAR(50)", _str),
    ("device", "VARCHAR(50)", _str),
    ("midia", "VARCHAR(100)", _str),
    ("investment_lineItem", "DECIMAL(14,2)", _dec),
    ("investment_campaign", "DECIMAL(14,2)", _dec),
]

DDL_CAMPAIGNS = (
    "CREATE TABLE IF NOT EXISTS globoAds_campaigns (\n"
    "  id BIGINT AUTO_INCREMENT PRIMARY KEY,\n"
    "  run_id BIGINT NOT NULL,\n"
    "  extracted_at DATETIME NOT NULL,\n"
    + "".join(f"  `{c}` {t},\n" for c, t, _ in COLUMNS)
    + "  INDEX idx_run (run_id),\n"
    "  INDEX idx_date (date),\n"
    "  INDEX idx_campaign (codCampaing)\n"
    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
)

DDL_RUNS = (
    "CREATE TABLE IF NOT EXISTS globoAds_runs (\n"
    "  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,\n"
    "  start_date DATE, end_date DATE,\n"
    "  started_at DATETIME NOT NULL, finished_at DATETIME NULL,\n"
    "  total_elements INT NULL, received INT NULL,\n"
    "  status ENUM('RUNNING','SUCCESS','ERROR') NOT NULL DEFAULT 'RUNNING',\n"
    "  error_message TEXT NULL\n"
    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
)


def flatten(rec: dict) -> dict:
    """Dot->underscore flatten of the one-level-nested impression/video/investment objects."""
    out = {}
    for k, v in rec.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                out[f"{k}_{kk}"] = vv
        else:
            out[k] = v
    return out


def main():
    start, end = (sys.argv[1], sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_RANGE
    body = {"codClient": COD_CLIENT} if COD_CLIENT else {}
    body |= {"startDate": start, "endDate": end}
    started_at = datetime.now()

    con = mysql_conn()
    run_id = None
    try:
        with con.cursor() as cur:
            cur.execute(DDL_CAMPAIGNS)
            cur.execute(DDL_RUNS)
            cur.execute(
                "INSERT INTO globoAds_runs (start_date, end_date, started_at, status)"
                " VALUES (%s, %s, %s, 'RUNNING')", (start, end, started_at))
            run_id = cur.lastrowid
        con.commit()
        print(f"run {run_id}: pulling /digital/items {start}..{end} (codClient={COD_CLIENT})")

        rows = list(paginate("/digital/items", body, size=1000))
        total = paginate.last_run["totalElements"]

        cols = [c for c, _, _ in COLUMNS]
        casters = {c: f for c, _, f in COLUMNS}
        values = []
        for r in rows:
            flat = flatten(r)
            values.append([run_id, started_at] + [casters[c](flat.get(c)) for c in cols])

        collist = ", ".join(["run_id", "extracted_at"] + [f"`{c}`" for c in cols])
        ph = ", ".join(["%s"] * (len(cols) + 2))
        with con.cursor() as cur:
            cur.executemany(
                f"INSERT INTO globoAds_campaigns ({collist}) VALUES ({ph})", values)
            cur.execute(
                "UPDATE globoAds_runs SET finished_at=%s, total_elements=%s, received=%s,"
                " status='SUCCESS' WHERE run_id=%s",
                (datetime.now(), total, len(rows), run_id))
        con.commit()

        ok = total is None or total == len(rows)
        print(f"  loaded {len(rows)} rows / totalElements {total}  "
              f"[{'ok' if ok else 'WARN mismatch — restatement or page drift'}]")
        print(f"  globoAds_runs.run_id={run_id} status=SUCCESS")
    except Exception as exc:  # mark the run failed (if one was opened), then re-raise
        con.rollback()
        if run_id is not None:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE globoAds_runs SET finished_at=%s, status='ERROR', error_message=%s"
                    " WHERE run_id=%s", (datetime.now(), str(exc)[:2000], run_id))
            con.commit()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
