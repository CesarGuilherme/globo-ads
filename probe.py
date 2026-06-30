#!/usr/bin/env python3
"""Phase 1 — probe which of the 6 platform groups hold data for this account.

POSTs the cheapest endpoint per group with codClient and reports HTTP status +
record count, so Phase 2 only extracts platforms that actually have data.

Run: python3 probe.py
"""
from __future__ import annotations

from client import COD_CLIENT, post

DATES = {"startDate": "2024-05-01", "endDate": "2025-07-31"}

# (label, path, body) — cheapest endpoint per group that proves data exists.
PROBES = [
    ("Digital · campaigns", "/digital/campaigns", {**DATES}),
    ("Digital · items", "/digital/items", {**DATES, "size": 250}),
    ("TV Aberta · projects", "/freetoair/projects", {}),
    ("TV Fechada · projects", "/paytv/projects", {}),
    ("Aud.Agregada · TV Aberta projetos", "/aggregated/audience/free-to-air/projects", {**DATES}),
    ("Aud.Agregada · TV Fechada projetos", "/aggregated/audience/pay-tv/projects", {**DATES}),
    ("Globo Impacto · orders (freetoair)", "/globoimpact/orders", {"type": "freetoair"}),
    ("Globo Impacto · orders (paytv)", "/globoimpact/orders", {"type": "paytv"}),
    ("Globo Impacto · orders (multiplatform)", "/globoimpact/orders", {"type": "multiplatform"}),
]


def count(payload) -> int | str:
    if isinstance(payload, dict):
        for k in ("content", "response", "orders", "creatives", "purchaseTypes"):
            v = payload.get(k)
            if isinstance(v, list):
                return payload.get("totalElements", len(v))
        return "obj"
    if isinstance(payload, list):
        return len(payload)
    return "?"


def main():
    body_base = {"codClient": COD_CLIENT} if COD_CLIENT else {}
    print(f"codClient = {COD_CLIENT}\n")
    print(f"{'platform / endpoint':42} {'HTTP':5} {'records':>8}")
    print("-" * 60)
    for label, path, extra in PROBES:
        r = post(path, {**body_base, **extra})
        n = ""
        if r.ok:
            try:
                n = count(r.json())
            except ValueError:
                n = "non-json"
        else:
            n = r.text[:40].replace("\n", " ")
        print(f"{label:42} {r.status_code:<5} {str(n):>8}")


if __name__ == "__main__":
    main()
