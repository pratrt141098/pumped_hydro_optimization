"""
ISO-NE data fetching layer for June 24, 2025.

Fetches DA LMPs, RT LMPs, TMNSR prices, and DA A/S strike prices from the
ISO-NE Web API and returns clean pandas DataFrames ready for optimization.
"""
import os
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://webservices.iso-ne.com/api/v1.1"
HEADERS = {"Accept": "application/json"}
DATE = "20250624"
MASS_HUB = 4000


def _auth() -> tuple[str, str]:
    user = os.environ.get("ISONE_USERNAME")
    password = os.environ.get("ISONE_PASSWORD")
    if not user or not password:
        raise EnvironmentError("ISONE_USERNAME and ISONE_PASSWORD must be set in .env")
    return user, password


def _get(url: str) -> dict:
    resp = requests.get(url, auth=_auth(), headers=HEADERS)
    if not resp.ok:
        raise RuntimeError(
            f"Request failed [{resp.status_code}] {url}\n{resp.text[:500]}"
        )
    return resp.json()


def _parse_hour_from_begin_date(begin_date: str) -> int:
    """Extract 0-based hour from ISO-8601 BeginDate string, e.g. '2025-06-24T13:00:00.000-04:00' → 13."""
    return int(begin_date[11:13])


def _parse_hour_from_end_label(local_hour_end: str) -> int:
    """Convert 1-indexed local_hour_end string (e.g. '01') to 0-based hour."""
    return int(local_hour_end) - 1


def _sanity_check(df: pd.DataFrame, price_col: str, label: str) -> None:
    assert len(df) == 24, f"{label}: expected 24 rows, got {len(df)}"
    assert df[price_col].notna().all(), f"{label}: null values found in {price_col}"
    assert list(df["hour"]) == list(range(24)), f"{label}: hours are not 0-23 in order"
    print(f"\n{label} — {price_col}")
    print(f"  min={df[price_col].min():.3f}  max={df[price_col].max():.3f}  mean={df[price_col].mean():.3f}")


def fetch_da_lmp() -> pd.DataFrame:
    """Day-Ahead LMPs at Mass Hub. Returns columns: hour (0-23), da_lmp ($/MWh)."""
    url = f"{BASE_URL}/hourlylmp/da/final/day/{DATE}/location/{MASS_HUB}"
    records = _get(url)["HourlyLmps"]["HourlyLmp"]

    rows = [
        {
            "hour": _parse_hour_from_begin_date(r["BeginDate"]),
            "da_lmp": float(r["LmpTotal"]),
        }
        for r in records
    ]
    df = pd.DataFrame(rows).sort_values("hour").reset_index(drop=True)
    _sanity_check(df, "da_lmp", "DA LMP")
    return df


def fetch_rt_lmp() -> pd.DataFrame:
    """Real-Time LMPs at Mass Hub. Returns columns: hour (0-23), rt_lmp ($/MWh)."""
    url = f"{BASE_URL}/hourlylmp/rt/final/day/{DATE}/location/{MASS_HUB}"
    records = _get(url)["HourlyLmps"]["HourlyLmp"]

    rows = [
        {
            "hour": _parse_hour_from_begin_date(r["BeginDate"]),
            "rt_lmp": float(r["LmpTotal"]),
        }
        for r in records
    ]
    df = pd.DataFrame(rows).sort_values("hour").reset_index(drop=True)

    # API returns hourly data; if granularity ever changes to 5-min, aggregate here
    if len(df) > 24:
        df = df.groupby("hour", as_index=False)["rt_lmp"].mean()

    _sanity_check(df, "rt_lmp", "RT LMP")
    return df


def fetch_tmnsr() -> pd.DataFrame:
    """TMNSR clearing prices (system-wide). Returns columns: hour (0-23), tmnsr_price ($/MWh)."""
    url = f"{BASE_URL}/daasreservedata/day/{DATE}"
    records = _get(url)["isone_web_services"]["day_ahead_reserves"]["day_ahead_reserve"]

    rows = [
        {
            "hour": _parse_hour_from_end_label(r["market_hour"]["local_hour_end"]),
            "tmnsr_price": float(r["tmnsr_clearing_price"]),
        }
        for r in records
    ]
    df = pd.DataFrame(rows).sort_values("hour").reset_index(drop=True)
    _sanity_check(df, "tmnsr_price", "TMNSR")
    return df


def fetch_strike_prices() -> pd.DataFrame:
    """DA A/S TMNSR strike prices (system-wide). Returns columns: hour (0-23), tmnsr_strike ($/MWh)."""
    url = f"{BASE_URL}/daasstrikeprices/day/{DATE}"
    records = _get(url)["isone_web_services"]["day_ahead_strike_prices"]["day_ahead_strike_price"]

    rows = [
        {
            "hour": _parse_hour_from_end_label(r["market_hour"]["local_hour_end"]),
            "tmnsr_strike": float(r["strike_price"]),
        }
        for r in records
    ]
    df = pd.DataFrame(rows).sort_values("hour").reset_index(drop=True)
    _sanity_check(df, "tmnsr_strike", "Strike Prices")
    return df
