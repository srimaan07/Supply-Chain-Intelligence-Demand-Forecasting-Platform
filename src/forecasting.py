"""
Demand Forecasting Module.

Implements multiple forecasting models:
- Linear Regression
- Random Forest
- XGBoost
- Facebook Prophet

Evaluates with RMSE, MAE, MAPE and selects best model.
"""

from __future__ import annotations

import json
import logging
import warnings
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from src.config import PROJECT_ROOT, get_settings
from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning)


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


class DemandForecaster:
    """Multi-model demand forecasting engine."""

    HORIZONS = [3, 6, 12]

    def __init__(self, models_dir: Path | None = None):
        self.models_dir = models_dir or (PROJECT_ROOT / "models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.best_model_name: str | None = None
        self.metrics: dict[str, dict[str, float]] = {}

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["demand_date"] = pd.to_datetime(df["demand_date"])
        df = df.sort_values("demand_date")
        df["year"] = df["demand_date"].dt.year
        df["month"] = df["demand_date"].dt.month
        df["day_of_week"] = df["demand_date"].dt.dayofweek
        df["week_of_year"] = df["demand_date"].dt.isocalendar().week.astype(int)
        df["quarter"] = df["demand_date"].dt.quarter
        return df

    def _aggregate_demand(self, level: str = "product") -> pd.DataFrame:
        if level == "product":
            query = """
                SELECT product_id, demand_date, SUM(demand_quantity) AS demand
                FROM demand_history GROUP BY product_id, demand_date
            """
        elif level == "warehouse":
            query = """
                SELECT warehouse_id, demand_date, SUM(demand_quantity) AS demand
                FROM demand_history GROUP BY warehouse_id, demand_date
            """
        else:
            query = """
                SELECT region, demand_date, SUM(demand_quantity) AS demand
                FROM demand_history GROUP BY region, demand_date
            """
        return read_sql(query)

    def _build_monthly_series(self, df: pd.DataFrame, id_col: str) -> pd.DataFrame:
        df["demand_date"] = pd.to_datetime(df["demand_date"])
        monthly = (
            df.groupby([id_col, pd.Grouper(key="demand_date", freq="MS")])["demand"]
            .sum()
            .reset_index()
        )
        return monthly

    def _create_lag_features(self, df: pd.DataFrame, id_col: str) -> pd.DataFrame:
        df = df.sort_values([id_col, "demand_date"])
        for lag in [1, 2, 3, 6, 12]:
            df[f"lag_{lag}"] = df.groupby(id_col)["demand"].shift(lag)
        df["rolling_mean_3"] = df.groupby(id_col)["demand"].transform(
            lambda x: x.rolling(3, min_periods=1).mean()
        )
        df["rolling_mean_6"] = df.groupby(id_col)["demand"].transform(
            lambda x: x.rolling(6, min_periods=1).mean()
        )
        df["month"] = df["demand_date"].dt.month
        df["quarter"] = df["demand_date"].dt.quarter
        return df.dropna()

    def _evaluate_model(self, name: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "mape": mape(y_true, y_pred),
        }
        self.metrics[name] = metrics
        return metrics

    def train_ml_models(self, sample_size: int = 50_000) -> dict[str, Any]:
        """Train sklearn/XGBoost models on aggregated demand."""
        raw = self._aggregate_demand("product")
        monthly = self._build_monthly_series(raw, "product_id")
        featured = self._create_lag_features(monthly, "product_id")

        feature_cols = [c for c in featured.columns if c.startswith(("lag_", "rolling_", "month", "quarter"))]
        X = featured[feature_cols].values
        y = featured["demand"].values

        if len(X) > sample_size:
            idx = np.random.default_rng(get_settings().random_seed).choice(len(X), sample_size, replace=False)
            X, y = X[idx], y[idx]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=get_settings().random_seed
        )

        models = {
            "linear_regression": LinearRegression(),
            "random_forest": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
            "xgboost": XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1),
        }

        results = {}
        for name, model in models.items():
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            preds = np.clip(preds, 0, None)
            metrics = self._evaluate_model(name, y_test, preds)
            results[name] = metrics
            logger.info("%s - RMSE: %.2f, MAE: %.2f, MAPE: %.2f%%", name, metrics["rmse"], metrics["mae"], metrics["mape"])

        self.best_model_name = min(results, key=lambda k: results[k]["mape"])
        logger.info("Best ML model: %s", self.best_model_name)

        with open(self.models_dir / "forecast_metrics.json", "w") as f:
            json.dump({"models": results, "best_model": self.best_model_name}, f, indent=2)

        return results

    def train_prophet(self, top_n_products: int = 20) -> dict[str, float]:
        """Train Prophet on top demand products."""
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("Prophet not available")
            return {}

        raw = self._aggregate_demand("product")
        top_products = (
            raw.groupby("product_id")["demand"].sum().nlargest(top_n_products).index.tolist()
        )

        all_preds, all_actual = [], []
        for pid in top_products[:10]:
            pdf = raw[raw["product_id"] == pid].copy()
            monthly = self._build_monthly_series(pdf.assign(product_id=pid), "product_id")
            if len(monthly) < 12:
                continue

            prophet_df = monthly.rename(columns={"demand_date": "ds", "demand": "y"})[["ds", "y"]]
            train_size = int(len(prophet_df) * 0.8)
            train, test = prophet_df.iloc[:train_size], prophet_df.iloc[train_size:]

            model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
            model.fit(train)
            future = model.make_future_dataframe(periods=len(test), freq="MS")
            forecast = model.predict(future)
            preds = forecast.iloc[train_size : train_size + len(test)]["yhat"].values
            actual = test["y"].values
            all_preds.extend(preds)
            all_actual.extend(actual)

        if all_preds:
            metrics = self._evaluate_model("prophet", np.array(all_actual), np.array(all_preds))
            logger.info("Prophet - RMSE: %.2f, MAE: %.2f, MAPE: %.2f%%", metrics["rmse"], metrics["mae"], metrics["mape"])
            return metrics
        return {}

    def generate_forecasts(self, horizons: list[int] | None = None) -> pd.DataFrame:
        """Generate forecasts for products and store in database."""
        horizons = horizons or self.HORIZONS
        raw = self._aggregate_demand("product")
        monthly = self._build_monthly_series(raw, "product_id")
        featured = self._create_lag_features(monthly, "product_id")

        feature_cols = [c for c in featured.columns if c.startswith(("lag_", "rolling_", "month", "quarter"))]
        model = XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1)
        model.fit(featured[feature_cols], featured["demand"])

        top_products = featured.groupby("product_id")["demand"].sum().nlargest(100).index.tolist()
        forecast_date = date.today()
        records = []

        for pid in top_products:
            pdf = featured[featured["product_id"] == pid].sort_values("demand_date")
            if pdf.empty:
                continue
            last_row = pdf.iloc[-1]
            last_date = last_row["demand_date"]

            for horizon in horizons:
                for m in range(1, horizon + 1):
                    fdate = last_date + pd.DateOffset(months=m)
                    X_pred = last_row[feature_cols].values.reshape(1, -1)
                    pred = max(0, float(model.predict(X_pred)[0]))
                    records.append({
                        "product_id": pid,
                        "warehouse_id": None,
                        "region": None,
                        "forecast_date": fdate.date(),
                        "horizon_months": horizon,
                        "model_name": "xgboost",
                        "predicted_demand": round(pred, 2),
                        "lower_bound": round(pred * 0.85, 2),
                        "upper_bound": round(pred * 1.15, 2),
                        "rmse": self.metrics.get("xgboost", {}).get("rmse"),
                        "mae": self.metrics.get("xgboost", {}).get("mae"),
                        "mape": self.metrics.get("xgboost", {}).get("mape"),
                    })

        df = pd.DataFrame(records)
        if len(df):
            execute_sql("DELETE FROM forecasts WHERE forecast_date >= :d", {"d": forecast_date})
            bulk_insert_dataframe(df, "forecasts")
        logger.info("Generated %d forecast records", len(df))
        return df

    def run(self, quick: bool = False) -> dict[str, Any]:
        sample = 10_000 if quick else 50_000
        ml_results = self.train_ml_models(sample_size=sample)
        prophet_results = {} if quick else self.train_prophet()
        forecasts = self.generate_forecasts()

        all_metrics = {**ml_results}
        if prophet_results:
            all_metrics["prophet"] = prophet_results
            if prophet_results.get("mape", 999) < ml_results.get(self.best_model_name, {}).get("mape", 999):
                self.best_model_name = "prophet"

        return {
            "metrics": all_metrics,
            "best_model": self.best_model_name,
            "forecasts_generated": len(forecasts),
        }


def run_forecasting(quick: bool = False) -> dict[str, Any]:
    return DemandForecaster().run(quick=quick)
