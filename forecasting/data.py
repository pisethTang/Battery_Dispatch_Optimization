"""Historical SA1 spot prices from AEMO NEMWeb, resampled to 30-minute means.

Why NEMWeb and not Open Electricity: the OE free plan only serves the last 730 days and caps
each 5-minute request to a few days, while the AEMO "Aggregated price and demand" monthly CSVs
go back decades. Both carry the same AEMO dispatch prices (spot-checked: 5-minute values match).

Conventions
- AEMO SETTLEMENTDATE is the END of the interval, in NEM market time (AEST, UTC+10, no DST).
  We relabel every row to its interval START so a day D covers 00:00..23:30 AEST of D.
- 5-minute rows (from 1 Oct 2021, five-minute settlement) are averaged into 30-minute buckets,
  the same mean-resample the live pipeline uses. Older files are already 30-minute.

Run: python -m forecasting.data   (downloads missing months, writes data/sa1_prices.parquet)
"""

import io
import json
import time
from datetime import date

import pandas as pd
import requests

from forecasting.config import HISTORY_START, PRICES_PATH, RAW_DIR, REGION

URL = "https://www.aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_{ym}_{region}.csv"


def _months(start: str, end: date) -> list[str]:
    return [p.strftime("%Y%m") for p in pd.period_range(start, end.strftime("%Y-%m"), freq="M")]


def download_month(ym: str, force: bool = False) -> pd.DataFrame | None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"PRICE_AND_DEMAND_{ym}_{REGION}.csv"
    if force or not path.exists():
        r = requests.get(URL.format(ym=ym, region=REGION), headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
        if r.status_code != 200 or not r.text.startswith("REGION"):
            print(f"  {ym}: not available (HTTP {r.status_code})")
            return None
        path.write_text(r.text)
        time.sleep(0.5)  # be polite to NEMWeb
    return pd.read_csv(path)


def to_30min(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns={"SETTLEMENTDATE": "end", "RRP": "price", "TOTALDEMAND": "demand"})
    df["end"] = pd.to_datetime(df["end"], format="%Y/%m/%d %H:%M:%S")
    df = df.sort_values("end").drop_duplicates("end")

    # interval length from the gap to the previous row: 5 min after 5MS, 30 min before it
    length = df["end"].diff().dt.total_seconds().div(60)
    length = length.where(length.isin([5, 30])).bfill().fillna(5)
    df["start"] = df["end"] - pd.to_timedelta(length, unit="min")

    out = (
        df.set_index("start")[["price", "demand"]]
        .resample("30min")
        .agg(["mean", "count"])
    )
    return pd.DataFrame({
        "price": out[("price", "mean")],
        "demand": out[("demand", "mean")],
        "n_obs": out[("price", "count")],
    })


def build(force_current_month: bool = True) -> pd.DataFrame:
    today = date.today()
    frames = []
    for ym in _months(HISTORY_START, today):
        is_current = ym == today.strftime("%Y%m")
        raw = download_month(ym, force=force_current_month and is_current)
        if raw is not None:
            frames.append(raw)

    df = to_30min(pd.concat(frames, ignore_index=True))

    # keep whole AEST days only, and drop today's (still incomplete) day
    first_day = df.index.min().ceil("D")
    last_day = min((df.index.max() + pd.Timedelta(minutes=30)).floor("D") - pd.Timedelta(days=1),
                   pd.Timestamp(today) - pd.Timedelta(days=1))
    full_index = pd.date_range(first_day, last_day + pd.Timedelta(hours=23, minutes=30), freq="30min", name="interval_start")
    df = df.reindex(full_index)
    df["n_obs"] = df["n_obs"].fillna(0).astype(int)
    # buckets with no observations at all stay NaN (mean of nothing); they are reported, never invented
    df.loc[df["n_obs"] == 0, ["price", "demand"]] = float("nan")
    return df


def gap_report(df: pd.DataFrame) -> dict:
    missing = df["price"].isna()
    expected_obs = pd.Series(6, index=df.index).where(df.index >= pd.Timestamp("2021-10-01 04:00"), 1)
    partial = (df["n_obs"] > 0) & (df["n_obs"] < expected_obs)
    days_with_missing = sorted({d.strftime("%Y-%m-%d") for d in df.index[missing].normalize()})
    return {
        "start": df.index.min().strftime("%Y-%m-%d %H:%M"),
        "end": df.index.max().strftime("%Y-%m-%d %H:%M"),
        "rows": int(len(df)),
        "days": int(len(df) // 48),
        "missing_30min_intervals": int(missing.sum()),
        "partial_30min_intervals": int(partial.sum()),
        "days_with_missing_intervals": days_with_missing,
        "price_min": float(df["price"].min()),
        "price_max": float(df["price"].max()),
        "gap_handling": (
            "30-min buckets are the mean of whatever 5-min observations exist (partial buckets counted above). "
            "Buckets with no observations stay NaN and are never filled in the stored data. Days with any NaN "
            "price are excluded as backtest target days; as model inputs, LightGBM takes NaN natively and the "
            "LSTM forward-fills."
        ),
    }


def load_prices() -> pd.DataFrame:
    return pd.read_parquet(PRICES_PATH)


def daily_matrix(df: pd.DataFrame, column: str = "price") -> pd.DataFrame:
    """Rows = AEST calendar days, columns = 48 half-hour intervals (0 = 00:00-00:30)."""
    s = df[column]
    out = pd.DataFrame({"day": s.index.normalize(), "slot": s.index.hour * 2 + s.index.minute // 30, "v": s.values})
    return out.pivot(index="day", columns="slot", values="v")


if __name__ == "__main__":
    df = build()
    PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PRICES_PATH)
    report = gap_report(df)
    shown = {k: (v if k != "days_with_missing_intervals" else f"{len(v)} days: {v[:10]}{' ...' if len(v) > 10 else ''}") for k, v in report.items()}
    print(json.dumps(shown, indent=2))
    print(f"saved {PRICES_PATH}")
