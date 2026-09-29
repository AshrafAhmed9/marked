"""
Tests for the frozen scoring formula and the backtest's core guards
(look-ahead, survivorship, branch filter). These are the tests that matter
for a rigor claim -- not coverage theater.

SVB 2022Q3 golden values are taken directly from the FDIC BankFind API
response captured during the kickoff spike (2026-09-27), in the API's
native units ($000s): SCHA=93,292,000 SCHF=77,367,000 EQ=15,129,000
ASSET=210,244,000 DEP=178,878,000 DEPUNA=155,263,000.
"""
import math
from pathlib import Path

import pandas as pd
import pytest

from pipeline.score import (
    BankQuarter,
    htm_unrealized_loss,
    liquidity_cover,
    mtm_equity,
    mtm_equity_ratio,
    run_risk_score,
    run_threshold_dollars,
    uninsured_share,
)

SVB_2022Q3 = BankQuarter(
    cert=24735, name="SILICON VALLEY BANK", repdte="20220930",
    asset=210_244_000, eq=15_129_000,
    scha=93_292_000, schf=77_367_000,
    depuna=155_263_000, dep=178_878_000,
    chbal=13_000_000, scaf=27_000_000,  # approximate, not asserted on
)


def test_htm_unrealized_loss_svb():
    # 93,292,000 - 77,367,000 = 15,925,000 ($000s) = $15.925B
    loss = htm_unrealized_loss(SVB_2022Q3)
    assert loss == pytest.approx(15_925_000, rel=1e-6)


def test_htm_loss_floored_at_zero_for_gain():
    bq = BankQuarter(cert=1, name="x", repdte="20220930", asset=100, eq=10,
                      scha=50, schf=55, depuna=None, dep=80)  # fair value > amortized cost = a gain
    assert htm_unrealized_loss(bq) == 0.0


def test_mtm_equity_svb_near_zero():
    # equity 15,129,000 minus HTM loss 15,925,000 = -796,000 ($000s), i.e.
    # slightly negative -- SVB's book equity almost exactly absorbed by its
    # own unbooked bond loss, five months before failure.
    eq = mtm_equity(SVB_2022Q3)
    assert eq == pytest.approx(15_129_000 - 15_925_000, rel=1e-6)
    assert eq < 0


def test_uninsured_share_svb():
    share = uninsured_share(SVB_2022Q3)
    assert share == pytest.approx(155_263_000 / 178_878_000, rel=1e-6)
    assert 0.85 < share < 0.90  # matches the widely reported ~87%


def test_uninsured_share_none_when_not_reported():
    bq = BankQuarter(cert=2, name="small bank", repdte="20220930",
                      asset=500_000, eq=50_000, scha=10_000, schf=10_000,
                      depuna=None, dep=400_000)
    assert uninsured_share(bq) is None
    assert run_risk_score(bq) is None  # must propagate None, never silently score as 0


def test_run_risk_score_is_large_and_positive_for_svb():
    score = run_risk_score(SVB_2022Q3)
    assert score is not None
    assert score > 0
    # mtm_equity_ratio is near zero/negative, so score should be very large
    # relative to a healthy bank
    healthy = BankQuarter(cert=3, name="healthy bank", repdte="20220930",
                           asset=1_000_000, eq=120_000, scha=100_000, schf=98_000,
                           depuna=400_000, dep=800_000)
    healthy_score = run_risk_score(healthy)
    assert score > healthy_score * 100


def test_run_threshold_none_without_uninsured_data():
    bq = BankQuarter(cert=4, name="x", repdte="20220930", asset=100, eq=10,
                      scha=5, schf=5, depuna=None, dep=80, chbal=5, scaf=5)
    assert run_threshold_dollars(bq) is None


def test_liquidity_cover_signature_below_one():
    # Signature Bank failed primarily on liquidity, not solvency: cash+AFS
    # was well short of uninsured deposits even though HTM losses were
    # comparatively small. Approximate 2022Q3 figures ($000s).
    sig = BankQuarter(cert=57053, name="SIGNATURE BANK", repdte="20220930",
                       asset=110_000_000, eq=8_000_000, scha=7_500_000, schf=6_900_000,
                       depuna=79_000_000, dep=88_000_000, chbal=6_000_000, scaf=7_700_000)
    cover = liquidity_cover(sig)
    assert cover is not None
    assert cover < 0.3  # nowhere near enough liquid assets to cover uninsured deposits


class TestLookaheadGuard:
    def test_quarter_not_usable_before_lag(self):
        from pipeline.backtest import usable_asof
        as_of = pd.Timestamp("2022-10-05")  # 5 days after quarter end
        assert not usable_asof("20220930", as_of)

    def test_quarter_usable_after_lag(self):
        from pipeline.backtest import usable_asof
        as_of = pd.Timestamp("2022-11-15")  # 46 days after quarter end
        assert usable_asof("20220930", as_of)

    def test_boundary_exactly_30_days(self):
        from pipeline.backtest import usable_asof
        as_of = pd.Timestamp("2022-09-30") + pd.Timedelta(days=30)
        assert usable_asof("20220930", as_of)


class TestBranchFilter:
    def test_zero_equity_branch_dropped(self):
        """Foreign-bank US branches often report EQ<=0 (they're not
        separately capitalized entities) -- the spike found these topping
        naive rankings before this filter was added. to_bank_quarters must
        drop them."""
        from pipeline.backtest import to_bank_quarters
        df = pd.DataFrame([{
            "CERT": 99999, "NAMEFULL": "FOREIGN BRANCH", "REPDTE": "20220930",
            "ASSET": 5_000_000, "EQ": 0.0, "SCHA": 0, "SCHF": 0,
            "DEPUNA": 1000, "DEP": 4_000_000, "CHBAL": 0, "SCAF": 0,
            "OTHBFHLB": 0, "IDT1RWAJR": None, "RBC1AAJ": None,
        }])
        result = to_bank_quarters(df)
        assert len(result) == 0

    def test_normal_bank_kept(self):
        from pipeline.backtest import to_bank_quarters
        df = pd.DataFrame([{
            "CERT": 1, "NAMEFULL": "NORMAL BANK", "REPDTE": "20220930",
            "ASSET": 5_000_000, "EQ": 500_000, "SCHA": 0, "SCHF": 0,
            "DEPUNA": 1000, "DEP": 4_000_000, "CHBAL": 0, "SCAF": 0,
            "OTHBFHLB": 0, "IDT1RWAJR": 12.0, "RBC1AAJ": 9.0,
        }])
        result = to_bank_quarters(df)
        assert len(result) == 1
