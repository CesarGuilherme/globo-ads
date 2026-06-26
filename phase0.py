#!/usr/bin/env python3
"""Phase 0 — two pre-build checks that gate the extractor.

1. Grain: is codLineItem+date+creative+platform+device actually unique on a page?
   If not, find the smallest key extension that is, so upsert won't delete real rows.
2. Crawl: page /digital/items start->finish; confirm no mid-run 401 and that the
   number of records received equals the API's totalElements.

Run: python3 phase0.py
"""
from __future__ import annotations

import itertools

from client import COD_CLIENT, paginate, post_json

ITEMS = "/digital/items"
BODY = {"startDate": "2024-05-01", "endDate": "2025-07-31"}
if COD_CLIENT:
    BODY["codClient"] = COD_CLIENT

BASE_KEY = ["codLineItem", "date", "creative", "platform", "device"]
EXTRA = ["seconds", "midia", "format", "campaignType", "product", "codCampaing"]


def key(rec, fields):
    return tuple(rec.get(f) for f in fields)


def check_grain():
    page = post_json(ITEMS, {**BODY, "page": 0, "size": 1000})
    rows = page["content"]
    print(f"[grain] page 0: {len(rows)} rows, totalElements={page['totalElements']}")

    fields = list(BASE_KEY)
    while True:
        keys = [key(r, fields) for r in rows]
        dupes = len(keys) - len(set(keys))
        print(f"[grain] key={'+'.join(fields)} -> {len(set(keys))} distinct / {len(rows)} rows"
              f" ({dupes} collisions)")
        if dupes == 0:
            print(f"[grain] ✅ unique grain: {'+'.join(fields)}")
            return fields
        # widen the key by one extra dimension and retry
        added = next((f for f in EXTRA if f not in fields), None)
        if added is None:
            # show a colliding example so we can see what differs
            seen = {}
            for r in rows:
                k = key(r, fields)
                if k in seen:
                    print("[grain] ⚠ still colliding; example pair differs only in non-key fields:")
                    print("   A:", {f: seen[k].get(f) for f in EXTRA})
                    print("   B:", {f: r.get(f) for f in EXTRA})
                    break
                seen[k] = r
            print("[grain] ❌ no unique grain from candidate fields — needs manual review")
            return None
        fields.append(added)


def check_crawl():
    n = sum(1 for _ in paginate(ITEMS, BODY, size=1000))
    info = paginate.last_run
    ok = n == info["totalElements"]
    mark = "✅" if ok else "⚠"
    print(f"[crawl] {mark} received {n} records; API totalElements={info['totalElements']}"
          f"{'' if ok else '  (mismatch — restatement or page drift; warn, do not abort)'}")
    return ok


if __name__ == "__main__":
    print("=== Phase 0.1 — prove the grain ===")
    grain = check_grain()
    print("\n=== Phase 0.2 — prove a full crawl survives ===")
    check_crawl()
    print("\ngrain key =", "+".join(grain) if grain else "UNRESOLVED")
