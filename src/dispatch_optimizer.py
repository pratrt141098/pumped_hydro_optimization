"""
Dynamic-programming dispatch optimizer for a 1,000 MW pumped-hydro asset
over a single 24-hour horizon with perfect foresight.

State space
-----------
State is (hour, storage_level).
  - hour: 0..23 (plus terminal "hour 24" for the DP base case)
  - storage_level: multiples of 250 MWh in [0, 8000], i.e. 33 discrete levels
    (250 is GCD(750, 1000), so all reachable storage states stay on this grid)

Recurrence
----------
Let V[h][s] = max total revenue from hour h through hour 23, given storage s.
Base case:  V[24][s] = 0 for all s.
For h = 23..0 and each storage state s:

    pump:     s + 750 <= 8000   →  s' = s + 750
    generate: s >= 1000         →  s' = s - 1000
    tmnsr:    always feasible   →  s' = s
    idle:     always feasible   →  s' = s

    V[h][s]      = max over feasible actions of  (R_action(h) + V[h+1][s'])
    policy[h][s] = argmax action

Forward reconstruction starts at (h=0, s=0) and follows policy[h][s].

Assumptions
-----------
* Efficiency is modeled on the pump side (1000 MWh consumed → 750 MWh stored;
  generate is 1:1). Total optimal revenue is invariant to which side carries
  the loss, but this convention yields a richer state space (multiples of 250
  vs multiples of 1000), which makes the DP grid more informative.
* Single product per hour: the asset cannot split capacity between DA energy
  and TMNSR within the same hour. Consistent with the required output schema.
* Terminal storage at hour 24 is valued at zero (single-day analysis).
* Perfect foresight of all prices.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from src import revenue

PUMP_CONSUMPTION_MWH = 1000   # MWh of energy purchased per pump hour
PUMP_STORAGE_GAIN_MWH = 750   # MWh added to storage per pump hour (75% RTE on pump side)
GENERATE_DRAW_MWH = 1000      # MWh drawn from storage per generate hour (1:1)
MAX_STORAGE_MWH = 8000
STORAGE_STEP_MWH = 250        # GCD(750, 1000)
N_STORAGE_STATES = MAX_STORAGE_MWH // STORAGE_STEP_MWH + 1   # 33
N_HOURS = 24

ACTIONS = ("pump", "generate", "tmnsr", "idle")


@dataclass
class DPResult:
    schedule: pd.DataFrame   # 24-row dispatch schedule
    value_table: np.ndarray  # V[h][s], shape (25, 33)
    policy_table: np.ndarray # policy[h][s], shape (24, 33), dtype object
    v0: float                # V[0][0] — optimal total revenue


def _storage_index(mwh: int) -> int:
    return mwh // STORAGE_STEP_MWH


def _storage_mwh(idx: int) -> int:
    return idx * STORAGE_STEP_MWH


def optimize(prices: pd.DataFrame) -> DPResult:
    """
    Run the backward DP and forward reconstruction.

    `prices` must have columns: hour, da_lmp, rt_lmp, tmnsr_price, tmnsr_strike,
    one row per hour 0..23.
    """
    prices = prices.sort_values("hour").reset_index(drop=True)
    assert list(prices["hour"]) == list(range(N_HOURS)), "prices must cover hours 0..23"

    da = prices["da_lmp"].to_numpy()
    rt = prices["rt_lmp"].to_numpy()
    tm = prices["tmnsr_price"].to_numpy()
    strike = prices["tmnsr_strike"].to_numpy()

    # Per-hour revenue for the three price-dependent actions (idle is always 0)
    r_pump = np.array([revenue.pump(da[h]) for h in range(N_HOURS)])
    r_gen = np.array([revenue.generate(da[h]) for h in range(N_HOURS)])
    r_tmnsr = np.array([revenue.tmnsr(tm[h], rt[h], strike[h]) for h in range(N_HOURS)])

    V = np.zeros((N_HOURS + 1, N_STORAGE_STATES))
    policy = np.empty((N_HOURS, N_STORAGE_STATES), dtype=object)

    pump_gain_idx = PUMP_STORAGE_GAIN_MWH // STORAGE_STEP_MWH      # +3 indices
    gen_draw_idx = GENERATE_DRAW_MWH // STORAGE_STEP_MWH           # -4 indices
    max_idx = N_STORAGE_STATES - 1

    for h in range(N_HOURS - 1, -1, -1):
        for s_idx in range(N_STORAGE_STATES):
            best_action = "idle"
            best_value = revenue.idle() + V[h + 1, s_idx]

            # tmnsr (always feasible, storage unchanged)
            v = r_tmnsr[h] + V[h + 1, s_idx]
            if v > best_value:
                best_value, best_action = v, "tmnsr"

            # pump
            if s_idx + pump_gain_idx <= max_idx:
                v = r_pump[h] + V[h + 1, s_idx + pump_gain_idx]
                if v > best_value:
                    best_value, best_action = v, "pump"

            # generate
            if s_idx - gen_draw_idx >= 0:
                v = r_gen[h] + V[h + 1, s_idx - gen_draw_idx]
                if v > best_value:
                    best_value, best_action = v, "generate"

            V[h, s_idx] = best_value
            policy[h, s_idx] = best_action

    # Forward reconstruction from (h=0, s=0)
    rows = []
    cumulative = 0.0
    s_idx = 0
    for h in range(N_HOURS):
        action = policy[h, s_idx]
        s_start = _storage_mwh(s_idx)

        if action == "pump":
            s_next_idx = s_idx + pump_gain_idx
            da_rev = r_pump[h]
            tm_rev = 0.0
        elif action == "generate":
            s_next_idx = s_idx - gen_draw_idx
            da_rev = r_gen[h]
            tm_rev = 0.0
        elif action == "tmnsr":
            s_next_idx = s_idx
            da_rev = 0.0
            tm_rev = r_tmnsr[h]
        else:  # idle
            s_next_idx = s_idx
            da_rev = 0.0
            tm_rev = 0.0

        hourly_total = da_rev + tm_rev
        cumulative += hourly_total
        rows.append({
            "hour": h,
            "action": action,
            "storage_start_mwh": s_start,
            "storage_end_mwh": _storage_mwh(s_next_idx),
            "da_energy_revenue": da_rev,
            "tmnsr_revenue": tm_rev,
            "hourly_total_revenue": hourly_total,
            "cumulative_revenue": cumulative,
        })
        s_idx = s_next_idx

    schedule = pd.DataFrame(rows)
    return DPResult(schedule=schedule, value_table=V, policy_table=policy, v0=V[0, 0])
