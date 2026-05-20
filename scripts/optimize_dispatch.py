"""
Step 2 orchestration: load Step 1 prices, run the DP optimizer, run sanity
checks, save the schedule CSV, and produce the dispatch figure.
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.dispatch_optimizer import (
    optimize,
    MAX_STORAGE_MWH,
    PUMP_CONSUMPTION_MWH,
    PUMP_STORAGE_GAIN_MWH,
    GENERATE_DRAW_MWH,
)
from src import revenue

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRICES_PATH = os.path.join(REPO, "data", "prices_20250624.csv")
SCHEDULE_PATH = os.path.join(REPO, "data", "dispatch_schedule_20250624.csv")
FIGURE_PATH = os.path.join(REPO, "figures", "dispatch_20250624.png")

ACTION_COLORS = {
    "pump": "red",
    "generate": "green",
    "tmnsr": "blue",
    "idle": "gray",
}


def sanity_checks(schedule: pd.DataFrame, prices: pd.DataFrame, v0: float) -> None:
    print("\n=== Sanity checks ===")

    # Storage bounds
    assert (schedule["storage_start_mwh"] >= 0).all()
    assert (schedule["storage_end_mwh"] >= 0).all()
    assert (schedule["storage_start_mwh"] <= MAX_STORAGE_MWH).all()
    assert (schedule["storage_end_mwh"] <= MAX_STORAGE_MWH).all()
    print("  ✓ storage stays within [0, 8000] MWh")

    # Transitions match the action
    for _, row in schedule.iterrows():
        s0, s1, action = row["storage_start_mwh"], row["storage_end_mwh"], row["action"]
        delta = s1 - s0
        if action == "pump":
            assert delta == PUMP_STORAGE_GAIN_MWH, f"hour {row['hour']}: pump delta {delta}"
        elif action == "generate":
            assert delta == -GENERATE_DRAW_MWH, f"hour {row['hour']}: generate delta {delta}"
        else:
            assert delta == 0, f"hour {row['hour']}: {action} delta {delta}"

    # Continuity: each hour's start matches prior hour's end (starting at 0)
    prev_end = 0
    for _, row in schedule.iterrows():
        assert row["storage_start_mwh"] == prev_end, f"discontinuity at hour {row['hour']}"
        prev_end = row["storage_end_mwh"]
    print("  ✓ storage transitions match actions and are continuous")

    # Under the corrected call-option settlement, R_tmnsr can be negative.
    # Idle weakly dominates TMNSR iff R_tmnsr <= 0, so any idle hour must satisfy that.
    for _, row in schedule.iterrows():
        if row["action"] == "idle":
            h = int(row["hour"])
            pr = prices.iloc[h]
            r_tm = revenue.tmnsr(pr["tmnsr_price"], pr["rt_lmp"], pr["tmnsr_strike"])
            assert r_tm <= 0.0, f"idle at hour {h} but TMNSR revenue would be {r_tm}"
    print("  ✓ idle hours only when TMNSR revenue would be <= 0")

    # Total revenue matches V[0][0]
    total = schedule["hourly_total_revenue"].sum()
    assert np.isclose(total, v0), f"schedule total {total} != V[0][0] {v0}"
    print(f"  ✓ schedule total ({total:,.2f}) matches V[0][0] ({v0:,.2f})")


def print_summary(schedule: pd.DataFrame) -> None:
    total_rev = schedule["hourly_total_revenue"].sum()
    da_rev = schedule["da_energy_revenue"].sum()
    gen_rev = schedule.loc[schedule["action"] == "generate", "da_energy_revenue"].sum()
    pump_cost = schedule.loc[schedule["action"] == "pump", "da_energy_revenue"].sum()
    tm_rev = schedule["tmnsr_revenue"].sum()

    pump_hours = (schedule["action"] == "pump").sum()
    gen_hours = (schedule["action"] == "generate").sum()
    tmnsr_hours = (schedule["action"] == "tmnsr").sum()
    idle_hours = (schedule["action"] == "idle").sum()

    mwh_pumped = pump_hours * PUMP_CONSUMPTION_MWH
    mwh_generated = gen_hours * GENERATE_DRAW_MWH
    ending_storage = int(schedule["storage_end_mwh"].iloc[-1])

    print("\n=== Summary ===")
    print(f"Total revenue for the day:       ${total_rev:>12,.2f}")
    print(f"  Generation revenue (DA sales): ${gen_rev:>12,.2f}")
    print(f"  Pumping cost (DA purchases):   ${pump_cost:>12,.2f}")
    print(f"  Net DA energy revenue:         ${da_rev:>12,.2f}")
    print(f"  TMNSR revenue:                 ${tm_rev:>12,.2f}")
    print()
    print(f"Action counts: pump={pump_hours}  generate={gen_hours}  tmnsr={tmnsr_hours}  idle={idle_hours}")
    print(f"Total MWh pumped (grid draw):    {mwh_pumped:>6,} MWh")
    print(f"Total MWh generated (grid feed): {mwh_generated:>6,} MWh")
    print(f"Ending storage:                  {ending_storage:>6,} MWh")


def make_figure(schedule: pd.DataFrame, prices: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(FIGURE_PATH), exist_ok=True)
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 2]}
    )

    # Top: DA LMP line with action-colored hour markers
    ax_top.plot(prices["hour"], prices["da_lmp"], color="black", lw=1.2, label="DA LMP")
    for action, color in ACTION_COLORS.items():
        mask = schedule["action"] == action
        if mask.any():
            ax_top.scatter(
                schedule.loc[mask, "hour"],
                prices.loc[mask.values, "da_lmp"],
                color=color, s=80, label=action, zorder=3, edgecolor="black", linewidth=0.5,
            )
    ax_top.set_ylabel("DA LMP ($/MWh)")
    ax_top.set_title("Optimal Dispatch — June 24, 2025")
    ax_top.legend(loc="upper left", framealpha=0.9)
    ax_top.grid(True, alpha=0.3)

    # Bottom: cumulative revenue bars
    ax_bot.bar(schedule["hour"], schedule["cumulative_revenue"] / 1000, color="steelblue")
    ax_bot.set_ylabel("Cumulative revenue ($k)")
    ax_bot.set_xlabel("Hour")
    ax_bot.set_xticks(range(24))
    ax_bot.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIGURE_PATH, dpi=130)
    plt.close(fig)
    print(f"\nSaved figure to {FIGURE_PATH}")


def main():
    prices = pd.read_csv(PRICES_PATH)
    result = optimize(prices)

    print("=== Dispatch schedule ===")
    print(result.schedule.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    sanity_checks(result.schedule, prices, result.v0)
    print_summary(result.schedule)

    os.makedirs(os.path.dirname(SCHEDULE_PATH), exist_ok=True)
    result.schedule.to_csv(SCHEDULE_PATH, index=False)
    print(f"\nSaved schedule to {SCHEDULE_PATH}")

    make_figure(result.schedule, prices)


if __name__ == "__main__":
    main()
