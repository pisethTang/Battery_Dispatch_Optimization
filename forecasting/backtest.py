"""Walk-forward backtest of day-ahead price forecasts fed into the battery LP.

    python -m forecasting.backtest            # full run: validation -> freeze -> test -> report
    python -m forecasting.backtest --reuse-validation   # skip tuning, reuse results/validation.json

Stages
1. Split by time: train = start .. val_start-1, validation = 3 months before the test period,
   test = final TEST_DAYS days. During tuning the price matrix is truncated at the test start,
   so the test period is not merely unused but physically absent.
2. Validation: every candidate config runs the same walk-forward procedure as the test
   (expanding window, retrain every RETRAIN_EVERY_DAYS) over the validation months; the config
   with the best validation capture rate is frozen and written to results/validation.json.
3. Test: frozen configs, expanding-window retrain every RETRAIN_EVERY_DAYS days on all data before
   the retrain date, then forecast each day of that block one day ahead.
4. Each day: LP on actual prices (perfect foresight) and on each forecast; forecast schedules
   are scored at actual prices. Capture rate = sum(realised) / sum(perfect foresight).
"""

import argparse
import json
import time

import numpy as np
import pandas as pd

from forecasting import config as C
from forecasting.data import daily_matrix, gap_report, load_prices
from forecasting.economics import capture_rate, realised_profit, schedule
from forecasting.models import build

LGBM_GRID = [
    {"transform": t, "objective": o, "num_leaves": nl, "train_start": ts}
    for (t, o) in [("identity", "l2"), ("identity", "huber"), ("asinh", "l2")]
    for nl in (15, 63)
    for ts in ("2019-01-01", "2021-10-01")  # all history vs. five-minute-settlement era only
]
LSTM_GRID = [
    {"transform": t, "loss": l, "hidden": h}
    for (t, l) in [("identity", "mse"), ("identity", "huber"), ("asinh", "mse")]
    for h in (32, 64)
]
GRIDS = {"naive": [{}], "lightgbm": LGBM_GRID, "lstm": LSTM_GRID}
ML_MODELS = ["lightgbm", "lstm"]
FORECAST_MODELS = ["naive", *ML_MODELS]


def split(P: pd.DataFrame) -> dict[str, pd.Timestamp]:
    last = P.index[-1]
    test_start = last - pd.Timedelta(days=C.TEST_DAYS - 1)
    val_start = test_start - pd.DateOffset(months=C.VALIDATION_MONTHS)
    return {"data_start": P.index[0], "val_start": val_start, "test_start": test_start, "test_end": last}


def complete_days(P: pd.DataFrame, start, end) -> pd.DatetimeIndex:
    days = P.index[(P.index >= start) & (P.index <= end)]
    return days[P.loc[days].notna().all(axis=1).to_numpy()]


