"""
Inventory Intelligence Module.

Analyzes inventory health, generates alerts, and provides
reorder recommendations.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)


class InventoryAnalyzer:
    """Inventory health analysis and alert generation."""

    def __init__(self, analysis_date: date | None = None):
        self.analysis_date = analysis_date or date.today()

    def get_inventory_health(self) -> pd.DataFrame:
        return read_sql("SELECT * FROM v_inventory_health ORDER BY health_status, warehouse_id")

    def get_overstocked_items(self, threshold_days: float = 180) -> pd.DataFrame:
        query = """
            SELECT * FROM v_inventory_health
            WHERE health_status IN ('Overstocked', 'Dead Inventory')
               OR days_of_inventory > :threshold
            ORDER BY inventory_value DESC
        """
        return read_sql(query, {"threshold": threshold_days})

    def get_understocked_items(self) -> pd.DataFrame:
        query = """
            SELECT * FROM v_inventory_health
            WHERE health_status IN ('Stock Out', 'Reorder Required', 'Low Stock')
            ORDER BY
                CASE health_status
                    WHEN 'Stock Out' THEN 1
                    WHEN 'Reorder Required' THEN 2
                    WHEN 'Low Stock' THEN 3
                    ELSE 4
                END,
                current_stock ASC
        """
        return read_sql(query)

    def get_dead_inventory(self, days_threshold: float = 180) -> pd.DataFrame:
        query = """
            SELECT * FROM v_inventory_health
            WHERE days_of_inventory > :days OR health_status = 'Dead Inventory'
            ORDER BY days_of_inventory DESC
        """
        return read_sql(query, {"days": days_threshold})

    def get_fast_moving_products(self, turnover_threshold: float = 12) -> pd.DataFrame:
        query = """
            SELECT * FROM v_inventory_health
            WHERE inventory_turnover > :threshold OR health_status = 'Fast Moving'
            ORDER BY inventory_turnover DESC
        """
        return read_sql(query, {"threshold": turnover_threshold})

    def generate_alerts(self) -> pd.DataFrame:
        understocked = self.get_understocked_items()
        alerts = []

        for _, row in understocked.iterrows():
            if row["health_status"] == "Stock Out":
                alert_type, severity = "STOCK_OUT", "critical"
                message = (
                    f"Product {row['product_name']} ({row['product_id']}) is OUT OF STOCK "
                    f"at {row['warehouse_name']} ({row['warehouse_id']})."
                )
            elif row["health_status"] == "Reorder Required":
                alert_type, severity = "REORDER_REQUIRED", "high"
                message = (
                    f"Product {row['product_name']} ({row['product_id']})\n"
                    f"Current Stock: {row['current_stock']}\n"
                    f"Reorder Point: {row['reorder_point']}\n"
                    f"Status: Reorder Required"
                )
            else:
                alert_type, severity = "LOW_STOCK", "medium"
                message = (
                    f"Product {row['product_name']} at {row['warehouse_name']} "
                    f"has low stock ({row['current_stock']} units)."
                )

            alerts.append({
                "alert_date": self.analysis_date,
                "product_id": row["product_id"],
                "warehouse_id": row["warehouse_id"],
                "alert_type": alert_type,
                "current_stock": row["current_stock"],
                "reorder_point": row["reorder_point"],
                "message": message,
                "severity": severity,
            })

        df = pd.DataFrame(alerts)
        if len(df):
            execute_sql("DELETE FROM inventory_alerts WHERE alert_date = :d", {"d": self.analysis_date})
            bulk_insert_dataframe(df, "inventory_alerts")
        logger.info("Generated %d inventory alerts", len(df))
        return df

    def get_recommendations(self) -> list[dict[str, Any]]:
        understocked = self.get_understocked_items()
        recommendations = []
        for _, row in understocked.head(50).iterrows():
            reorder_qty = max(
                int(row["reorder_point"] - row["current_stock"] + row["safety_stock"]),
                row["safety_stock"],
            )
            recommendations.append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "warehouse_id": row["warehouse_id"],
                "current_stock": int(row["current_stock"]),
                "reorder_point": int(row["reorder_point"]),
                "recommended_reorder": reorder_qty,
                "status": row["health_status"],
                "priority": "critical" if row["health_status"] == "Stock Out" else "high",
            })
        return recommendations

    def summary(self) -> dict[str, Any]:
        health = self.get_inventory_health()
        return {
            "total_skus": len(health),
            "stock_outs": len(health[health["health_status"] == "Stock Out"]),
            "reorder_required": len(health[health["health_status"] == "Reorder Required"]),
            "overstocked": len(health[health["health_status"].isin(["Overstocked", "Dead Inventory"])]),
            "fast_moving": len(health[health["health_status"] == "Fast Moving"]),
            "healthy": len(health[health["health_status"] == "Healthy"]),
            "total_inventory_value": float(health["inventory_value"].sum()),
        }


def analyze_inventory(analysis_date: date | None = None) -> dict[str, Any]:
    analyzer = InventoryAnalyzer(analysis_date)
    alerts = analyzer.generate_alerts()
    return {
        "summary": analyzer.summary(),
        "alerts_count": len(alerts),
        "recommendations": analyzer.get_recommendations()[:20],
    }
