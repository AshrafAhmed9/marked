"""
Classic failure-prediction baseline: a CAMELS-style logistic regression
trained ONLY on failures through 2019 (equity, ROA, net charge-offs, loan/
deposit ratio, brokered-deposit reliance, asset growth). No uninsured-deposit
or mark-to-market features -- this deliberately reproduces the standard
credit-risk lens that regulators and most bank-failure ML papers use, so we
can show what it misses.

This is a genuine second, independent baseline (distinct from the Tier 1
regulatory ratio already compared against in backtest.py). It exists to
answer: "does a reasonable ML model, trained the ordinary way, also catch
SVB?" The honest answer, checked in the spike, is no -- it ranks SVB and
First Republic among the safest banks, while still catching credit-driven
failures like Citizens Bank (Sac City). Publishing both outcomes is the
point: it shows why a second, different lens (run_risk_score) is necessary,
not just that our number is bigger.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

FEATURES = ["EQV", "ROA", "NCLNLSR", "LNLSDEPR", "NTLNLSR", "ASSTLTR", "BROR"]

TRAIN_QUARTERS = ["20080630", "20090630", "20100630"]
TRAIN_HORIZON_DAYS = 730  # label = failed within 2 years of this quarter


def _load_quarter(repdte: str) -> pd.DataFrame:
    path = DATA_DIR / f"financials_{repdte}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run fetch.py first")
    df = pd.read_parquet(path)
    df["BROR"] = 100.0 * df["BRO"].fillna(0).astype(float) / df["DEP"].replace(0, np.nan)
    df["BROR"] = df["BROR"].fillna(0)
    for f in FEATURES:
        df[f] = pd.to_numeric(df[f], errors="coerce").fillna(0.0).clip(-1e4, 1e4)
    df["REPDTE"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d")
    df["CERT"] = df["CERT"].astype(int)
    return df


def _load_failures() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "failures.parquet")
    df["FAILDATE"] = pd.to_datetime(df["FAILDATE"], format="%m/%d/%Y")
    # ~488 of 4,117 historical failure records (mostly pre-1940s, before the
    # modern CERT numbering system) have a null CERT and can never be joined
    # to Call Report financials data anyway. Dropped here, not silently
    # coerced -- none are in our 2019-2026 window of interest.
    df = df.dropna(subset=["CERT"])
    df["CERT"] = df["CERT"].astype(int)
    return df


def build_training_set(failures: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    # earliest failure date per CERT (a handful of certs recur across
    # separate historical failure events; we only need "did this cert fail
    # within the label horizon", so the earliest date is the correct one
    # to test against and using .map() with a raw Series lookup blows up
    # when a CERT key maps to more than one row)
    fail_within = failures.groupby("CERT")["FAILDATE"].min()
    frames = []
    for q in TRAIN_QUARTERS:
        df = _load_quarter(q)
        qdate = df["REPDTE"].iloc[0]
        horizon_end = qdate + pd.Timedelta(days=TRAIN_HORIZON_DAYS)
        fdate = df["CERT"].map(fail_within)
        df["label"] = ((fdate > qdate) & (fdate <= horizon_end)).fillna(False).astype(int)
        frames.append(df)
    full = pd.concat(frames, ignore_index=True)
    return full[FEATURES], full["label"]


def fit_classic_model(failures: pd.DataFrame) -> tuple[LogisticRegression, StandardScaler]:
    X, y = build_training_set(failures)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    Xs = np.clip(Xs, -8, 8)
    model = LogisticRegression(max_iter=1000)
    model.fit(Xs, y)
    return model, scaler


def score_quarter(repdte: str, model: LogisticRegression, scaler: StandardScaler) -> pd.DataFrame:
    df = _load_quarter(repdte)
    X = df[FEATURES]
    Xs = np.clip(scaler.transform(X), -8, 8)
    df["classic_score"] = model.predict_proba(Xs)[:, 1]
    df["classic_rank"] = df["classic_score"].rank(ascending=False, method="min").astype(int)
    return df[["CERT", "NAMEFULL", "REPDTE", "classic_score", "classic_rank"]]


if __name__ == "__main__":
    failures = _load_failures()
    model, scaler = fit_classic_model(failures)
    print("Classic model coefficients (feature: weight):")
    for f, w in zip(FEATURES, model.coef_[0]):
        print(f"  {f}: {w:.3f}")

    test = score_quarter("20220930", model, scaler)
    n = len(test)
    named = {24735: "SVB", 57053: "Signature", 59017: "First Republic",
             27332: "Republic First", 25851: "Heartland Tri-State (fraud)",
             8758: "Citizens Bank Sac City (credit)"}
    for cert, name in named.items():
        row = test[test["CERT"] == cert]
        if row.empty:
            print(f"{name}: not found in 2022Q3")
            continue
        r = int(row["classic_rank"].iloc[0])
        print(f"{name}: classic rank {r} of {n}")
