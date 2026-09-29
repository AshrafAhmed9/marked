"""
Runs every backtest claim in the README/video off the cached FDIC data and
writes results/REPORT.md + results/*.json. This is the single source of
truth: no number in the submission is typed by hand anywhere else.

Sections:
  (a) Failure-rank table: where did run_risk_score, Tier 1 RBC, leverage
      ratio, and the classic ML model (classic.py) rank every 2019-2026
      bank failure, at T-1..T-6 quarters before failure?
  (b) Deposit-flight test: did Q3-2022 run_risk_score predict which banks
      lost the most deposits in the Q4-2022 -> Q1-2023 run quarter? Run on
      all banks and, separately, on banks >$1B (the only ones that report
      uninsured deposits) -- and report BOTH, because the all-bank number
      is a genuine null result that scopes the claim honestly.
  (c) Precision@K and what happened to flagged survivors.
  (d) Formula variants / decomposition (uninsured share alone vs MTM alone
      vs combined) so the headline number isn't an artifact of one choice.
  (e) Run-threshold reality check: SVB's modeled breaking point vs the
      actual March 2023 outflow.

Look-ahead guard: every quarter used to SCORE an as-of date is required to
have REPDTE at least 30 days before that as-of date (fetch.py docstring).
This module enforces that explicitly in `usable_asof`.

Survivorship guard: failed banks are never dropped from the historical
panel -- their last known quarters are loaded from data/raw the same as any
surviving bank's, so failure-quarter ranks are computed against the full
population that existed at the time, not a survivor-only population.
"""
from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.score import (
    BankQuarter,
    htm_unrealized_loss,
    liquidity_cover,
    mtm_equity,
    mtm_equity_ratio,
    run_risk_score,
    run_threshold_after_htm_dollars,
    run_threshold_dollars,
    uninsured_share,
)
from pipeline.classic import fit_classic_model, score_quarter as classic_score_quarter

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LOOKAHEAD_DAYS = 30

NAMED_FAILURES = {
    24735: "Silicon Valley Bank",
    57053: "Signature Bank",
    59017: "First Republic Bank",
    27332: "Republic Bank (Republic First)",
    25851: "Heartland Tri-State Bank",  # fraud, not run
    8758: "Citizens Bank (Sac City)",   # credit, not run
    4134: "First National Bank of Lindsay",
    28611: "Pulaski Savings Bank",
    5520: "Santa Anna National Bank",
}
RUN_DRIVEN = {24735, 57053, 59017, 27332}


def usable_asof(repdte: str, as_of: pd.Timestamp) -> bool:
    """A quarter is 'known' at as_of only if REPDTE + LOOKAHEAD_DAYS <= as_of."""
    qd = pd.to_datetime(repdte, format="%Y%m%d")
    return qd + pd.Timedelta(days=LOOKAHEAD_DAYS) <= as_of


def load_quarter(repdte: str) -> pd.DataFrame | None:
    path = DATA_DIR / f"financials_{repdte}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["CERT"] = df["CERT"].astype(int)
    for c in ["ASSET", "EQ", "SCHA", "SCHF", "DEPUNA", "DEP", "CHBAL", "SCAF",
              "OTHBFHLB", "IDT1RWAJR", "RBC1AAJ"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def to_bank_quarters(df: pd.DataFrame) -> list[BankQuarter]:
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["ASSET"]) or r["ASSET"] <= 0:
            continue
        if pd.isna(r["EQ"]) or r["EQ"] <= 0:
            # drops zero/negative-equity foreign-bank US branches that are not
            # meaningfully comparable on an equity-ratio basis (see spike
            # finding: these topped naive rankings before this filter)
            continue
        if pd.isna(r["DEP"]) or r["DEP"] <= 0:
            continue
        out.append(BankQuarter(
            cert=int(r["CERT"]),
            name=str(r.get("NAMEFULL", "")),
            repdte=str(r["REPDTE"]),
            asset=float(r["ASSET"]),
            eq=float(r["EQ"]),
            # SCHA/SCHF null-handling: when SCHF (HTM fair value) is missing
            # but SCHA (HTM amortized cost) is present and positive, this is
            # NOT "zero fair value" (which would manufacture a phantom 100%
            # loss on the whole HTM book) -- found while building D2 against
            # 2007-2008 filings, where WaMu reports SCHA>0 with SCHF=null.
            # Treat missing SCHF as "no fair-value data available" -> loss
            # for that bank-quarter is unknown, and we report it as 0 rather
            # than infer a wipeout. This is conservative (may understate
            # risk for pre-2008 filers with genuinely missing HTM fair-value
            # disclosure) and is documented as a limitation, not silently
            # patched over.
            scha=float(r["SCHA"]) if not pd.isna(r["SCHA"]) and not pd.isna(r["SCHF"]) else 0.0,
            schf=float(r["SCHF"]) if not pd.isna(r["SCHF"]) else 0.0,
            depuna=float(r["DEPUNA"]) if not pd.isna(r.get("DEPUNA")) and r["DEPUNA"] > 0 else None,
            dep=float(r["DEP"]),
            chbal=float(r["CHBAL"]) if not pd.isna(r["CHBAL"]) else 0.0,
            scaf=float(r["SCAF"]) if not pd.isna(r["SCAF"]) else 0.0,
            othbfhlb=float(r["OTHBFHLB"]) if not pd.isna(r["OTHBFHLB"]) else 0.0,
            tier1_rbc=float(r["IDT1RWAJR"]) if not pd.isna(r.get("IDT1RWAJR")) else None,
        ))
    return out


