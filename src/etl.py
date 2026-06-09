"""
ETL Pipeline for Supply Chain Intelligence Platform.

Extract -> Transform -> Load workflow with data quality handling
and derived metric calculation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import get_settings
from src.database import bulk_insert_dataframe, log_etl_audit, truncate_tables

logger = logging.getLogger(__name__)

PIPELINE_NAME = "supply_chain_etl"
CARRYING_COST_RATE = 0.25  # 25% annual carrying cost


class SupplyChainETL:
    """Complete ETL pipeline for supply chain data."""

    def __init__(self, raw_dir: Path | None = None, processed_dir: Path | None = None):
        settings = get_settings()
        self.raw_dir = raw_dir or settings.raw_data_path
        self.processed_dir = processed_dir or settings.processed_data_path
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.stats: dict[str, int] = {}

    def extract(self) -> dict[str, pd.DataFrame]:
        """Load raw CSV datasets."""
        started = datetime.now(timezone.utc)
        datasets = {}
        failed = 0

        for name in [
            "products", "warehouses", "suppliers", "product_suppliers",
            "inventory", "orders", "logistics", "demand_history",
        ]:
            path = self.raw_dir / f"{name}.csv"
            if not path.exists():
                raise FileNotFoundError(f"Missing raw data file: {path}")
            date_cols = {
                "orders": ["order_date", "expected_delivery", "delivery_date"],
                "logistics": ["ship_date", "expected_delivery", "actual_delivery"],
                "demand_history": ["demand_date"],
                "inventory": ["last_restocked"],
            }.get(name, [])
            datasets[name] = pd.read_csv(path, parse_dates=date_cols if date_cols else None)
            logger.info("Extracted %s: %d rows", name, len(datasets[name]))

        log_etl_audit(PIPELINE_NAME, "extract", sum(len(d) for d in datasets.values()), failed, "success", started, datetime.now(timezone.utc))
        return datasets

    def _clean_products(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["product_id"])
        df = df.dropna(subset=["product_id", "product_name", "category", "unit_cost", "selling_price"])
        df["unit_cost"] = df["unit_cost"].clip(lower=0)
        df["selling_price"] = df["selling_price"].clip(lower=df["unit_cost"])
        df["is_active"] = df["is_active"].fillna(True).astype(bool)
        self.stats["products_dropped"] = before - len(df)
        return df

    def _clean_warehouses(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop_duplicates(subset=["warehouse_id"])
        df = df.dropna(subset=["warehouse_id", "location", "capacity_units"])
        df["capacity_units"] = df["capacity_units"].clip(lower=1)
        df["current_utilization"] = df["current_utilization"].clip(0, 1)
        return df

    def _clean_suppliers(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop_duplicates(subset=["supplier_id"])
        df = df.dropna(subset=["supplier_id", "supplier_name", "lead_time_days"])
        df["lead_time_days"] = df["lead_time_days"].clip(lower=0)
        df["reliability_score"] = df["reliability_score"].clip(0, 100)
        df["defect_rate"] = df["defect_rate"].clip(0, 1).fillna(0)
        return df

    def _clean_inventory(self, df: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["product_id", "warehouse_id"])
        df = df.dropna(subset=["product_id", "warehouse_id"])
        df["current_stock"] = df["current_stock"].fillna(0).astype(int).clip(lower=0)
        df["reorder_point"] = df["reorder_point"].fillna(0).astype(int).clip(lower=0)
        df["safety_stock"] = df["safety_stock"].fillna(0).astype(int).clip(lower=0)

        costs = products.set_index("product_id")["unit_cost"]
        df["inventory_value"] = df["product_id"].map(costs) * df["current_stock"]

        # Derived fields computed after orders are available - placeholder
        df["days_of_inventory"] = np.nan
        df["inventory_turnover"] = np.nan
        df["stock_status"] = "Unknown"
        self.stats["inventory_dropped"] = before - len(df)
        return df

    def _clean_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["order_id"])
        df = df.dropna(subset=["order_id", "product_id", "quantity", "order_date"])
        df["quantity"] = df["quantity"].clip(lower=1).astype(int)
        df["fill_rate"] = df["fill_rate"].fillna(1.0).clip(0, 1)

        # Fix date inconsistencies
        mask = df["delivery_date"].notna() & (df["delivery_date"] < df["order_date"])
        df.loc[mask, "delivery_date"] = df.loc[mask, "order_date"]

        mask2 = df["expected_delivery"].notna() & (df["expected_delivery"] < df["order_date"])
        df.loc[mask2, "expected_delivery"] = df.loc[mask2, "order_date"] + pd.Timedelta(days=3)

        df["is_on_time"] = df["is_on_time"].where(df["is_on_time"].notna(), False)
        self.stats["orders_dropped"] = before - len(df)
        return df

    def _clean_logistics(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop_duplicates(subset=["shipment_id"])
        df = df.dropna(subset=["shipment_id", "carrier", "route", "shipping_cost"])
        df["shipping_cost"] = df["shipping_cost"].clip(lower=0)
        df["delay_days"] = df["delay_days"].fillna(0).astype(int).clip(lower=0)
        df["is_delayed"] = df["is_delayed"].fillna(df["delay_days"] > 0)
        return df

    def _clean_demand_history(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.drop_duplicates(subset=["product_id", "warehouse_id", "demand_date"])
        df = df.dropna(subset=["product_id", "demand_date", "demand_quantity"])
        df["demand_quantity"] = df["demand_quantity"].clip(lower=0).astype(int)
        return df

    def _compute_inventory_metrics(
        self, inventory: pd.DataFrame, orders: pd.DataFrame, products: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate inventory turnover, days of inventory, and stock status."""
        annual_demand = (
            orders[orders["order_status"] == "Delivered"]
            .groupby("product_id")["quantity"]
            .sum()
            .reset_index()
        )
        annual_demand["annual_demand"] = annual_demand["quantity"] / 2  # 2 years of data

        inv = inventory.merge(annual_demand[["product_id", "annual_demand"]], on="product_id", how="left")
        inv["annual_demand"] = inv["annual_demand"].fillna(0)

        avg_inventory = inv.groupby("product_id")["current_stock"].transform("mean").replace(0, 1)
        inv["inventory_turnover"] = (inv["annual_demand"] / avg_inventory).round(4)
        inv["days_of_inventory"] = np.where(
            inv["inventory_turnover"] > 0,
            (365 / inv["inventory_turnover"]).round(2),
            999,
        )

        def stock_status(row):
            if row["current_stock"] <= 0:
                return "Stock Out"
            if row["current_stock"] <= row["reorder_point"]:
                return "Reorder Required"
            if row["current_stock"] <= row["safety_stock"]:
                return "Low Stock"
            if row.get("max_stock") and row["current_stock"] > row["max_stock"]:
                return "Overstocked"
            if row["days_of_inventory"] > 180:
                return "Dead Inventory"
            if row["inventory_turnover"] > 12:
                return "Fast Moving"
            return "Healthy"

        inv["stock_status"] = inv.apply(stock_status, axis=1)
        return inv.drop(columns=["annual_demand"], errors="ignore")

    def _add_order_derived_fields(self, orders: pd.DataFrame, suppliers: pd.DataFrame) -> pd.DataFrame:
        """Add lead time variance and fill rate metrics."""
        supplier_lt = suppliers.set_index("supplier_id")["lead_time_days"]
        orders = orders.copy()
        orders["contracted_lead_time"] = orders["supplier_id"].map(supplier_lt)
        orders["actual_lead_time"] = np.where(
            orders["delivery_date"].notna(),
            (orders["delivery_date"] - orders["order_date"]).dt.days,
            np.nan,
        )
        orders["lead_time_variance"] = orders["actual_lead_time"] - orders["contracted_lead_time"]
        return orders

    def transform(self, datasets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Clean data and compute derived fields."""
        started = datetime.now(timezone.utc)
        processed = {}

        processed["products"] = self._clean_products(datasets["products"].copy())
        processed["warehouses"] = self._clean_warehouses(datasets["warehouses"].copy())
        processed["suppliers"] = self._clean_suppliers(datasets["suppliers"].copy())
        processed["product_suppliers"] = datasets["product_suppliers"].drop_duplicates(
            subset=["product_id", "supplier_id"]
        )
        processed["orders"] = self._clean_orders(datasets["orders"].copy())
        processed["orders"] = self._add_order_derived_fields(
            processed["orders"], processed["suppliers"]
        )
        processed["inventory"] = self._clean_inventory(
            datasets["inventory"].copy(), processed["products"]
        )
        processed["inventory"] = self._compute_inventory_metrics(
            processed["inventory"], processed["orders"], processed["products"]
        )
        processed["logistics"] = self._clean_logistics(datasets["logistics"].copy())
        processed["demand_history"] = self._clean_demand_history(datasets["demand_history"].copy())

        # Save processed files
        for name, df in processed.items():
            out_path = self.processed_dir / f"{name}.csv"
            df.to_csv(out_path, index=False)

        total = sum(len(d) for d in processed.values())
        log_etl_audit(PIPELINE_NAME, "transform", total, self.stats.get("orders_dropped", 0), "success", started, datetime.now(timezone.utc))
        logger.info("Transform complete. Stats: %s", self.stats)
        return processed

    def load(self, datasets: dict[str, pd.DataFrame], truncate: bool = True) -> dict[str, int]:
        """Load cleaned data into PostgreSQL."""
        started = datetime.now(timezone.utc)
        load_order = [
            "products", "warehouses", "suppliers", "product_suppliers",
            "inventory", "orders", "logistics", "demand_history",
        ]

        if truncate:
            truncate_tables(load_order)

        counts = {}
        for table in load_order:
            df = datasets[table].copy()
            # Drop columns not in schema
            drop_cols = ["contracted_lead_time", "actual_lead_time", "lead_time_variance"]
            df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
            if "inventory_id" in df.columns and table == "inventory":
                df = df.drop(columns=["inventory_id"])
            counts[table] = bulk_insert_dataframe(df, table)

        log_etl_audit(
            PIPELINE_NAME, "load", sum(counts.values()), 0, "success", started, datetime.now(timezone.utc)
        )
        logger.info("Load complete: %s", counts)
        return counts

    def run(self, truncate: bool = True) -> dict[str, int]:
        """Execute full ETL pipeline."""
        logger.info("Starting ETL pipeline...")
        raw = self.extract()
        processed = self.transform(raw)
        counts = self.load(processed, truncate=truncate)
        logger.info("ETL pipeline completed successfully.")
        return counts


def run_etl(truncate: bool = True) -> dict[str, int]:
    return SupplyChainETL().run(truncate=truncate)
