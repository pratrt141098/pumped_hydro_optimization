"""
Orchestration script for Step 1: fetch all four ISO-NE price series,
merge into a single DataFrame, and save to data/prices_20250624.csv.
"""
import os
import sys
import pandas as pd

# allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.fetch_data import fetch_da_lmp, fetch_rt_lmp, fetch_tmnsr, fetch_strike_prices

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prices_20250624.csv")


def main():
    print("Fetching DA LMP...")
    da = fetch_da_lmp()

    print("Fetching RT LMP...")
    rt = fetch_rt_lmp()

    print("Fetching TMNSR prices...")
    tmnsr = fetch_tmnsr()

    print("Fetching DA A/S strike prices...")
    strikes = fetch_strike_prices()

    # merge all on hour
    combined = (
        da
        .merge(rt, on="hour")
        .merge(tmnsr, on="hour")
        .merge(strikes, on="hour")
    )

    assert len(combined) == 24, f"Merge lost rows: {len(combined)} != 24"
    assert list(combined.columns) == ["hour", "da_lmp", "rt_lmp", "tmnsr_price", "tmnsr_strike"]

    print("\n=== Combined DataFrame (all 24 hours) ===")
    print(combined.to_string(index=False))

    print(f"\n=== Summary ===")
    print(combined.describe().loc[["min", "max", "mean"]].to_string())

    out = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    combined.to_csv(out, index=False)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