def walk_forward(name: str, cfg: dict, P: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[dict, list]:
    """Expanding-window retrain every RETRAIN_EVERY_DAYS; forecast each day one day ahead."""
    forecasts, fits = {}, []
    block_start = days[0]
    while block_start <= days[-1]:
        block_end = block_start + pd.Timedelta(days=C.RETRAIN_EVERY_DAYS)
        block = days[(days >= block_start) & (days < block_end)]
        model = build(name, cfg).fit(P, cutoff=block_start)
        trained_through = getattr(model, "trained_through", None)
        assert trained_through is None or trained_through < block_start, "training saw a forecast day"
        preds = model.predict(P, block)
        forecasts.update(zip(block, preds))
        fits.append({
            "retrain_date": block_start.strftime("%Y-%m-%d"),
            "trained_through": trained_through.strftime("%Y-%m-%d") if trained_through is not None else None,
            "rounds_or_epochs": getattr(model, "num_rounds", getattr(model, "num_epochs", None)),
        })
        block_start = block_end
    return forecasts, fits


def score(P: pd.DataFrame, days, forecasts: dict, pf_cache: dict) -> dict:
    realised, perfect, errors = [], [], []
    for d in days:
        actual = P.loc[d].to_numpy()
        if d not in pf_cache:
            s = schedule(actual)
            pf_cache[d] = (s, realised_profit(s["charge_mw"], s["discharge_mw"], actual).sum())
        s = schedule(forecasts[d])
        realised.append(realised_profit(s["charge_mw"], s["discharge_mw"], actual).sum())
        perfect.append(pf_cache[d][1])
        errors.append(forecasts[d] - actual)
    e = np.concatenate(errors)
    return {
        "capture_rate": capture_rate(sum(realised), sum(perfect)),
        "realised_aud": float(sum(realised)),
        "perfect_foresight_aud": float(sum(perfect)),
        "mae": float(np.abs(e).mean()),
        "rmse": float(np.sqrt((e ** 2).mean())),
    }


def validate(P: pd.DataFrame, s: dict) -> dict:
    P_tune = P[P.index < s["test_start"]]  # the test period does not exist during tuning
    val_days = complete_days(P_tune, s["val_start"], s["test_start"] - pd.Timedelta(days=1))
    pf_cache, out = {}, {}
    for name in FORECAST_MODELS:
        candidates = []
        for cfg in GRIDS[name]:
            t0 = time.time()
            forecasts, _ = walk_forward(name, cfg, P_tune, val_days)
            m = score(P_tune, val_days, forecasts, pf_cache)
            candidates.append({"config": cfg, **m})
            print(f"  [val] {name:8s} {json.dumps(cfg):95s} capture={m['capture_rate']:.3f} "
                  f"mae={m['mae']:.1f} rmse={m['rmse']:.1f} ({time.time() - t0:.0f}s)")
        best = max(candidates, key=lambda c: c["capture_rate"])
        out[name] = {"chosen": best["config"], "candidates": candidates}
    return {
        "selection_metric": "validation capture rate (aggregate realised / perfect foresight)",
        "validation_days": len(val_days),
        "validation_period": [val_days[0].strftime("%Y-%m-%d"), val_days[-1].strftime("%Y-%m-%d")],
        "models": out,
    }


def run_test(P: pd.DataFrame, s: dict, chosen: dict) -> tuple[dict, dict, dict]:
    test_days = complete_days(P, s["test_start"], s["test_end"])
    forecasts, fits = {}, {}
    for name in FORECAST_MODELS:
        t0 = time.time()
        forecasts[name], fits[name] = walk_forward(name, chosen[name], P, test_days)
        print(f"  [test] {name} forecasts done ({time.time() - t0:.0f}s)")

    C.DAILY_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    slots = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    for i, d in enumerate(test_days):
        actual = P.loc[d].to_numpy()
        price_inputs = {"perfect_foresight": actual, **{n: forecasts[n][d] for n in FORECAST_MODELS}}
        methods, row = {}, {"date": d.strftime("%Y-%m-%d"), "price_max": float(actual.max()), "price_min": float(actual.min())}
        for method, prices in price_inputs.items():
            sch = schedule(prices)
            profit = realised_profit(sch["charge_mw"], sch["discharge_mw"], actual)
            methods[method] = {
                "charge_mw": sch["charge_mw"].tolist(),
                "discharge_mw": sch["discharge_mw"].tolist(),
                "soc_mwh": sch["soc_mwh"].tolist(),
                "cumulative_profit_aud": np.round(np.cumsum(profit), 2).tolist(),
                "profit_aud": round(float(profit.sum()), 2),
            }
            row[f"{method}_aud"] = float(profit.sum())
            if method != "perfect_foresight":
                row[f"{method}_abs_err"] = float(np.abs(prices - actual).sum())
                row[f"{method}_sq_err"] = float(((prices - actual) ** 2).sum())
        day_json = {
            "date": row["date"],
            "intervals": slots,
            "actual_price": np.round(actual, 2).tolist(),
            "forecast_price": {n: np.round(forecasts[n][d], 2).tolist() for n in FORECAST_MODELS},
            "methods": methods,
        }
        (C.DAILY_DIR / f"{row['date']}.json").write_text(json.dumps(day_json))
        rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"  [test] scored {i + 1}/{len(test_days)} days")
    return pd.DataFrame(rows), forecasts, fits


def summarise(daily: pd.DataFrame) -> dict:
    n_intervals = len(daily) * C.INTERVALS_PER_DAY
    pf = daily["perfect_foresight_aud"].sum()
    models = {}
    for n in FORECAST_MODELS:
        models[n] = {
            "capture_rate": float(daily[f"{n}_aud"].sum() / pf),
            "realised_aud": float(daily[f"{n}_aud"].sum()),
            "mae": float(daily[f"{n}_abs_err"].sum() / n_intervals),
            "rmse": float(np.sqrt(daily[f"{n}_sq_err"].sum() / n_intervals)),
            "days_with_loss": int((daily[f"{n}_aud"] < 0).sum()),
        }
    q = pd.PeriodIndex(pd.to_datetime(daily["date"]), freq="Q").astype(str)
    quarterly = []
    for quarter, g in daily.groupby(q):
        entry = {"quarter": quarter, "days": len(g), "perfect_foresight_aud": float(g["perfect_foresight_aud"].sum())}
        for n in FORECAST_MODELS:
            entry[f"{n}_capture_rate"] = float(g[f"{n}_aud"].sum() / g["perfect_foresight_aud"].sum())
        quarterly.append(entry)
    best_ml = max(ML_MODELS, key=lambda n: models[n]["capture_rate"])
    return {"perfect_foresight_aud": float(pf), "models": models, "quarterly": quarterly, "best_ml_model": best_ml}


