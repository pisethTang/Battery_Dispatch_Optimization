"""Writes results/REPORT.md and the typical-day chart from the backtest outputs."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forecasting import config as C

COLOURS = {"perfect_foresight": "#111827", "naive": "#f59e0b", "lightgbm": "#2563eb", "lstm": "#db2777"}
LABELS = {"perfect_foresight": "Actual (perfect foresight)", "naive": "Naive (yesterday)", "lightgbm": "LightGBM", "lstm": "LSTM"}


def typical_day(daily: pd.DataFrame) -> str:
    """The test day whose perfect-foresight profit is closest to the median."""
    pf = daily["perfect_foresight_aud"]
    return daily.loc[(pf - pf.median()).abs().idxmin(), "date"]


def plot_day(day: str, forecasts: dict, P: pd.DataFrame, path):
    d = pd.Timestamp(day)
    x = np.arange(C.INTERVALS_PER_DAY) / 2
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(x, P.loc[d].to_numpy(), color=COLOURS["perfect_foresight"], lw=2.2, label=LABELS["perfect_foresight"])
    for n in ("naive", "lightgbm", "lstm"):
        ax.plot(x, forecasts[n][d], color=COLOURS[n], lw=1.6, ls="--" if n == "naive" else "-", label=LABELS[n])
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.set_xlim(0, 23.5)
    ax.set_xticks(range(0, 24, 3), [f"{h:02d}:00" for h in range(0, 24, 3)])
    ax.set_xlabel("Interval start (AEST)")
    ax.set_ylabel("SA1 spot price (AUD/MWh)")
    ax.set_title(f"Typical test day {day}: actual vs day-ahead forecasts")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def write_report(result: dict, validation: dict, daily: pd.DataFrame, forecasts: dict, P: pd.DataFrame):
    day = typical_day(daily)
    plot_day(day, forecasts, P, C.RESULTS_DIR / "typical_day.png")
    row = daily.set_index("date").loc[day]

    m = result["models"]
    best = result["best_ml_model"]
    data, bat, sp = result["data"], result["battery"], result["split"]
    ml_ranked = sorted(["lightgbm", "lstm"], key=lambda n: -m[n]["capture_rate"])

    lines = [
        "# Day-ahead price forecasting backtest (SA1)",
        "",
        f"Generated {result['generated_at']} by `python -m forecasting.backtest` from `data/sa1_prices.parquet`.",
        "",
        "## Headline",
        "",
        f"Over **{result['Z_test_days']} test days** ({sp['test'][0]} to {sp['test'][1]}), scheduling the battery on "
        f"**{LABELS[best]}** forecasts captured **{pct(m[best]['capture_rate'])}** of perfect-foresight arbitrage revenue, "
        f"vs **{pct(m['naive']['capture_rate'])}** for the naive same-time-yesterday baseline. "
        f"{LABELS[ml_ranked[0]]} beat {LABELS[ml_ranked[1]]} "
        f"({pct(m[ml_ranked[0]]['capture_rate'])} vs {pct(m[ml_ranked[1]]['capture_rate'])}).",
        "",
        "## Data",
        "",
        f"- Source: {data['source']}",
        f"- Range: {data['start']} to {data['end']} ({data['days']} days, {data['rows']:,} half-hour rows), {data['timezone']}",
        f"- Gaps: {data['missing_30min_intervals']} missing and {data['partial_30min_intervals']} partially observed half-hours. {data['gap_handling']}",
        f"- Price range: {data['price_min']:,.2f} to {data['price_max']:,.2f} AUD/MWh",
        "- Open Electricity (used by the live app) only serves the last 730 days on the current plan, so history comes "
        "from AEMO NEMWeb; the same 5-minute prices were spot-checked against Open Electricity.",
        "",
        "## Battery (fixed for every day)",
        "",
        f"- Capacity {bat['capacity_mwh']} MWh, max charge/discharge {bat['max_mw']} MW, efficiency {bat['efficiency']} "
        f"({bat['efficiency_applied_to']}), starts each day empty, {bat['interval_hours']} h intervals.",
        "- These are the React app's default sliders and the API's default efficiency. The LP is `calculate_optimal_dispatch()` "
        "from `main.py`, unchanged.",
        "",
        "## Method",
        "",
        f"- Train: {sp['train'][0]} to {sp['train'][1]}. Validation: {sp['validation'][0]} to {sp['validation'][1]} "
        f"({validation['validation_days']} days). Test: {sp['test'][0]} to {sp['test'][1]}.",
        "- Decision at the end of day D-1; all 48 half-hour prices of day D are forecast from data up to D-1 only "
        "(enforced by `tests/test_forecasting.py`).",
        f"- Expanding window: each model is retrained every {sp['retrain_every_days']} days on all data before the retrain "
        "date (early stopping uses the last 60 days of that training window), then forecasts each day of the block one day ahead.",
        "- Hyperparameters, target transform / loss and training start were chosen on the validation period by capture "
        "rate, with the test period removed from the data, then frozen.",
        "- Each test day: LP on actual prices gives perfect foresight PF_D; LP on each forecast gives a schedule which is "
        "scored at actual prices, `sum((d - c) * actual * 0.5)`. Capture rate = sum(realised) / sum(PF).",
        "",
        "Frozen configurations:",
        "",
    ]
    for n in ("lightgbm", "lstm"):
        lines.append(f"- {LABELS[n]}: `{result['chosen_configs'][n]}`")
    lines += [
        "",
        "## Results (test period)",
        "",
        f"Z = {result['Z_test_days']} days. Perfect-foresight revenue over the period: ${result['perfect_foresight_aud']:,.0f}.",
        "",
        "| Model | Capture rate | Realised revenue (AUD) | MAE (AUD/MWh) | RMSE (AUD/MWh) | Days with a loss |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for n in ("naive", "lightgbm", "lstm"):
        lines.append(f"| {LABELS[n]} | {pct(m[n]['capture_rate'])} | {m[n]['realised_aud']:,.0f} | {m[n]['mae']:.1f} | "
                     f"{m[n]['rmse']:.1f} | {m[n]['days_with_loss']} |")
    lines += [
        "",
        "Capture rate by quarter:",
        "",
        "| Quarter | Days | Perfect foresight (AUD) | Naive | LightGBM | LSTM |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for q in result["quarterly"]:
        lines.append(f"| {q['quarter']} | {q['days']} | {q['perfect_foresight_aud']:,.0f} | {pct(q['naive_capture_rate'])} | "
                     f"{pct(q['lightgbm_capture_rate'])} | {pct(q['lstm_capture_rate'])} |")
    lines += [
        "",
        "Validation results (used for selection; test period not involved):",
        "",
        "| Model | Config | Val capture | Val MAE |",
        "|---|---|---:|---:|",
    ]
    for n in ("naive", "lightgbm", "lstm"):
        for c in sorted(validation["models"][n]["candidates"], key=lambda c: -c["capture_rate"]):
            chosen = " (chosen)" if c["config"] == validation["models"][n]["chosen"] else ""
            lines.append(f"| {LABELS[n]}{chosen} | `{c['config']}` | {pct(c['capture_rate'])} | {c['mae']:.1f} |")
    lines += [
        "",
        "## Typical test day",
        "",
        f"![Typical test day](typical_day.png)",
        "",
        f"{day} is the test day whose perfect-foresight profit (${row['perfect_foresight_aud']:,.0f}) is closest to the "
        f"median. Realised that day: naive ${row['naive_aud']:,.0f}, LightGBM ${row['lightgbm_aud']:,.0f}, "
        f"LSTM ${row['lstm_aud']:,.0f}.",
        "",
        "## Limitations",
        "",
        "This is a single small battery acting as a price taker in one region (SA1) on energy arbitrage only: no FCAS, "
        "no network losses, no degradation cost and no cycling limit. The LP is the app's unchanged formulation, so efficiency "
        "is applied on charge only, the battery starts every day empty with no end-of-day state-of-charge target, and it may "
        "charge and discharge in the same interval (which burns energy when prices are negative). Prices are 30-minute "
        "averages of the 5-minute settlement price, so intra-half-hour spikes are smoothed out and the true opportunity "
        "is larger than measured. The schedule is fixed once per day at the end of D-1 and never re-optimised intraday, "
        "whereas a real operator rebids through the day using AEMO pre-dispatch forecasts, demand, weather and "
        "interconnector data, none of which are used here (features are lagged prices and calendar only). "
        "Forecasts are point forecasts with no uncertainty, so the schedule cannot hedge against spikes. Results come from "
        f"one {result['Z_test_days']}-day test window. SA1 revenue is dominated by a few extreme-price days, so the capture "
        "rate moves a lot from quarter to quarter (table above) and should be read as indicative rather than precise.",
        "",
    ]
    (C.RESULTS_DIR / "REPORT.md").write_text("\n".join(lines))
