"""
Exports everything the static site needs into site/data/*.json. The site is
pure static HTML/CSS/JS (GitHub Pages) -- no backend, nothing that can go
down during judging. Every number here comes from results/backtest.json or
directly from score_quarter_df, never typed by hand.

Outputs:
  site/data/search_index.json   - {cert, name} for every bank ever seen
  site/data/bank_<cert>.json    - full quarterly timeseries for one bank
  site/data/backtest.json       - copy of results/backtest.json (site reads it directly)
  site/data/today.json          - latest-quarter snapshot summary
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from pipeline.backtest import score_quarter_df, DATA_DIR, RESULTS_DIR

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data"
SITE_DATA.mkdir(parents=True, exist_ok=True)

ALL_QUARTERS = sorted(
    p.stem.replace("financials_", "")
    for p in DATA_DIR.glob("financials_*.parquet")
)

NAMED_FAILURES = {
    24735: {"faildate": "2023-03-10", "note": "Closed by regulators after a bank run."},
    57053: {"faildate": "2023-03-12", "note": "Closed after a liquidity-driven run."},
    59017: {"faildate": "2023-05-01", "note": "Seized and sold after a run following SVB/Signature."},
    27332: {"faildate": "2024-04-26", "note": "Failed after the theory behind this project was already published (Mar 2023) -- a true out-of-sample case."},
}


def _row_to_point(q: str, r: pd.Series) -> dict:
    return dict(
        repdte=q,
        name=r["name"],
        n_banks=int(r["n_banks"]),
        run_risk_score=None if pd.isna(r["run_risk_score"]) else round(float(r["run_risk_score"]), 4),
        rank_run_risk=None if pd.isna(r["rank_run_risk"]) else int(r["rank_run_risk"]),
        tier1_rbc=None if pd.isna(r["tier1_rbc"]) else round(float(r["tier1_rbc"]), 2),
        rank_tier1=None if pd.isna(r["rank_tier1"]) else int(r["rank_tier1"]),
        mtm_equity_ratio=None if pd.isna(r["mtm_equity_ratio"]) else round(float(r["mtm_equity_ratio"]), 4),
        uninsured_share=None if pd.isna(r["uninsured_share"]) else round(float(r["uninsured_share"]), 4),
        liquidity_cover=None if pd.isna(r["liquidity_cover"]) else round(float(r["liquidity_cover"]), 3),
        run_threshold_dollars_k=None if pd.isna(r["run_threshold_dollars"]) else round(float(r["run_threshold_dollars"]), 0),
        run_threshold_after_htm_k=None if pd.isna(r["run_threshold_after_htm"]) else round(float(r["run_threshold_after_htm"]), 0),
        asset_k=round(float(r["asset"]), 0),
    )


def build_all_bank_timeseries(certs: set[int]) -> dict[int, dict]:
    """Scores each quarter exactly once (score_quarter_df re-scores all
    ~4,700 banks per call, so doing this per-bank-per-quarter as originally
    written was O(banks x quarters) full rescans -- ~1,400 full-population
    scoring passes for 14 banks. This does 99 passes total, one per quarter,
    and pulls out every requested bank's row from each."""
    points_by_cert: dict[int, list[dict]] = {c: [] for c in certs}
    for i, q in enumerate(ALL_QUARTERS):
        df = score_quarter_df(q)
        if df.empty:
            continue
        for cert in certs:
            row = df[df["cert"] == cert]
            if row.empty:
                continue
            points_by_cert[cert].append(_row_to_point(q, row.iloc[0]))
        if (i + 1) % 20 == 0:
            print(f"  scored {i+1}/{len(ALL_QUARTERS)} quarters...")
    out = {}
    for cert, points in points_by_cert.items():
        if not points:
            out[cert] = None
            continue
        out[cert] = dict(cert=cert, name=points[-1]["name"], points=points, failure=NAMED_FAILURES.get(cert))
    return out


def build_search_index() -> list[dict]:
    seen = {}
    for q in ALL_QUARTERS[-8:]:  # last 2 years is enough for a name+cert search index
        df = score_quarter_df(q)
        for _, r in df.iterrows():
            seen[int(r["cert"])] = r["name"]
    for cert, info in NAMED_FAILURES.items():
        if cert not in seen:
            df = score_quarter_df("20220930")
            row = df[df["cert"] == cert]
            if not row.empty:
                seen[cert] = row.iloc[0]["name"]
    index = [{"cert": c, "name": n} for c, n in sorted(seen.items(), key=lambda kv: kv[1])]
    return index


def build_today() -> dict:
    latest = ALL_QUARTERS[-1]
    df = score_quarter_df(latest)
    n = len(df)
    reporters = df.dropna(subset=["run_risk_score"])
    top = reporters.nlargest(15, "run_risk_score")[
        ["cert", "name", "run_risk_score", "rank_run_risk", "tier1_rbc", "uninsured_share", "mtm_equity_ratio"]
    ]
    n_negative_mtm = int((df["mtm_equity_ratio"] < 0).sum())
    total_htm_loss_k = float(df["htm_loss"].sum())
    return dict(
        as_of=latest,
        n_banks=n,
        n_reporters=len(reporters),
        n_negative_mtm_equity=n_negative_mtm,
        total_htm_unrealized_loss_k=round(total_htm_loss_k, 0),
        top_15=json.loads(top.to_json(orient="records")),
    )


def main():
    print(f"Quarters available: {len(ALL_QUARTERS)} ({ALL_QUARTERS[0]}..{ALL_QUARTERS[-1]})")

    print("Building search index...")
    index = build_search_index()
    (SITE_DATA / "search_index.json").write_text(json.dumps(index))
    print(f"  {len(index)} banks")

    certs_to_export = set(NAMED_FAILURES.keys()) | {
        27330,  # Silvergate
        33497, 57450, 59108,  # Schwab entities
        2270,   # Zions
        983,    # Comerica
        5510,   # Frost Bank
        3510,   # Wells Fargo (large stable comparator)
        8758,   # Citizens Bank Sac City (classic-model catch)
        25851,  # Heartland Tri-State (fraud, honest limit)
        29730, 32633,  # IndyMac, WaMu (D2, 2008 era)
    }
    print(f"Building bank timeseries for {len(certs_to_export)} banks (scoring each quarter once)...")
    all_ts = build_all_bank_timeseries(certs_to_export)
    for cert, data in all_ts.items():
        if data is None:
            print(f"  {cert}: no data, skipped")
            continue
        (SITE_DATA / f"bank_{cert}.json").write_text(json.dumps(data))
        print(f"  {cert}: {data['name']} ({len(data['points'])} quarters)")

    print("Copying backtest results...")
    shutil.copy(RESULTS_DIR / "backtest.json", SITE_DATA / "backtest.json")

    d2_path = RESULTS_DIR / "d2_depth.json"
    if d2_path.exists():
        shutil.copy(d2_path, SITE_DATA / "d2_depth.json")

    print("Building today snapshot...")
    today = build_today()
    (SITE_DATA / "today.json").write_text(json.dumps(today, default=str))
    print(f"  as_of={today['as_of']} n_banks={today['n_banks']} negative_mtm={today['n_negative_mtm_equity']}")

    print("Done.")


if __name__ == "__main__":
    main()
