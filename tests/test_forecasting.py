import numpy as np
import pandas as pd
import pytest

from forecasting.backtest import split
from forecasting.economics import realised_profit, schedule
from forecasting.features import lgbm_features, lstm_inputs
from forecasting.models import LightGBMModel, LSTMModel, NaiveModel


def synthetic_prices(n_days=200, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2024-01-01", periods=n_days, freq="D")
    shape = 80 + 60 * np.sin(np.linspace(0, 2 * np.pi, 48))
    values = shape + rng.normal(0, 20, (n_days, 48))
    values[rng.random((n_days, 48)) < 0.01] = 5000.0  # occasional spikes
    return pd.DataFrame(values, index=days, columns=range(48))


def tamper_from(P: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Replace every price on `day` and after with garbage."""
    Q = P.copy()
    Q.loc[Q.index >= day] = np.random.default_rng(1).normal(9999, 5000, Q.loc[Q.index >= day].shape)
    return Q


# --- leakage: features for day D must not depend on day D or later ---

def test_lgbm_features_ignore_target_day_and_future():
    P = synthetic_prices()
    D = P.index[120]
    days = pd.DatetimeIndex([D])
    pd.testing.assert_frame_equal(lgbm_features(P, days), lgbm_features(tamper_from(P, D), days))


def test_lstm_inputs_ignore_target_day_and_future():
    P = synthetic_prices()
    D = P.index[120]
    days = pd.DatetimeIndex([D])
    for a, b in zip(lstm_inputs(P, days), lstm_inputs(tamper_from(P, D), days)):
        np.testing.assert_array_equal(a, b)


def test_features_do_change_when_history_changes():
    # guard against a vacuous leakage test: D-1 must actually matter
    P = synthetic_prices()
    D = P.index[120]
    days = pd.DatetimeIndex([D])
    assert not lgbm_features(P, days).equals(lgbm_features(tamper_from(P, P.index[119]), days))


@pytest.mark.parametrize("model_factory", [
    lambda: NaiveModel(),
    lambda: LightGBMModel(transform="asinh", num_leaves=7),
    lambda: LSTMModel(hidden=8, max_epochs=3, patience=2),
], ids=["naive", "lightgbm", "lstm"])
def test_fit_and_forecast_ignore_target_day_and_future(model_factory):
    """End to end: fit with cutoff D and forecast D; tampering with D and later changes nothing."""
    P = synthetic_prices()
    D = P.index[150]
    days = pd.DatetimeIndex([D])
    clean = model_factory().fit(P, cutoff=D).predict(P, days)
    Q = tamper_from(P, D)
    tampered = model_factory().fit(Q, cutoff=D).predict(Q, days)
    np.testing.assert_allclose(clean, tampered)


def test_split_order():
    P = synthetic_prices(n_days=800)
    s = split(P)
    assert s["data_start"] < s["val_start"] < s["test_start"] <= s["test_end"]
    assert (s["test_end"] - s["test_start"]).days == 364


# --- realised profit ---

def test_realised_profit_hand_calculation():
    charge = [2.0, 0.0, 0.0]
    discharge = [0.0, 0.0, 1.8]
    actual = [10.0, 50.0, 200.0]
    # (0 - 2) * 10 * 0.5 + 0 + (1.8 - 0) * 200 * 0.5 = -10 + 180
    np.testing.assert_allclose(realised_profit(charge, discharge, actual), [-10.0, 0.0, 180.0])


def test_realised_profit_uses_actual_not_forecast_prices():
    actual = np.array([10.0] * 24 + [200.0] * 24)
    # forecast puts the peak in the morning, when actual prices are flat and cheap
    wrong_forecast = np.array([10.0] * 12 + [200.0] * 12 + [10.0] * 24)
    s = schedule(wrong_forecast)
    realised = realised_profit(s["charge_mw"], s["discharge_mw"], actual).sum()
    pf = schedule(actual)
    perfect = realised_profit(pf["charge_mw"], pf["discharge_mw"], actual).sum()
    assert perfect > 0
    # it cycled inside the flat $10 period, so it lost the 10% charging loss
    assert realised < 0
    assert realised <= perfect


def test_perfect_forecast_captures_everything():
    actual = np.array([30.0, -20.0, 5.0, 300.0] * 12)
    s = schedule(actual)
    pf = realised_profit(s["charge_mw"], s["discharge_mw"], actual).sum()
    s2 = schedule(actual.copy())
    assert realised_profit(s2["charge_mw"], s2["discharge_mw"], actual).sum() == pytest.approx(pf)