def day_index(daily: pd.DataFrame, best: str) -> dict:
    """Small index for the API/React picker; 'best'/'worst' use the best ML model's daily capture
    on days where perfect foresight earned at least $100 (ratios on near-zero days are meaningless)."""
    d = daily.copy()
    d["best_model_capture"] = d[f"{best}_aud"] / d["perfect_foresight_aud"]
    eligible = d[d["perfect_foresight_aud"] >= 100]
    cols = ["date", "price_max", "price_min", "perfect_foresight_aud", *[f"{n}_aud" for n in FORECAST_MODELS]]
    return {
        "best_model": best,
        "best_day": eligible.loc[eligible["best_model_capture"].idxmax(), "date"],
        "worst_day": eligible.loc[eligible["best_model_capture"].idxmin(), "date"],
        "biggest_spike_day": d.loc[d["price_max"].idxmax(), "date"],
        "definitions": {
            "best_day": f"highest {best} capture rate among days where perfect foresight earned >= $100",
            "worst_day": f"lowest {best} capture rate among days where perfect foresight earned >= $100",
            "biggest_spike_day": "highest actual 30-minute price",
        },
        "days": d[cols].round(2).to_dict(orient="records"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-validation", action="store_true", help="reuse results/validation.json instead of re-tuning")
    args = parser.parse_args()
    np.random.seed(C.SEED)
    t_start = time.time()

    df = load_prices()
    P = daily_matrix(df)
    s = split(P)
    print("split:", {k: v.strftime("%Y-%m-%d") for k, v in s.items()})

    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    val_path = C.RESULTS_DIR / "validation.json"
    if args.reuse_validation and val_path.exists():
        validation = json.loads(val_path.read_text())
        print("reusing", val_path)
    else:
        print("validation (test period excluded from the data)...")
        validation = validate(P, s)
        val_path.write_text(json.dumps(validation, indent=2))
    chosen = {n: validation["models"][n]["chosen"] for n in FORECAST_MODELS}
    print("frozen configs:", chosen)

    print("test...")
    daily, forecasts, fits = run_test(P, s, chosen)
    summary = summarise(daily)
    index = day_index(daily, summary["best_ml_model"])
    (C.DAILY_DIR / "index.json").write_text(json.dumps(index))

    gaps = gap_report(df)
    result = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "data": {
            "source": "AEMO NEMWeb aggregated price and demand, SA1 (5-min RRP averaged to 30-min; pre-Oct-2021 native 30-min)",
            "timezone": "NEM market time (AEST, UTC+10, no daylight saving); intervals labelled by start",
            **{k: v for k, v in gaps.items() if k != "days_with_missing_intervals"},
            "n_days_with_missing_intervals": len(gaps["days_with_missing_intervals"]),
        },
        "battery": {"capacity_mwh": C.BATTERY_CAPACITY_MWH, "max_mw": C.BATTERY_MAX_MW,
                    "efficiency": C.BATTERY_EFFICIENCY, "efficiency_applied_to": "charging only (unchanged app LP)",
                    "start_soc_mwh": 0.0, "interval_hours": C.DT_HOURS},
        "split": {
            "train": [s["data_start"].strftime("%Y-%m-%d"), (s["val_start"] - pd.Timedelta(days=1)).strftime("%Y-%m-%d")],
            "validation": validation["validation_period"],
            "test": [daily["date"].iloc[0], daily["date"].iloc[-1]],
            "retrain_every_days": C.RETRAIN_EVERY_DAYS,
        },
        "Z_test_days": int(len(daily)),
        "chosen_configs": chosen,
        "retrains": fits,
        **summary,
        "X_best_model_capture_pct": round(100 * summary["models"][summary["best_ml_model"]]["capture_rate"]),
        "Y_naive_capture_pct": round(100 * summary["models"]["naive"]["capture_rate"]),
        "runtime_seconds": round(time.time() - t_start),
    }
    (C.RESULTS_DIR / "backtest.json").write_text(json.dumps(result, indent=2))

    from forecasting.report import write_report
    write_report(result, validation, daily, forecasts, P)

    print(json.dumps({k: result[k] for k in ("Z_test_days", "best_ml_model", "X_best_model_capture_pct", "Y_naive_capture_pct")}))
    for n, m in summary["models"].items():
        print(f"  {n:8s} capture={m['capture_rate']:.3f} mae={m['mae']:.1f} rmse={m['rmse']:.1f}")


if __name__ == "__main__":
    main()
