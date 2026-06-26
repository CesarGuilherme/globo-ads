#!/usr/bin/env python3
"""Phase 3 — reconciliation export the analyst can take to an auditor.

Reads the latest extraction run from gads.db and emits dated CSVs with
delivered-vs-contracted, CPM and underdelivery flags, computed at the CORRECT
grain (verified during Phase 0 / pre-report analysis):

  - impressionsDelivered : PER-ROW, additive            -> SUM
  - impressionsContracted: CONSTANT per line-item; values <= 1 are SENTINELS
        (line sold by period/daily, not by impression volume) -> excluded from
        delivery%; only line-items with contracted > 1 are reconciled.
  - investment_lineItem  : varies at a HIDDEN sub-grain  -> reported as MAX per
        line-item (best estimate of the line-item's spend). Naive row-sum ~9x's
        it; confirm intended aggregation with Globo. See NOTA METODOLOGICA.
  - video vtr / quartiles: field is an unexplained small-integer count, NOT a
        rate -> deliberately omitted (not defensible as VTR%).

Outputs: out/campaign_summary_<date>.csv, out/lineitem_detail_<date>.csv
Run: python3 report.py
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

DB = "gads.db"
OUT = Path("out")

NOTA = (
    "investment_lineItem varia num grão mais fino que os campos expostos pela API "
    "(o mesmo segmento oculto que divide impressionsDelivered); reportado aqui como o "
    "MAX por item de linha. Soma linha-a-linha = R$ 2.365.119,83. Confirmar a agregação "
    "de investimento pretendida com a Globo antes de publicar totais em R$. "
    "Contratado <= 1 é sentinela (item vendido por período/diária, não por impressão) e "
    "fica fora do cálculo de % de entrega. Métricas de vídeo (vtr) omitidas: campo é "
    "contagem inteira, não taxa."
)

LINEITEM_SQL = """
SELECT campaign, codCampaing, codLineItem, lineItem,
       SUM(impression_impressionsDelivered)  AS delivered,
       MAX(impression_impressionsContracted) AS contracted_raw,
       SUM(clicks)                           AS clicks,
       MAX(investment_lineItem)              AS investment
FROM digital_items WHERE run_id=?
GROUP BY campaign, codCampaing, codLineItem, lineItem
"""


def latest_run(con, endpoint):
    row = con.execute(
        "SELECT run_id, extracted_at FROM runs WHERE endpoint=? ORDER BY run_id DESC LIMIT 1",
        (endpoint,)).fetchone()
    if not row:
        raise SystemExit(f"no run for {endpoint} — run extract.py first")
    return row


def write_csv(path, meta, cols, rows):
    OUT.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for line in meta:
            w.writerow([line])
        w.writerow([])
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    run_id, extracted_at = latest_run(con, "/digital/items")
    tag = extracted_at[:10]
    meta = [
        "SECOM — Globo Ads Digital — Reconciliação de entrega vs. contratado",
        f"Fonte: /api/v1/digital/items | run_id={run_id} | extraido_em={extracted_at}",
        f"NOTA METODOLOGICA: {NOTA}",
    ]

    li = []
    for r in con.execute(LINEITEM_SQL, (run_id,)):
        d = (r["delivered"] or 0)
        craw = r["contracted_raw"] or 0
        contracted = craw if craw > 1 else ""        # sentinel -> blank
        inv = round(r["investment"] or 0, 2)
        li.append(dict(
            campaign=r["campaign"], codCampaing=r["codCampaing"],
            codLineItem=r["codLineItem"], lineItem=r["lineItem"],
            delivered=d, contracted=contracted, clicks=r["clicks"] or 0, investment=inv,
            cpm=round(inv / d * 1000, 2) if d else "",
            entrega_pct=round(d / craw * 100, 1) if craw > 1 else "",
            # flag off the displayed (rounded) %, so a line shown as 100.0% is never "SIM"
            subentrega="SIM" if craw > 1 and round(d / craw * 100, 1) < 100.0 else "",
        ))
    li_cols = ["campaign", "codCampaing", "codLineItem", "lineItem", "delivered",
               "contracted", "entrega_pct", "subentrega", "investment", "cpm", "clicks"]
    write_csv(OUT / f"lineitem_detail_{tag}.csv", meta, li_cols, li)

    camp = {}
    for r in li:
        c = camp.setdefault(r["campaign"], dict(
            campaign=r["campaign"], codCampaing=r["codCampaing"], line_items=0,
            delivered=0, contracted=0, deliv_on_contracted=0, investment=0.0, clicks=0))
        c["line_items"] += 1
        c["delivered"] += r["delivered"]
        c["investment"] += r["investment"]
        c["clicks"] += r["clicks"]
        if r["contracted"] != "":                     # only real-contracted lines
            c["contracted"] += r["contracted"]
            c["deliv_on_contracted"] += r["delivered"]
    crows = []
    for c in camp.values():
        c["investment"] = round(c["investment"], 2)
        c["cpm"] = round(c["investment"] / c["delivered"] * 1000, 2) if c["delivered"] else ""
        c["entrega_pct"] = (round(c["deliv_on_contracted"] / c["contracted"] * 100, 1)
                            if c["contracted"] else "")
        c["subentrega"] = ("SIM" if c["contracted"] and c["entrega_pct"] < 100.0 else "")
        c["contracted"] = c["contracted"] or ""
        crows.append(c)
    crows.sort(key=lambda x: x["investment"], reverse=True)
    camp_cols = ["campaign", "codCampaing", "line_items", "delivered", "contracted",
                 "entrega_pct", "subentrega", "investment", "cpm", "clicks"]
    write_csv(OUT / f"campaign_summary_{tag}.csv", meta, camp_cols, crows)

    td = sum(r["delivered"] for r in li)
    ti = sum(r["investment"] for r in li)
    flagged = [r for r in li if r["subentrega"] == "SIM"]
    reconciled = sum(1 for r in li if r["contracted"] != "")
    print(f"run {run_id} @ {extracted_at}")
    print(f"  campanhas                : {len(crows)}")
    print(f"  itens de linha           : {len(li)}  ({reconciled} com contratado real)")
    print(f"  impressões entregues     : {td:,.0f}")
    print(f"  investimento (max/item)  : R$ {ti:,.2f}   [ver NOTA METODOLOGICA]")
    print(f"  itens em subentrega      : {len(flagged)}")
    for r in flagged:
        print(f"     - {r['campaign'][:55]}  {r['entrega_pct']}%")
    print(f"  CSVs -> {OUT}/campaign_summary_{tag}.csv , lineitem_detail_{tag}.csv")


if __name__ == "__main__":
    main()
