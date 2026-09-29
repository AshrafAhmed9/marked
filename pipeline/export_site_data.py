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


def build_all_bank_timeseries(
    full_history_certs: set[int],
    light_certs: set[int],
    light_quarters: int = 12,
) -> dict[int, dict]:
    """Scores each quarter exactly once and pulls every requested bank's row
    out via an O(1) dict lookup (not a per-cert boolean mask, which would be
    O(banks_requested x rows_in_quarter) per quarter -- at ~4,500 requested
    banks x 4,700 rows x 102 quarters that's >2 billion comparisons and was
    the actual bottleneck the first time this ran with only 16 banks).

    full_history_certs get every quarter available (named failures + the
    hand-picked comparators discussed in the README). light_certs (the rest
    of the ~4,500 banks in the search index) get only the last
    `light_quarters` -- enough to show a real recent trend on the site
    without exporting ~100 quarters x 4,500 banks of JSON."""
    all_certs = full_history_certs | light_certs
    points_by_cert: dict[int, list[dict]] = {c: [] for c in all_certs}
    n = len(ALL_QUARTERS)
    for i, q in enumerate(ALL_QUARTERS):
        is_light_window = i >= n - light_quarters
        wanted = all_certs if is_light_window else full_history_certs
        if not wanted:
            continue
        df = score_quarter_df(q)
        if df.empty:
            continue
        # build the O(1) lookup once per quarter, not once per requested bank
        by_cert = df.set_index("cert")
        for cert in wanted:
            if cert not in by_cert.index:
                continue
            row = by_cert.loc[cert]
            if isinstance(row, pd.DataFrame):  # duplicate cert guard, shouldn't happen but don't crash
                row = row.iloc[0]
            points_by_cert[cert].append(_row_to_point(q, row))
        if (i + 1) % 20 == 0:
            print(f"  scored {i+1}/{n} quarters ({len(wanted)} banks this quarter)...")
    out = {}
    for cert, points in points_by_cert.items():
        if not points:
            out[cert] = None
            continue
        out[cert] = dict(cert=cert, name=points[-1]["name"], points=points, failure=NAMED_FAILURES.get(cert))
    return out


def build_search_index(must_include: set[int] = frozenset()) -> list[dict]:
    """Every currently-operating bank (from the last 8 quarters) plus every
    cert in `must_include` (named failures and comparators, several of which
    stopped filing years before the last-8-quarters window -- SVB's last
    filing is 2022Q4, well outside any recent window) get a search index
    entry, so every bank with a full detail page is actually findable."""
    seen = {}
    for q in ALL_QUARTERS[-8:]:  # last 2 years is enough for a name+cert search index
        df = score_quarter_df(q)
        for _, r in df.iterrows():
            seen[int(r["cert"])] = r["name"]

    missing = set(must_include) - set(seen.keys())
    if missing:
        # walk backwards from the most recent quarter until each missing
        # cert's last known filing is found, instead of assuming one fixed
        # quarter works for every bank (they failed on different dates)
        for q in reversed(ALL_QUARTERS):
            if not missing:
                break
            df = score_quarter_df(q)
            if df.empty:
                continue
            by_cert = df.set_index("cert")
            found = missing & set(by_cert.index)
            for cert in found:
                seen[cert] = by_cert.loc[cert, "name"]
            missing -= found

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

    full_history_certs = set(NAMED_FAILURES.keys()) | {
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

    print("Building search index...")
    index = build_search_index(must_include=full_history_certs)
    (SITE_DATA / "search_index.json").write_text(json.dumps(index, separators=(",", ":")))
    print(f"  {len(index)} banks")

    # every other bank in the search index gets a light (last-3-years)
    # detail page instead of "no data exported" -- the search box promises
    # "search any of ~4,700 US banks" and up to this point only 16 of them
    # actually had a page behind that promise.
    light_certs = {row["cert"] for row in index} - full_history_certs
    print(f"Building bank timeseries: {len(full_history_certs)} full-history + "
          f"{len(light_certs)} light (last 12 quarters) = {len(full_history_certs) + len(light_certs)} banks total...")
    all_ts = build_all_bank_timeseries(full_history_certs, light_certs)
    written, skipped = 0, 0
    for cert, data in all_ts.items():
        if data is None:
            skipped += 1
            continue
        (SITE_DATA / f"bank_{cert}.json").write_text(json.dumps(data, separators=(",", ":")))
        written += 1
    print(f"  wrote {written} bank files, skipped {skipped} with no data")
    for cert in full_history_certs:
        d = all_ts.get(cert)
        if d:
            print(f"    {cert}: {d['name']} ({len(d['points'])} quarters, full history)")

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
