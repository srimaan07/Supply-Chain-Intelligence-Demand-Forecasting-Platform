"""
Inventory Optimization Engine.

Calculates recommended stock levels, reorder quantities,
safety stock, and Economic Order Quantity (EOQ).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)

ORDERING_COST = 50.0  # Fixed cost per order
HOLDING_COST_RATE = 0.25  # Annual holding cost as fraction of unit cost


class InventoryOptimizer:
    """Inventory optimization using forecast output and EOQ formulas."""

    def __init__(self, recommendation_date: date | None = None):
        self.recommendation_date = recommendation_date or date.today()

    def calculate_eoq(self, annual_demand: float, unit_cost: float, ordering_cost: float = ORDERING_COST) -> int:
        if annual_demand <= 0 or unit_cost <= 0:
            return 0
        holding_cost = unit_cost * HOLDING_COST_RATE
        eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
        return max(int(round(eoq)), 1)

    def calculate_safety_stock(self, avg_demand: float, lead_time_days: int, service_level: float = 0.95) -> int:
        z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
        z = z_scores.get(service_level, 1.65)
        demand_std = avg_demand * 0.3  # Assume 30% coefficient of variation
        safety = z * demand_std * np.sqrt(lead_time_days / 30)
        return max(int(round(safety)), 0)

    def generate_recommendations(self) -> pd.DataFrame:
        inventory = read_sql("""
            SELECT i.*, p.unit_cost, p.product_name, s.lead_time_days
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            LEFT JOIN product_suppliers ps ON i.product_id = ps.product_id AND ps.is_primary = true
            LEFT JOIN suppliers s ON ps.supplier_id = s.supplier_id
        """)

        demand = read_sql("""
            SELECT product_id, warehouse_id,
                   AVG(demand_quantity) AS avg_daily_demand,
                   SUM(demand_quantity) AS total_demand
            FROM demand_history
            GROUP BY product_id, warehouse_id
        """)

        forecasts = read_sql("""
            SELECT product_id, AVG(predicted_demand) AS expected_monthly_demand
            FROM forecasts WHERE horizon_months = 3
            GROUP BY product_id
        """)

        inv = inventory.merge(
            demand, on=["product_id", "warehouse_id"], how="left"
        ).merge(
            forecasts, on="product_id", how="left"
        )

        inv["avg_daily_demand"] = inv["avg_daily_demand"].fillna(1)
        inv["total_demand"] = inv["total_demand"].fillna(0)
        inv["expected_monthly_demand"] = inv["expected_monthly_demand"].fillna(inv["avg_daily_demand"] * 30)
        inv["lead_time_days"] = inv["lead_time_days"].fillna(7)

        records = []
        for _, row in inv.iterrows():
            annual_demand = row["avg_daily_demand"] * 365
            eoq = self.calculate_eoq(annual_demand, row["unit_cost"])
            safety = self.calculate_safety_stock(
                row["avg_daily_demand"], int(row["lead_time_days"])
            )
            reorder_point = int(row["avg_daily_demand"] * row["lead_time_days"] + safety)
            expected_demand = row["expected_monthly_demand"] * 3  # 3-month horizon

            if row["current_stock"] <= reorder_point:
                recommended = max(eoq, int(expected_demand - row["current_stock"] + safety))
                priority = "critical" if row["current_stock"] <= 0 else "high"
            elif row["current_stock"] <= row["reorder_point"]:
                recommended = eoq
                priority = "medium"
            else:
                recommended = 0
                priority = "low"

            if recommended > 0:
                records.append({
                    "product_id": row["product_id"],
                    "warehouse_id": row["warehouse_id"],
                    "recommendation_date": self.recommendation_date,
                    "current_stock": int(row["current_stock"]),
                    "recommended_reorder": recommended,
                    "expected_demand": round(expected_demand, 2),
                    "safety_stock": safety,
                    "eoq": eoq,
                    "reorder_point": reorder_point,
                    "priority": priority,
                    "status": "pending",
                })

        df = pd.DataFrame(records)
        if len(df):
            execute_sql(
                "DELETE FROM inventory_recommendations WHERE recommendation_date = :d",
                {"d": self.recommendation_date},
            )
            bulk_insert_dataframe(df, "inventory_recommendations")
        logger.info("Generated %d inventory optimization recommendations", len(df))
        return df

    def format_recommendation(self, product_id: str, warehouse_id: str) -> str:
        query = """
            SELECT r.*, p.product_name FROM inventory_recommendations r
            JOIN products p ON r.product_id = p.product_id
            WHERE r.product_id = :pid AND r.warehouse_id = :wid
            ORDER BY r.recommendation_date DESC LIMIT 1
        """
        result = read_sql(query, {"pid": product_id, "wid": warehouse_id})
        if result.empty:
            return f"No recommendation for {product_id} at {warehouse_id}"

        row = result.iloc[0]
        return (
            f"Product ID: {row['product_id']}\n"
            f"Product: {row['product_name']}\n"
            f"Warehouse: {row['warehouse_id']}\n\n"
            f"Recommended Reorder: {row['recommended_reorder']} Units\n"
            f"Expected Demand: {row['expected_demand']:.0f} Units\n"
            f"Safety Stock: {row['safety_stock']} Units\n"
            f"EOQ: {row['eoq']} Units\n"
            f"Priority: {row['priority']}"
        )

    def summary(self) -> dict[str, Any]:
        recs = read_sql(
            "SELECT * FROM inventory_recommendations WHERE recommendation_date = :d",
            {"d": self.recommendation_date},
        )
        if recs.empty:
            recs = self.generate_recommendations()
        return {
            "total_recommendations": len(recs),
            "critical": len(recs[recs["priority"] == "critical"]),
            "high_priority": len(recs[recs["priority"] == "high"]),
            "total_reorder_units": int(recs["recommended_reorder"].sum()) if len(recs) else 0,
        }


def run_optimization(recommendation_date: date | None = None) -> dict[str, Any]:
    optimizer = InventoryOptimizer(recommendation_date)
    recs = optimizer.generate_recommendations()
    return {
        "summary": optimizer.summary(),
        "recommendations_count": len(recs),
        "sample_recommendations": recs.head(10).to_dict(orient="records"),
    }
