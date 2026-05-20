"""
Hourly revenue formulas for the four dispatch actions.

Each function takes the prices for a single hour and the asset's MW capacity
and returns dollar revenue for that hour. Costs (e.g., pumping) are returned
as negative numbers so totals can be summed directly.

Capacity defaults to 1000 MW per the problem spec.
"""

CAPACITY_MW = 1000


def pump(da_lmp: float, capacity: float = CAPACITY_MW) -> float:
    """Pump action: buy 1000 MWh of DA energy. Cost is negative revenue."""
    return -capacity * da_lmp


def generate(da_lmp: float, capacity: float = CAPACITY_MW) -> float:
    """Generate action: sell 1000 MWh of DA energy."""
    return capacity * da_lmp


def tmnsr(tmnsr_price: float, rt_lmp: float, strike: float, capacity: float = CAPACITY_MW) -> float:
    """
    TMNSR clearing revenue, net of the closeout charge (ISO-NE call-option settlement).

        closeout    = max(RT_LMP - Strike, 0)   (floored at zero — the call payoff)
        net per MW  = TMNSR_price - closeout    (NOT floored — net revenue can go negative)

    The DA A/S product is settled as a call option on real-time energy: the closeout
    charge is the option payoff (always ≥ 0), and the cleared MW receives the TMNSR
    clearing price net of that payoff. When RT spikes far above the strike, the closeout
    can exceed the TMNSR price and net revenue is negative — so idling can dominate
    clearing TMNSR, unlike in a payoff-floored formulation.
    """
    closeout = max(rt_lmp - strike, 0.0)
    return capacity * (tmnsr_price - closeout)


def idle() -> float:
    return 0.0