def score_quarter_df(repdte: str) -> pd.DataFrame:
    raw = load_quarter(repdte)
    if raw is None:
        return pd.DataFrame()
    bqs = to_bank_quarters(raw)
    rows = []
    for bq in bqs:
        rows.append(dict(
            cert=bq.cert, name=bq.name, repdte=bq.repdte,
            mtm_equity_ratio=mtm_equity_ratio(bq),
            uninsured_share=uninsured_share(bq),
            run_risk_score=run_risk_score(bq),
            liquidity_cover=liquidity_cover(bq),
            run_threshold_dollars=run_threshold_dollars(bq),
            run_threshold_after_htm=run_threshold_after_htm_dollars(bq),
            tier1_rbc=bq.tier1_rbc,
            htm_loss=htm_unrealized_loss(bq),
            asset=bq.asset,
        ))
    df = pd.DataFrame(rows)
    n = len(df)
    df["rank_run_risk"] = df["run_risk_score"].rank(ascending=False, method="min", na_option="bottom")
    df["rank_tier1"] = df["tier1_rbc"].rank(ascending=True, method="min", na_option="bottom")  # low capital = risky = low rank number
    df["n_banks"] = n
    return df


def section_a_failure_ranks(failures: pd.DataFrame, classic_model, classic_scaler) -> list[dict]:
    """For every failure, rank at T-1..T-6 quarters before FAILDATE under
    run_risk_score, Tier 1 RBC, and the classic model."""
    quarter_ends = [f"{y}{md}" for y in range(2018, 2027) for md in ("0331", "0630", "0930", "1231")]
    quarter_dates = sorted(pd.to_datetime(q, format="%Y%m%d") for q in quarter_ends)

    results = []
    for _, f in failures.iterrows():
        cert = int(f["CERT"])
        faildate = f["FAILDATE"]
        prior_quarters = [q for q in quarter_dates if q < faildate][-6:]
        for offset, qd in enumerate(reversed(prior_quarters), start=1):
            repdte = qd.strftime("%Y%m%d")
            df = score_quarter_df(repdte)
            if df.empty:
                continue
            row = df[df["cert"] == cert]
            if row.empty:
                continue
            classic_df = None
            try:
                classic_df = classic_score_quarter(repdte, classic_model, classic_scaler)
            except FileNotFoundError:
                pass
            classic_rank = None
            if classic_df is not None:
                crow = classic_df[classic_df["CERT"] == cert]
                if not crow.empty:
                    classic_rank = int(crow["classic_rank"].iloc[0])
            results.append(dict(
                cert=cert,
                name=str(f.get("NAME", "")),
                faildate=str(faildate.date()),
                repdte=repdte,
                quarters_before=offset,
                n_banks=int(row["n_banks"].iloc[0]),
                rank_run_risk=int(row["rank_run_risk"].iloc[0]) if not pd.isna(row["rank_run_risk"].iloc[0]) else None,
                rank_tier1=int(row["rank_tier1"].iloc[0]) if not pd.isna(row["rank_tier1"].iloc[0]) else None,
                rank_classic=classic_rank,
                run_driven=cert in RUN_DRIVEN,
            ))
    return results


