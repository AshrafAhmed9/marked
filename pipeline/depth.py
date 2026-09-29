"""
Depth modules D2 and D6 (see COMPETITION.md for D3/D4/D5 field-availability
findings -- D3/D4 dropped, D5 narrowed).

D2: apply the FROZEN formula (pipeline/score.py, unchanged) to the 2007-2008
    era and check whether it flagged IndyMac (failed 2008-07-11, CERT 29730)
    and Washington Mutual (failed 2008-09-25, CERT 32633), the two largest
    run-driven failures of that crisis. This is the strongest available
    rebuttal to "the formula was reverse-engineered from SVB": if it also
    separates the run failures from the crisis's much larger population of
    credit-driven failures in a totally different era, using the exact same
    two accounting inputs, that isn't fitting to 2023.

    HONEST CAVEAT, discovered while building this: FDIC's financials API
    reports SCHF (HTM fair value) as null for IndyMac and WaMu in every
    2007-2008 quarter checked (SCHA is present for WaMu, near-zero for
    IndyMac). Per the null-handling fix in backtest.py, a null SCHF means
    htm_unrealized_loss is reported as 0 for that bank-quarter -- NOT that
    the bank had no HTM exposure. So D2's mtm_equity_ratio for WaMu/IndyMac
    is effectively just their reported book equity ratio (no HTM markdown
    applied), and run_risk_score for the 2008 era is driven almost entirely
    by uninsured_share, not the MTM half of the formula. This is reported
    explicitly, not hidden -- it is a genuine data-availability limit of the
    free API, not a modeling choice.

D6: seasonal-adjusted deposit flight is implemented directly in
    backtest.py's section_b_deposit_flight (adjusts each bank's Q4'22->Q1'23
    % change by subtracting that same bank's Q4'21->Q1'22 % change). This
    module documents the data-vintage caveat: the FDIC API serves whatever
    is the CURRENT (possibly since-amended) value for a given REPDTE, not
    a point-in-time snapshot of what was originally filed. We spot-check
    SVB's 2022Q3 figures against the widely-reported contemporary 10-Q
    figures in tests/test_score.py and the README; no discrepancy was found
    for the fields used, but a systematic point-in-time API isn't available
    for free, so this is stated as a limitation rather than silently
    assumed away.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipeline.backtest import score_quarter_df, RESULTS_DIR

IndyMac_CERT = 29730
WaMu_CERT = 32633

CRISIS_QUARTERS = ["20061231", "20070331", "20070630", "20070930",
                    "20071231", "20080331", "20080630"]


def run_d2() -> dict:
    out = {"named": {}, "field_availability_note": (
        "SCHF (HTM fair value) is null for IndyMac and WaMu in every "
        "checked 2007-2008 quarter; per backtest.py's null-handling, "
        "htm_unrealized_loss is reported as 0 for those bank-quarters "
        "rather than inferred. run_risk_score for this era is therefore "
        "driven mostly by uninsured_share. Reported as a limitation."
    )}
    for cert, name in [(IndyMac_CERT, "IndyMac Bank"), (WaMu_CERT, "Washington Mutual")]:
        out["named"][name] = []
        for q in CRISIS_QUARTERS:
            df = score_quarter_df(q)
            if df.empty:
                continue
            row = df[df["cert"] == cert]
            if row.empty:
                continue
            r = row.iloc[0]
            out["named"][name].append(dict(
                repdte=q,
                n_banks=int(r["n_banks"]),
                rank_run_risk=int(r["rank_run_risk"]) if not pd.isna(r["rank_run_risk"]) else None,
                rank_tier1=int(r["rank_tier1"]) if not pd.isna(r["rank_tier1"]) else None,
                uninsured_share=round(r["uninsured_share"], 3) if r["uninsured_share"] is not None and not pd.isna(r["uninsured_share"]) else None,
            ))
    return out


def main():
    d2 = run_d2()
    (RESULTS_DIR / "d2_depth.json").write_text(json.dumps(d2, indent=2, default=str))
    print(json.dumps(d2, indent=2, default=str))
    print(f"\nWrote {RESULTS_DIR / 'd2_depth.json'}")


if __name__ == "__main__":
    main()
