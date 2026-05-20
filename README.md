# Pumped-Hydro Dispatch Optimization — ISO-NE

Dynamic-programming dispatch optimizer for a 1,000 MW / 8,000 MWh pumped-hydro storage asset at Mass Hub on the ISO-NE system. Pulls live price data from the ISO-NE Web Services API, then solves the single-day optimal schedule across the DA energy and DA Ancillary Services (TMNSR) markets.

For **June 24, 2025**, the optimizer finds a total revenue of **\$2,318,210**.

---

## Project layout

```
.
├── src/
│   ├── fetch_data.py          ISO-NE Web API client (DA LMP, RT LMP, TMNSR, strike)
│   ├── revenue.py             Per-action revenue formulas (pump, generate, TMNSR, idle)
│   └── dispatch_optimizer.py  Backward-recurrence DP + forward reconstruction
├── scripts/
│   ├── fetch_data.py          Step 1: fetch all four endpoints, merge, save CSV
│   └── optimize_dispatch.py   Step 2: load prices, optimize, verify, plot
├── notebooks/
│   └── summary_writeup.ipynb   Full technical writeup with figures
├── data/                      Output CSVs (prices + schedule)
└── figures/                   Output PNGs
```

## Setup

```bash
pip install -r requirements.txt   # or: pip install requests python-dotenv pandas numpy matplotlib nbconvert
cp .env.example .env              # then fill in ISONE_USERNAME and ISONE_PASSWORD
```

Credentials are loaded via `python-dotenv` and only read from `.env` (which is gitignored). The ISO-NE Web Services API uses HTTP Basic Auth.

## Usage

```bash
# Step 1 — fetch prices for June 24, 2025 and save data/prices_20250624.csv
python scripts/fetch_data.py

# Step 2 — run the DP optimizer, save data/dispatch_schedule_20250624.csv
#          and figures/dispatch_20250624.png
python scripts/optimize_dispatch.py

# Optional — re-execute the writeup notebook end-to-end
python -m nbconvert --to notebook --execute --inplace notebooks/summary_writeup.ipynb
```

Both scripts print sanity-check results and a summary table to stdout. The notebook embeds the same content plus inline figures.

## Endpoints used

| Series | Endpoint |
|---|---|
| DA LMP at Mass Hub (LocId 4000) | `/hourlylmp/da/final/day/{YYYYMMDD}/location/4000` |
| RT LMP at Mass Hub (LocId 4000) | `/hourlylmp/rt/final/day/{YYYYMMDD}/location/4000` |
| DA reserves (TMNSR, etc.) | `/daasreservedata/day/{YYYYMMDD}` |
| DA A/S strike prices | `/daasstrikeprices/day/{YYYYMMDD}` |

All endpoints called with `Accept: application/json`.

## Asset and market model

| Parameter | Value |
|---|---|
| Pump capacity | 1,000 MW |
| Generate capacity | 1,000 MW |
| Storage capacity | 8,000 MWh |
| Round-trip efficiency | 75% (modeled on the pump side: 1,000 MWh in → 750 MWh stored; generate 1:1) |
| Starting / terminal storage | 0 MWh (terminal storage valued at zero) |

**Actions per hour** (mutually exclusive): pump, generate, clear TMNSR, idle.

**Revenue formulas** (capacity C = 1,000 MW):

```
R_pump(h)     = -C · DA(h)
R_generate(h) = +C · DA(h)
closeout(h)   = max(RT(h) - Strike(h), 0)         # call payoff, floored at zero
R_tmnsr(h)    = C · (TMNSR(h) - closeout(h))      # net revenue NOT floored
R_idle        = 0
```

TMNSR is settled as a **call option on real-time energy**: the asset receives the TMNSR clearing price and pays the call payoff on RT. Because the net is unfloored, TMNSR revenue can be negative when RT spikes far above strike — in those hours, idle dominates.

## Dynamic programming

State: `(hour, storage_level)`. Storage discretized to multiples of 250 MWh = `GCD(750, 1000)`, giving 33 levels in [0, 8000]. State space is 25 × 33 = 825 cells.

Recurrence:

```
V[24][s] = 0  for all s

for h = 23 down to 0:
    for each storage state s:
        V[h][s] = max over feasible actions a of  R_a(h) + V[h+1][s'(s,a)]
```

Optimal schedule is reconstructed forward from `(h=0, s=0)` following the argmax policy.

## Results on June 24, 2025

| Item | Amount |
|---|---:|
| DA generation revenue | \$2,147,090 |
| Pumping cost | (\$375,670) |
| Net DA energy revenue | \$1,771,420 |
| TMNSR revenue | \$546,790 |
| **Total revenue** | **\$2,318,210** |

Action distribution: 8 pump hours (0–7), 10 TMNSR hours (8–15, 22–23), 6 generate hours (16–21), 0 idle hours. Reservoir fills to 6,000 MWh by hour 15 and drains to zero by midnight. Realized round-trip efficiency: 75%.

See [notebooks/summary_writeup.ipynb](notebooks/summary_writeup.ipynb) for full methodology, sanity checks, figures, and discussion of real-world implementation considerations (forecasting, multi-day continuation value, partial dispatch, physical constraints, market impact).

## Key assumptions

- Perfect foresight of all four price series.
- One product per hour (no DA/TMNSR capacity splitting).
- Full-capacity dispatch only (1,000 MW or zero).
- No ramping limits, startup costs, minimum run/down times, or pump↔generate transition delays.
- Price-taker.
- Terminal storage valued at zero (single-day analysis).