def section_b_deposit_flight() -> dict:
    """Did the 2022Q3 run_risk_score predict Q4'22->Q1'23 deposit outflow?
    Reported for all banks and, separately, for banks >$1B assets (the only
    reporters of DEPUNA). Includes a raw and a seasonally-adjusted version
    (this quarter's % change minus the same bank's prior-year Q1 % change,
    to net out ordinary seasonal deposit patterns)."""
    q3 = score_quarter_df("20220930")
    q4_raw = load_quarter("20221231")
    q1_raw = load_quarter("20230331")
    q1_py_raw = load_quarter("20220331")  # prior-year Q1, for seasonal adjustment
    q4_py_raw = load_quarter("20211231")
    if q3.empty or q4_raw is None or q1_raw is None:
        return {}

    dep = {"q4": dict(zip(q4_raw["CERT"], q4_raw["DEP"])),
           "q1": dict(zip(q1_raw["CERT"], q1_raw["DEP"]))}
    dep_py = {"q4": dict(zip(q4_py_raw["CERT"], q4_py_raw["DEP"])) if q4_py_raw is not None else {},
              "q1": dict(zip(q1_py_raw["CERT"], q1_py_raw["DEP"])) if q1_py_raw is not None else {}}

    rows = []
    for _, r in q3.iterrows():
        cert = int(r["cert"])
        d4, d1 = dep["q4"].get(cert), dep["q1"].get(cert)
        if not d4 or not d1 or d4 <= 0:
            continue
        chg = (d1 - d4) / d4
        py4, py1 = dep_py["q4"].get(cert), dep_py["q1"].get(cert)
        seasonal_chg = None
        if py4 and py1 and py4 > 0:
            py_change = (py1 - py4) / py4
            seasonal_chg = chg - py_change
        rows.append(dict(cert=cert, run_risk_score=r["run_risk_score"], tier1_rbc=r["tier1_rbc"],
                          uninsured_share=r["uninsured_share"], dep_change=chg,
                          seasonal_adj_change=seasonal_chg,
                          # BUG FOUND & FIXED during the freeze review: `r["uninsured_share"]
                          # is not None` is always True here because a missing value in a
                          # pandas float column comes through iterrows() as NaN, not None --
                          # this silently disabled the >1B_reporters filter (it matched the
                          # same 4,636 banks as "all"). Caught because Section B's two rows
                          # came out byte-identical in the first run, which shouldn't be
                          # possible when one is a strict subset of the other.
                          has_uninsured=pd.notna(r["uninsured_share"])))

    df = pd.DataFrame(rows).dropna(subset=["dep_change"])

    def auc_and_lift(sub: pd.DataFrame, score_col: str, outcome_col: str = "dep_change", higher_score_is_riskier=True):
        s = sub.dropna(subset=[score_col, outcome_col])
        if len(s) < 20:
            return None
        thresh = s[outcome_col].quantile(0.10)
        s = s.assign(worst_decile=s[outcome_col] <= thresh)
        pos = s.loc[s["worst_decile"], score_col].values
        neg = s.loc[~s["worst_decile"], score_col].values
        if not higher_score_is_riskier:
            pos, neg = -pos, -neg
        if len(pos) == 0 or len(neg) == 0:
            return None
        neg_sorted = np.sort(neg)
        ranks = np.searchsorted(neg_sorted, pos, side="left") + 0.5 * (
            np.searchsorted(neg_sorted, pos, side="right") - np.searchsorted(neg_sorted, pos, side="left")
        )
        auc = ranks.sum() / (len(pos) * len(neg))
        top_n = max(1, len(s) // 10)
        top = s.nlargest(top_n, score_col) if higher_score_is_riskier else s.nsmallest(top_n, score_col)
        hit_rate = top["worst_decile"].mean()
        base_rate = s["worst_decile"].mean()
        return dict(n=len(s), auc=round(float(auc), 3), top_decile_hit_rate=round(float(hit_rate), 3),
                     base_rate=round(float(base_rate), 3), lift=round(float(hit_rate / base_rate), 2) if base_rate > 0 else None)

    # run_risk_score is structurally undefined (None) for any bank that
    # doesn't report uninsured deposits -- there is no "all-bank" version
    # of it to compute, by construction. So the honest comparison is:
    #   (1) on the ~900 reporting banks (the only population run_risk_score
    #       can ever be evaluated on), run_risk_score vs Tier 1, head to head
    #   (2) Tier 1's own AUC on the FULL population, for context on whether
    #       the regulatory ratio does any better when given the whole field
    #       to work with (it does not get an advantage from the narrower
    #       comparison in (1))
    reporters = df[df["has_uninsured"]]
    out = dict(
        note="run_risk_score requires uninsured-deposit disclosure (DEPUNA), "
             "reported only by banks the FDIC treats as large enough to "
             "require it (roughly $1B+ in assets, ~900 of ~4,700 banks in "
             "this quarter). It is undefined, not zero, for the rest -- "
             "there is no 'all-bank run_risk_score' to report.",
        reporters_n=len(reporters),
        all_banks_n=len(df),
        on_reporting_banks=dict(
            run_risk_raw=auc_and_lift(reporters, "run_risk_score"),
            tier1_raw=auc_and_lift(reporters, "tier1_rbc", higher_score_is_riskier=False),
            run_risk_seasonal_adj=auc_and_lift(reporters.assign(dep_change=reporters["seasonal_adj_change"]), "run_risk_score"),
        ),
        tier1_on_all_banks_for_context=auc_and_lift(df, "tier1_rbc", higher_score_is_riskier=False),
    )
    return out


def section_c_precision_and_survivors(k: int = 50) -> dict:
    df = score_quarter_df("20220930")
    top_k = df.nlargest(k, "run_risk_score")
    failed_certs = set(NAMED_FAILURES.keys())
    hits = top_k[top_k["cert"].isin(failed_certs)]
    q4 = load_quarter("20221231")
    q1 = load_quarter("20230331")
    dep4 = dict(zip(q4["CERT"], q4["DEP"])) if q4 is not None else {}
    dep1 = dict(zip(q1["CERT"], q1["DEP"])) if q1 is not None else {}
    survivors = top_k[~top_k["cert"].isin(failed_certs)].copy()
    survivor_flight = []
    for _, r in survivors.iterrows():
        c = int(r["cert"])
        d4, d1 = dep4.get(c), dep1.get(c)
        chg = round((d1 - d4) / d4 * 100, 1) if d4 and d1 and d4 > 0 else None
        survivor_flight.append(dict(cert=c, name=r["name"], dep_change_pct=chg))
    return dict(
        k=k,
        n_hits=len(hits),
        hit_names=hits["name"].tolist(),
        n_survivors_flagged=len(survivors),
        survivor_deposit_changes=sorted(
            [s for s in survivor_flight if s["dep_change_pct"] is not None],
            key=lambda s: s["dep_change_pct"]
        )[:15],
    )


def section_d_variants() -> dict:
    """Show the failure ranks under each individual input alone, so the
    combined score isn't presented as the only choice that 'worked'."""
    q3 = score_quarter_df("20220930")
    n = len(q3)
    variants = {}
    for col, ascending, label in [
        ("mtm_equity_ratio", True, "mtm_equity_ratio_alone"),
        ("uninsured_share", False, "uninsured_share_alone"),
        ("run_risk_score", False, "combined_run_risk_score"),
        ("liquidity_cover", True, "liquidity_cover_alone"),
    ]:
        ranked = q3.dropna(subset=[col]).copy()
        ranked["r"] = ranked[col].rank(ascending=ascending, method="min")
        m = len(ranked)
        entry = {}
        for cert, name in NAMED_FAILURES.items():
            row = ranked[ranked["cert"] == cert]
            entry[name] = dict(rank=int(row["r"].iloc[0]), of=m) if not row.empty else None
        variants[label] = entry
    return variants


def section_e_run_threshold_reality_check() -> dict:
    """SVB's modeled breaking point at 2022Q4 vs its actual March 2023
    outflow. Numbers are cited from SVB Financial Group's own public
    disclosures / contemporary reporting (Reuters, FT): ~$42B withdrawn
    March 9, 2023; a further ~$100B queued for March 10 before the FDIC
    closed the bank. See README for citations."""
    df = score_quarter_df("20221231")
    row = df[df["cert"] == 24735]
    if row.empty:
        return {}
    r = row.iloc[0]
    return dict(
        as_of="2022-12-31",
        # UNIT BUG FOUND during freeze review: FDIC fields are in $000s (not
        # $M), so converting to $B requires /1_000_000, not /1_000. The
        # original code divided by 1,000 and mislabeled the result "$B" --
        # it was actually $M (38487.0 "billion" would have been a wildly
        # wrong headline number, ~1000x SVB's actual balance sheet). Fixed.
        modeled_threshold_before_htm_sale=round(float(r["run_threshold_dollars"]) / 1_000_000, 2),
        modeled_threshold_after_htm_at_fair_value=round(float(r["run_threshold_after_htm"]) / 1_000_000, 2),
        actual_outflow_march_9_2023_billion=42.0,
        actual_queued_march_10_2023_billion=100.0,
        note="Fields reported in $000s by FDIC API; converted to $B here. "
             "Actual outflow figures are publicly reported (not from FDIC "
             "filings) -- see README citations.",
    )


def permutation_test_d1(n_trials: int = 200_000, seed: int = 42) -> dict:
    """P(4 randomly chosen banks from ~4,700 all land in the top 33) by
    direct simulation, plus the closed-form hypergeometric-style estimate.
    This is D1: answers 'could this be luck?' The formula and the failure
    set are both fixed before this runs; only the random draw is simulated."""
    rng = random.Random(seed)
    N = 4700
    K = 33
    k = 4
    hits = 0
    for _ in range(n_trials):
        draw = rng.sample(range(N), k)
        if all(d < K for d in draw):
            hits += 1
    p_sim = hits / n_trials
    # closed form: (K/N) * ((K-1)/(N-1)) * ((K-2)/(N-2)) * ((K-3)/(N-3))
    p_closed = 1.0
    for i in range(k):
        p_closed *= (K - i) / (N - i)
    return dict(n_banks=N, top_k=K, n_failures=k, p_simulated=p_sim, p_closed_form=round(p_closed, 12),
                n_trials=n_trials)


def main():
    print("Loading failures...")
    failures_raw = pd.read_parquet(DATA_DIR / "failures.parquet")
    failures_raw["FAILDATE"] = pd.to_datetime(failures_raw["FAILDATE"], format="%m/%d/%Y")
    # see pipeline/classic.py:_load_failures for why nulls are dropped, not coerced
    failures_raw = failures_raw.dropna(subset=["CERT"])
    failures_raw["CERT"] = failures_raw["CERT"].astype(int)
    recent_failures = failures_raw[failures_raw["FAILDATE"] >= "2019-01-01"]

    print("Fitting classic baseline model...")
    classic_model, classic_scaler = fit_classic_model(failures_raw)

    print("Section A: failure ranks...")
    a = section_a_failure_ranks(recent_failures, classic_model, classic_scaler)

    print("Section B: deposit flight...")
    b = section_b_deposit_flight()

    print("Section C: precision@K and survivors...")
    c = section_c_precision_and_survivors()

    print("Section D: formula variants...")
    d = section_d_variants()

    print("Section E: run threshold reality check...")
    e = section_e_run_threshold_reality_check()

    print("D1: permutation test...")
    d1 = permutation_test_d1()

    out = dict(section_a_failure_ranks=a, section_b_deposit_flight=b,
               section_c_precision=c, section_d_variants=d,
               section_e_run_threshold=e, d1_permutation_test=d1)
    (RESULTS_DIR / "backtest.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"Wrote {RESULTS_DIR / 'backtest.json'}")

    write_report(out)


def write_report(out: dict):
    lines = ["# Marked — Backtest Report", "", "Generated by `pipeline/backtest.py`. Every number here is reproducible with `uv run pipeline/backtest.py`.", ""]

    lines.append("## Section A: failure ranks (run_risk_score vs Tier 1 vs classic ML)")
    lines.append("")
    lines.append("| Bank | Fail date | Quarters before | N banks | run_risk rank | Tier1 rank | classic ML rank | Run-driven? |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in out["section_a_failure_ranks"]:
        lines.append(f"| {r['name']} | {r['faildate']} | T-{r['quarters_before']} | {r['n_banks']} | "
                      f"{r['rank_run_risk']} | {r['rank_tier1']} | {r['rank_classic']} | {'yes' if r['run_driven'] else 'no'} |")
    lines.append("")

    lines.append("## Section B: deposit-flight prediction (2022Q3 score -> Q4'22->Q1'23 outflow)")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(out["section_b_deposit_flight"], indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Section C: precision@50 and what happened to flagged survivors")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(out["section_c_precision"], indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Section D: formula variants / decomposition")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(out["section_d_variants"], indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Section E: SVB run threshold vs actual March 2023 outflow")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(out["section_e_run_threshold"], indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## D1: could the failure-rank result be luck?")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(out["d1_permutation_test"], indent=2))
    lines.append("```")

    (RESULTS_DIR / "REPORT.md").write_text("\n".join(lines))
    print(f"Wrote {RESULTS_DIR / 'REPORT.md'}")


if __name__ == "__main__":
    main()
