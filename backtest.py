import statistics
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from openelectricity import OEClient
from openelectricity.types import MarketMetric

from main import BatterySpecs, MarketInterval, calculate_optimal_dispatch

# how many trailing 24h windows to backtest
N_DAYS = 7

# same battery config used by pipeline.py's demo payload
BATTERY = BatterySpecs(capacity_mwh=5.0, max_mw=2.5, efficiency=0.9)


def fetch_sa1_window(client: OEClient, start: datetime, end: datetime) -> list[MarketInterval]:
    # same fetch/resample steps as run_live_simulation() in main.py, just with an explicit window
    response = client.get_market(
        network_code="NEM",
        network_region="SA1",
        metrics=[MarketMetric.PRICE],
        interval="5m",
        date_start=start,
        date_end=end,
    )
    df = response.to_pandas()
    df["interval"] = pd.to_datetime(df["interval"])
    df = df.set_index("interval").resample("30min").mean().reset_index().tail(48)

    return [
        MarketInterval(
            timestamp=row["interval"].isoformat(),
            price_aud_mwh=float(row["price"]) if pd.notna(row["price"]) else 0.0,
        )
        for _, row in df.iterrows()
    ]


def run_backtest(n_days: int = N_DAYS) -> list[dict]:
    results = []
    with OEClient() as client:
        for days_back in range(1, n_days + 1):
            end = datetime.now() - timedelta(days=days_back - 1)
            start = end - timedelta(days=1)

            market_data = fetch_sa1_window(client, start, end)
            if len(market_data) < 48:
                print(f"day -{days_back}: skipped, only {len(market_data)} intervals returned")
                continue

            result = calculate_optimal_dispatch(BATTERY, market_data)
            prices = [m.price_aud_mwh for m in market_data]

            row = {
                "days_back": days_back,
                "status": result["optimization_status"],
                "profit_aud": result["total_profit_aud"],
                "price_min": min(prices),
                "price_max": max(prices),
                "price_spread": max(prices) - min(prices),
            }
            results.append(row)
            print(
                f"day -{days_back}: profit=${row['profit_aud']:.2f}  "
                f"min={row['price_min']:.2f} max={row['price_max']:.2f} "
                f"spread={row['price_spread']:.2f}"
            )

    return results


if __name__ == "__main__":
    results = run_backtest()

    if results:
        profits = [r["profit_aud"] for r in results]
        print("\n--- summary ---")
        print(f"battery: {BATTERY.capacity_mwh}MWh / {BATTERY.max_mw}MW / {BATTERY.efficiency} efficiency")
        print(f"n_days: {len(profits)}")
        print(f"mean daily profit: ${statistics.mean(profits):.2f}")
        print(f"range: ${min(profits):.2f} - ${max(profits):.2f}")
