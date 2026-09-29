"""
Marked: bank run-risk scoring formula.

FROZEN before the full historical backtest was run (see git log — this file's
first commit predates results/REPORT.md). Two accounting inputs, no fitted
weights, no knowledge of which banks failed baked into the coefficients. This
is the anti-hindsight guard: the formula does not change after we see how it
scores history.

Definitions (FDIC Call Report / UBPR field codes):
  ASSET   total assets
  EQ      total equity capital
  SCHA    held-to-maturity securities, amortized cost
  SCHF    held-to-maturity securities, fair value
  DEPUNA  uninsured deposits (only reported by banks with >$1B in assets or
          that file the UBPR uninsured-deposit estimate; smaller banks report
          null/blank)
  DEP     total deposits
  CHBAL   cash and due from banks
  SCAF    available-for-sale securities, fair value
  OTHBFHLB FHLB advances already drawn

All fields must come from a filing whose REPDTE is at least 30 days old
relative to the "as-of" date being scored (see fetch.py / look-ahead guard) —
Call Reports are not public the day the quarter ends.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BankQuarter:
    cert: int
    name: str
    repdte: str  # YYYYMMDD
    asset: float
    eq: float
    scha: float  # HTM amortized cost
    schf: float  # HTM fair value
    depuna: float | None  # uninsured deposits, None if not reported
    dep: float
    chbal: float = 0.0
    scaf: float = 0.0  # AFS fair value
    othbfhlb: float = 0.0
    tier1_rbc: float | None = None  # regulatory ratio, for comparison only


def htm_unrealized_loss(bq: BankQuarter) -> float:
    """Unbooked loss on held-to-maturity bonds. Floored at 0 (a gain isn't a
    risk). This is the number that never appears in the regulatory capital
    ratio — HTM securities are carried at amortized cost, not fair value,
    which is precisely the accounting gap SVB's failure exposed."""
    return max(bq.scha - bq.schf, 0.0)


def mtm_equity(bq: BankQuarter) -> float:
    """Equity if HTM losses were recognized today. This is NOT how banks
    report capital, and NOT how call-report equity (EQ) is computed — EQ
    already reflects AOCI for AFS securities but never touches HTM. That gap
    is the entire finding."""
    return bq.eq - htm_unrealized_loss(bq)


def mtm_equity_ratio(bq: BankQuarter) -> float:
    """Marked-to-market equity as a share of total assets. Negative means the
    bank is balance-sheet insolvent the moment HTM losses are realized."""
    if bq.asset <= 0:
        return 0.0
    return mtm_equity(bq) / bq.asset


def uninsured_share(bq: BankQuarter) -> float | None:
    """Share of deposits that are uninsured (>$250k, not covered by FDIC
    insurance). None if the bank does not report DEPUNA (typically <$1B
    assets) — this must be surfaced as "not reported", never treated as 0."""
    if bq.depuna is None or bq.dep <= 0:
        return None
    return bq.depuna / bq.dep


def run_risk_score(bq: BankQuarter) -> float | None:
    """
    Core score = uninsured_share / max(mtm_equity_ratio, epsilon).

    Interpretation: how much uninsured-deposit exposure exists per unit of
    true (mark-to-market) loss-absorbing capital. High uninsured share alone
    is not dangerous if the bank has capital to burn (see Signature, Schwab
    Bank). Low MTM equity alone is not dangerous if deposits are insured and
    sticky. The combination — large uninsured base sitting on capital that
    is not actually there — is the SVB pattern.

    epsilon = 0.001 (of assets) prevents division blow-up when mtm_equity is
    at or near zero; it is not tuned to any failure.

    Returns None if uninsured_share is not reported (small bank).
    """
    u = uninsured_share(bq)
    if u is None:
        return None
    eps = 0.001
    denom = max(mtm_equity_ratio(bq), eps)
    return u / denom


def liquidity_cover(bq: BankQuarter) -> float | None:
    """(cash + AFS fair value) / uninsured deposits. >1 means the bank could
    plausibly pay every uninsured depositor without touching HTM bonds at
    all. This is the "can it survive a run without becoming insolvent"
    lens — distinct from run_risk_score, which asks "is it already
    insolvent on a marked basis." Signature Bank failed primarily on this
    axis with comparatively small HTM losses."""
    if bq.depuna is None or bq.depuna <= 0:
        return None
    liquid = bq.chbal + bq.scaf
    return liquid / bq.depuna


def run_threshold_dollars(bq: BankQuarter) -> float | None:
    """Dollar amount of uninsured-deposit withdrawal the bank can absorb
    using cash + AFS securities before it must start selling HTM bonds,
    which crystallizes the unrealized loss against equity. This is the
    "breaking point" shown on the site's run slider.

    Simplified funding order: cash and due from banks first, then AFS
    securities at fair value, then HTM securities at fair value (triggering
    the loss). FHLB borrowing capacity is a separate, larger threshold
    (D5, not included in this base number — the two are shown separately
    so the base claim isn't inflated by a capacity that must itself be
    approved and can be denied under stress, as SVB found on 2023-03-09).
    """
    if bq.depuna is None:
        return None
    liquid = bq.chbal + bq.scaf
    return liquid


def run_threshold_after_htm_dollars(bq: BankQuarter) -> float | None:
    """Withdrawal amount at which the bank becomes balance-sheet insolvent:
    cash + AFS + HTM(fair value) exhausted against equity. Beyond this point
    every further dollar withdrawn exceeds what the bank's assets, marked to
    market, can cover."""
    if bq.depuna is None:
        return None
    return bq.chbal + bq.scaf + bq.schf


CORE_FEATURES = [
    "mtm_equity_ratio",
    "uninsured_share",
    "run_risk_score",
    "liquidity_cover",
]
