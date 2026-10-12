"""Turn a price vector into a battery schedule with the app's own LP, then score it on actual prices."""

from datetime import datetime, timedelta

import numpy as np

from forecasting.config import BATTERY_CAPACITY_MWH, BATTERY_EFFICIENCY, BATTERY_MAX_MW, DT_HOURS
from main import BatterySpecs, MarketInterval, calculate_optimal_dispatch

BATTERY = BatterySpecs(capacity_mwh=BATTERY_CAPACITY_MWH, max_mw=BATTERY_MAX_MW, efficiency=BATTERY_EFFICIENCY)


def schedule(prices, battery: BatterySpecs = BATTERY) -> dict[str, np.ndarray]:
    """Run the unchanged LP from main.py on `prices` (forecast or actual)."""
    t0 = datetime(2000, 1, 1)
    market = [MarketInterval(timestamp=t0 + timedelta(minutes=30 * i), price_aud_mwh=float(p)) for i, p in enumerate(prices)]
    result = calculate_optimal_dispatch(battery, market)
    if result["optimization_status"] != "Optimal":
        raise RuntimeError(f"LP status {result['optimization_status']}")
    rows = result["schedule"]
    return {k: np.array([r[k] for r in rows]) for k in ("charge_mw", "discharge_mw", "soc_mwh")}


def realised_profit(charge, discharge, actual_prices) -> np.ndarray:
    """Per-interval AUD earned by executing (charge, discharge) at the ACTUAL prices."""
    return (np.asarray(discharge) - np.asarray(charge)) * np.asarray(actual_prices) * DT_HOURS


def capture_rate(realised_total: float, perfect_total: float) -> float:
    return realised_total / perfect_total
