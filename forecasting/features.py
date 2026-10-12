"""Day-ahead features. Decision time is the end of day D-1: every feature for target day D
uses only rows of the daily price matrix strictly before D, plus calendar facts about D itself
(which are known in advance). tests/test_forecasting.py enforces this."""

from functools import lru_cache

import holidays
import numpy as np
import pandas as pd

from forecasting.config import INTERVALS_PER_DAY

LAG_DAYS = (1, 2, 7)
LSTM_LOOKBACK_DAYS = 7


@lru_cache(maxsize=None)
def _sa_holidays(year: int) -> frozenset:
    return frozenset(holidays.Australia(subdiv="SA", years=year).keys())


def is_sa_holiday(day: pd.Timestamp) -> int:
    return int(day.date() in _sa_holidays(day.year))


def check_contiguous(P: pd.DataFrame) -> None:
    expected = pd.date_range(P.index[0], P.index[-1], freq="D")
    if len(expected) != len(P) or not (P.index == expected).all():
        raise ValueError("daily price matrix must have one row per calendar day")


def lgbm_features(P: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """One row per (target day, half-hour slot). P = daily price matrix (days x 48)."""
    check_contiguous(P)
    pos = P.index.get_indexer(days)
    if (pos < max(LAG_DAYS)).any():
        raise ValueError(f"need {max(LAG_DAYS)} days of history before each target day")
    values = P.to_numpy()

    n = len(days)
    slot = np.tile(np.arange(INTERVALS_PER_DAY), n)
    rep = lambda a: np.repeat(np.asarray(a), INTERVALS_PER_DAY)

    feats = {"slot": slot}
    for lag in LAG_DAYS:
        feats[f"lag_{lag}d"] = values[pos - lag].ravel()

    prev = values[pos - 1]  # day D-1, the last complete day at decision time
    feats["d1_mean"] = rep(np.nanmean(prev, axis=1))
    feats["d1_std"] = rep(np.nanstd(prev, axis=1))
    feats["d1_min"] = rep(np.nanmin(prev, axis=1))
    feats["d1_max"] = rep(np.nanmax(prev, axis=1))

    feats["dow"] = rep(days.dayofweek)
    feats["month"] = rep(days.month)
    feats["holiday"] = rep([is_sa_holiday(d) for d in days])

    index = pd.MultiIndex.from_arrays([np.repeat(days, INTERVALS_PER_DAY), slot], names=["day", "slot"])
    return pd.DataFrame(feats, index=index)


def calendar_vector(day: pd.Timestamp) -> np.ndarray:
    """Calendar features of the target day (known in advance): day-of-week one-hot, month sin/cos, holiday."""
    dow = np.zeros(7)
    dow[day.dayofweek] = 1.0
    angle = 2 * np.pi * (day.month - 1) / 12
    return np.concatenate([dow, [np.sin(angle), np.cos(angle), is_sa_holiday(day)]])


def lstm_inputs(P: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Sequence input (n, 7, 48 + 2): the 7 days before D, each step = that day's 48 prices plus its
    day-of-week sin/cos. Calendar input (n, 10) for day D. Prices are raw here; the model transforms them."""
    check_contiguous(P)
    pos = P.index.get_indexer(days)
    if (pos < LSTM_LOOKBACK_DAYS).any():
        raise ValueError(f"need {LSTM_LOOKBACK_DAYS} days of history before each target day")
    values = P.ffill().to_numpy()  # gaps (none in the current cache) are forward-filled for the LSTM only

    seq, cal = [], []
    for p, day in zip(pos, days):
        window = values[p - LSTM_LOOKBACK_DAYS:p]
        window_days = P.index[p - LSTM_LOOKBACK_DAYS:p]
        angle = 2 * np.pi * window_days.dayofweek.to_numpy() / 7
        seq.append(np.column_stack([window, np.sin(angle), np.cos(angle)]))
        cal.append(calendar_vector(day))
    return np.asarray(seq, dtype=np.float32), np.asarray(cal, dtype=np.float32)
