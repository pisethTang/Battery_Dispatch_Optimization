"""Day-ahead price models. Each model is fitted on target days strictly before a cutoff and then
forecasts any later day D from the daily price matrix, reading only rows before D.

fit(P, cutoff): every training target day is < cutoff. The last ES_DAYS of that window are held out
for early stopping, then the model is refitted on the whole window with the chosen number of
boosting rounds / epochs. The test period is never visible to fit()."""

import copy
import os

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
from torch import nn

from forecasting.config import SEED
from forecasting.features import LAG_DAYS, LSTM_LOOKBACK_DAYS, lgbm_features, lstm_inputs

ES_DAYS = 60  # early-stopping split, taken from the end of each training window
ASINH_SCALE = 50.0  # $/MWh; asinh is ~linear below this and ~log above it


def forward(y: np.ndarray, transform: str) -> np.ndarray:
    return np.arcsinh(y / ASINH_SCALE) if transform == "asinh" else y


def inverse(y: np.ndarray, transform: str) -> np.ndarray:
    return np.sinh(y) * ASINH_SCALE if transform == "asinh" else y


def training_days(P: pd.DataFrame, cutoff: pd.Timestamp, lookback: int, start: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    """Target days usable for training: complete, enough history, and strictly before cutoff."""
    first = P.index[0] + pd.Timedelta(days=lookback)
    if start is not None:
        first = max(first, start)
    days = P.index[(P.index >= first) & (P.index < cutoff)]
    return days[P.loc[days].notna().all(axis=1).to_numpy()]


class NaiveModel:
    """price(D, t) = price(D-1, t)."""

    name = "naive"

    def fit(self, P, cutoff):
        return self

    def predict(self, P: pd.DataFrame, days: pd.DatetimeIndex) -> np.ndarray:
        pos = P.index.get_indexer(days)
        return P.to_numpy()[pos - 1]


class LightGBMModel:
    name = "lightgbm"

    def __init__(self, transform="identity", objective="l2", num_leaves=31, train_start=None, learning_rate=0.05):
        self.transform = transform
        self.objective = objective
        self.num_leaves = num_leaves
        self.train_start = pd.Timestamp(train_start) if train_start else None
        self.params = {
            "objective": "huber" if objective == "huber" else "regression",
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "min_data_in_leaf": 100,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 1,
            "lambda_l2": 1.0,
            "seed": SEED,
            "deterministic": True,
            "force_row_wise": True,
            "num_threads": min(8, os.cpu_count() or 1),
            "verbose": -1,
        }
        if objective == "huber":
            # huber delta in target units: $/MWh for raw prices, ~1 for asinh
            self.params["alpha"] = 50.0 if transform == "identity" else 1.0

    def _xy(self, P, days):
        X = lgbm_features(P, days)
        y = forward(P.loc[days].to_numpy().ravel(), self.transform)
        return X, y

    def fit(self, P: pd.DataFrame, cutoff: pd.Timestamp):
        days = training_days(P, cutoff, max(LAG_DAYS), self.train_start)
        fit_days, es_days = days[:-ES_DAYS], days[-ES_DAYS:]
        X_fit, y_fit = self._xy(P, fit_days)
        X_es, y_es = self._xy(P, es_days)
        probe = lgb.train(
            self.params, lgb.Dataset(X_fit, y_fit), num_boost_round=3000,
            valid_sets=[lgb.Dataset(X_es, y_es)],
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        self.num_rounds = max(probe.best_iteration, 1)
        X, y = self._xy(P, days)
        self.booster = lgb.train(self.params, lgb.Dataset(X, y), num_boost_round=self.num_rounds)
        self.trained_through = days[-1]
        return self

    def predict(self, P: pd.DataFrame, days: pd.DatetimeIndex) -> np.ndarray:
        pred = self.booster.predict(lgbm_features(P, days))
        return inverse(pred, self.transform).reshape(len(days), -1)


class _Net(nn.Module):
    def __init__(self, n_seq_features: int, n_cal: int, hidden: int, n_out: int = 48):
        super().__init__()
        self.lstm = nn.LSTM(n_seq_features, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden + n_cal, 128), nn.ReLU(), nn.Linear(128, n_out))

    def forward(self, seq, cal):
        _, (h, _) = self.lstm(seq)
        return self.head(torch.cat([h[-1], cal], dim=1))


class LSTMModel:
    name = "lstm"

    def __init__(self, transform="asinh", loss="mse", hidden=32, max_epochs=300, patience=25, batch_size=64, lr=1e-3):
        self.transform = transform
        self.loss = loss
        self.hidden = hidden
        self.max_epochs = max_epochs
        self.patience = patience
        self.batch_size = batch_size
        self.lr = lr

    def _prep(self, P, days):
        seq, cal = lstm_inputs(P, days)
        seq[:, :, :48] = (forward(seq[:, :, :48], self.transform) - self.mu) / self.sigma
        return torch.from_numpy(seq), torch.from_numpy(cal)

    def _target(self, P, days):
        y = (forward(P.loc[days].to_numpy(), self.transform) - self.mu) / self.sigma
        return torch.from_numpy(y.astype(np.float32))

    def _train(self, seq, cal, y, epochs, val=None):
        torch.manual_seed(SEED)
        net = _Net(seq.shape[2], cal.shape[1], self.hidden)
        opt = torch.optim.Adam(net.parameters(), lr=self.lr)
        loss_fn = nn.HuberLoss(delta=1.0) if self.loss == "huber" else nn.MSELoss()
        gen = torch.Generator().manual_seed(SEED)
        best, best_epoch, best_state = float("inf"), 0, None
        for epoch in range(1, epochs + 1):
            net.train()
            for idx in torch.randperm(len(y), generator=gen).split(self.batch_size):
                opt.zero_grad()
                loss = loss_fn(net(seq[idx], cal[idx]), y[idx])
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
            if val is not None:
                net.eval()
                with torch.no_grad():
                    v = loss_fn(net(val[0], val[1]), val[2]).item()
                if v < best:
                    best, best_epoch, best_state = v, epoch, copy.deepcopy(net.state_dict())
                elif epoch - best_epoch >= self.patience:
                    break
        if val is not None:
            net.load_state_dict(best_state)
        return net, best_epoch

    def fit(self, P: pd.DataFrame, cutoff: pd.Timestamp):
        torch.set_num_threads(min(8, os.cpu_count() or 1))
        days = training_days(P, cutoff, LSTM_LOOKBACK_DAYS)
        fit_days, es_days = days[:-ES_DAYS], days[-ES_DAYS:]
        # scaling statistics come from the training targets only
        t = forward(P.loc[fit_days].to_numpy(), self.transform)
        self.mu, self.sigma = float(t.mean()), float(t.std())

        seq, cal = self._prep(P, fit_days)
        es_seq, es_cal = self._prep(P, es_days)
        _, self.num_epochs = self._train(seq, cal, self._target(P, fit_days), self.max_epochs,
                                         val=(es_seq, es_cal, self._target(P, es_days)))
        self.num_epochs = max(self.num_epochs, 1)

        t = forward(P.loc[days].to_numpy(), self.transform)
        self.mu, self.sigma = float(t.mean()), float(t.std())
        seq, cal = self._prep(P, days)
        self.net, _ = self._train(seq, cal, self._target(P, days), self.num_epochs)
        self.trained_through = days[-1]
        return self

    def predict(self, P: pd.DataFrame, days: pd.DatetimeIndex) -> np.ndarray:
        self.net.eval()
        seq, cal = self._prep(P, days)
        with torch.no_grad():
            out = self.net(seq, cal).numpy().astype(np.float64)
        return inverse(out * self.sigma + self.mu, self.transform)


def build(name: str, config: dict):
    return {"naive": NaiveModel, "lightgbm": LightGBMModel, "lstm": LSTMModel}[name](**config)
