"""Leakage-aware chronological model evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit

from .features import MODEL_FEATURES


def chronological_folds(data: pd.DataFrame, n_splits: int = 4):
    """Yield expanding folds with training targets ending before test features begin."""
    dates = np.array(sorted(data["date"].dropna().astype(str).unique()))
    if len(dates) <= n_splits:
        raise ValueError(f"Need more than {n_splits} distinct dates; found {len(dates)}.")
    splitter = TimeSeriesSplit(n_splits=n_splits)
    for train_idx, test_idx in splitter.split(dates):
        train_dates, test_dates = set(dates[train_idx]), set(dates[test_idx])
        train = data[data["date"].astype(str).isin(train_dates)].copy()
        test = data[data["date"].astype(str).isin(test_dates)].copy()
        first_test_date = str(test["date"].astype(str).min())
        if "next_date" in train:
            train = train.loc[train["next_date"].astype(str).lt(first_test_date)].copy()
        yield train, test


def _model():
    return make_pipeline(SimpleImputer(strategy="constant", fill_value=0), StandardScaler(), Ridge(alpha=1.0))


def evaluate_oos(data: pd.DataFrame, n_splits: int = 4):
    """Return fold metrics and out-of-sample predictions; compares to zero-return baseline."""
    labeled = data.dropna(subset=["target_return"]).copy()
    predictions = []
    metrics = []
    for fold_no, (train, test) in enumerate(chronological_folds(labeled, n_splits=n_splits), start=1):
        train = train.dropna(subset=["target_return"])
        test = test.dropna(subset=["target_return"])
        if train.empty or test.empty:
            continue
        model = _model()
        model.fit(train[MODEL_FEATURES], train["target_return"])
        pred = model.predict(test[MODEL_FEATURES])
        fold_predictions = test[["ticker", "date", "next_date", "close", "target_close", "target_return"]].copy()
        fold_predictions["predicted_return"] = pred
        fold_predictions["predicted_close"] = fold_predictions["close"] * np.exp(pred)
        fold_predictions["fold"] = fold_no
        predictions.append(fold_predictions)
        actual = test["target_return"].to_numpy(dtype=float)
        metrics.append({
            "fold": fold_no, "train_end": str(train["date"].max()),
            "test_start": str(test["date"].min()), "test_end": str(test["date"].max()),
            "n_test": int(len(test)), "mae_return": float(np.mean(np.abs(actual - pred))),
            "zero_baseline_mae": float(np.mean(np.abs(actual))),
            "directional_accuracy": float(np.mean(np.sign(actual) == np.sign(pred))),
        })
    if not predictions:
        raise ValueError("No out-of-sample folds produced predictions.")
    return pd.DataFrame(metrics), pd.concat(predictions, ignore_index=True)


def forecast_latest(data: pd.DataFrame) -> pd.DataFrame:
    """Fit on labeled history strictly before each latest, unlabeled row."""
    ordered = data.sort_values(["ticker", "date"])
    latest = ordered.groupby("ticker", as_index=False).tail(1).copy()
    if latest.empty:
        raise ValueError("Need an unlabeled/latest row to forecast.")
    if latest["target_return"].notna().any():
        raise ValueError("Latest row must be unlabeled; refusing an in-sample forecast.")
    cutoff = str(latest["date"].astype(str).min())
    labeled = data.loc[data["target_return"].notna() & data["date"].astype(str).lt(cutoff)].copy()
    if labeled.empty:
        raise ValueError("No labeled historical rows exist before the unlabeled latest row.")
    model = _model()
    model.fit(labeled[MODEL_FEATURES], labeled["target_return"])
    latest["predicted_return"] = model.predict(latest[MODEL_FEATURES])
    latest["predicted_close"] = latest["close"] * np.exp(latest["predicted_return"])
    return latest[["ticker", "date", "close", "predicted_return", "predicted_close"]].reset_index(drop=True)
