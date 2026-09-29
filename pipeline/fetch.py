"""
Pull every quarterly Call Report financials snapshot (2001Q1-latest) and the
full bank-failures list from the FDIC BankFind Suite API (free, keyless,
public: https://banks.data.fdic.gov/docs/).

Caches each quarter to data/raw/financials_<REPDTE>.parquet so re-runs don't
re-hit the API. Run `uv run pipeline/fetch.py` to populate.

Look-ahead discipline: this script records REPDTE (the quarter-end date) for
every row. It does NOT record or assume a filing/publication date. Call
Reports are not public the day a quarter ends — backtest.py enforces a
30-day-after-REPDTE floor before treating a quarter's data as "known" at any
as-of date. That floor is a conservative estimate (real filing deadlines are
30-45 days after quarter-end); it is documented, not hidden.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://api.fdic.gov/banks"

FIELDS = [
    "CERT", "NAMEFULL", "REPDTE",
    "ASSET", "EQ", "CHBAL", "SCAF", "SCHA", "SCHF",
    "DEPUNA", "DEP", "OTHBFHLB",
    "IDT1RWAJR", "RBC1AAJ", "EQV", "ROA",
    "NCLNLSR", "NTLNLSR", "LNLSDEPR", "ASSTLTR", "BRO",
]

FAILURE_FIELDS = ["CERT", "NAME", "FAILDATE", "COST", "QBFASSET", "QBFDEP"]


def quarter_ends(start_year: int, end_year: int) -> list[str]:
    dates = []
    for y in range(start_year, end_year + 1):
        for md in ("0331", "0630", "0930", "1231"):
            dates.append(f"{y}{md}")
    return dates


def fetch_financials_quarter(repdte: str, retries: int = 3) -> pd.DataFrame | None:
    out_path = RAW_DIR / f"financials_{repdte}.parquet"
    if out_path.exists():
        return pd.read_parquet(out_path)

    url = f"{BASE}/financials"
    params = {
        "filters": f"REPDTE:{repdte}",
        "fields": ",".join(FIELDS),
        "limit": 10000,
    }
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
            rows = [r["data"] for r in payload.get("data", [])]
            if not rows:
                return None
            df = pd.DataFrame(rows)
            df.to_parquet(out_path, index=False)
            return df
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  retry {repdte} after {e} (sleep {wait}s)", file=sys.stderr)
            time.sleep(wait)
    print(f"  FAILED to fetch {repdte} after {retries} attempts", file=sys.stderr)
    return None


def fetch_all_financials(start_year: int = 2001, end_year: int = 2026) -> None:
    dates = quarter_ends(start_year, end_year)
    for i, d in enumerate(dates):
        cached = (RAW_DIR / f"financials_{d}.parquet").exists()
        df = fetch_financials_quarter(d)
        n = len(df) if df is not None else 0
        tag = "cached" if cached else "fetched"
        print(f"[{i+1}/{len(dates)}] {d}: {n} banks ({tag})")


def fetch_failures() -> pd.DataFrame:
    out_path = RAW_DIR / "failures.parquet"
    if out_path.exists():
        return pd.read_parquet(out_path)
    url = f"{BASE}/failures"
    params = {"fields": ",".join(FAILURE_FIELDS), "limit": 10000, "sort_by": "FAILDATE", "sort_order": "ASC"}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    rows = [r["data"] for r in resp.json()["data"]]
    df = pd.DataFrame(rows)
    df.to_parquet(out_path, index=False)
    print(f"failures: {len(df)} rows")
    return df


if __name__ == "__main__":
    print("Fetching bank failures list...")
    fetch_failures()
    print("Fetching quarterly financials 2001-2026 (this takes a while, cached per quarter)...")
    fetch_all_financials()
    print("Done.")
