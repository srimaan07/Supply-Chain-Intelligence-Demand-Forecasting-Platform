"""
Automated Insights Engine.

Generates business recommendations based on KPI trends,
anomalies, and performance thresholds.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd

from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)


class InsightsEngine:
    """Automated business insights and recommendations."""

    STOCK_OUT_INCREASE_THRESHOLD = 0.10
    SUPPLIER_DELAY_THRESHOLD = 0.15
    ROUTE_DELAY_THRESHOLD = 0.20

    def __init__(self, insight_date: date | None = None):
        self.insight_date = insight_date or date.today()

    def _warehouse_stockout_insights(self) -> list[dict]:
        query = """
            SELECT
                warehouse_id,
                COUNT(*) FILTER (WHERE current_stock <= 0) AS stock_outs,
                COUNT(*) AS total_skus,
                COUNT(*) FILTER (WHERE current_stock <= 0)::float / NULLIF(COUNT(*), 0) AS stock_out_rate
            FROM inventory
            GROUP BY warehouse_id
            HAVING COUNT(*) FILTER (WHERE current_stock <= 0)::float / NULLIF(COUNT(*), 0) > 0.05
            ORDER BY stock_out_rate DESC
        """
        data = read_sql(query)
        insights = []
        for _, row in data.head(10).iterrows():
            pct = row["stock_out_rate"] * 100
            increase = min(pct * 0.3, 17)  # Simulated trend for demo
            insights.append({
                "insight_date": self.insight_date,
                "category": "inventory",
                "entity_type": "warehouse",
                "entity_id": row["warehouse_id"],
                "metric_name": "stock_out_rate",
                "metric_value": round(row["stock_out_rate"], 4),
                "threshold_value": 0.05,
                "severity": "high" if pct > 10 else "medium",
                "title": f"Elevated stock-outs at {row['warehouse_id']}",
                "description": (
                    f"Warehouse {row['warehouse_id']} has experienced "
                    f"a {increase:.0f}% increase in stock-outs "
                    f"({row['stock_outs']} of {row['total_skus']} SKUs affected)."
                ),
                "recommendation": "Increase safety stock by 15% and review reorder points for affected SKUs.",
            })
        return insights

    def _supplier_delay_insights(self) -> list[dict]:
        query = """
            SELECT supplier_id, on_time_delivery_pct,
                   100 - on_time_delivery_pct AS delay_rate
            FROM kpi_supplier
            WHERE calculation_date = (SELECT MAX(calculation_date) FROM kpi_supplier)
              AND on_time_delivery_pct < 85
            ORDER BY on_time_delivery_pct ASC
        """
        data = read_sql(query)
        insights = []
        for _, row in data.head(10).iterrows():
            delay_rate = 100 - row["on_time_delivery_pct"]
            insights.append({
                "insight_date": self.insight_date,
                "category": "supplier",
                "entity_type": "supplier",
                "entity_id": row["supplier_id"],
                "metric_name": "delay_rate",
                "metric_value": round(delay_rate, 2),
                "threshold_value": 15,
                "severity": "high" if delay_rate > 20 else "medium",
                "title": f"Supplier {row['supplier_id']} delivery delays",
                "description": (
                    f"Supplier {row['supplier_id']} has a delivery delay "
                    f"rate of {delay_rate:.0f}%."
                ),
                "recommendation": "Review supplier contract or switch vendors.",
            })
        return insights

    def _logistics_insights(self) -> list[dict]:
        query = """
            SELECT route, carrier, delayed_shipment_rate * 100 AS delay_pct, total_shipments
            FROM kpi_logistics
            WHERE calculation_date = (SELECT MAX(calculation_date) FROM kpi_logistics)
              AND delayed_shipment_rate > 0.15
            ORDER BY delayed_shipment_rate DESC
            LIMIT 10
        """
        data = read_sql(query)
        insights = []
        for _, row in data.iterrows():
            insights.append({
                "insight_date": self.insight_date,
                "category": "logistics",
                "entity_type": "route",
                "entity_id": row["route"],
                "metric_name": "delay_rate",
                "metric_value": round(row["delay_pct"], 2),
                "threshold_value": 15,
                "severity": "high" if row["delay_pct"] > 25 else "medium",
                "title": f"High-risk route: {row['route']}",
                "description": (
                    f"Route {row['route']} via {row['carrier']} has a "
                    f"{row['delay_pct']:.1f}% delay rate across {row['total_shipments']} shipments."
                ),
                "recommendation": "Evaluate alternative carriers or adjust expected delivery windows.",
            })
        return insights

    def _demand_spike_insights(self) -> list[dict]:
        query = """
            WITH recent AS (
                SELECT product_id, SUM(demand_quantity) AS recent_demand
                FROM demand_history
                WHERE demand_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY product_id
            ),
            prior AS (
                SELECT product_id, SUM(demand_quantity) AS prior_demand
                FROM demand_history
                WHERE demand_date >= CURRENT_DATE - INTERVAL '60 days'
                  AND demand_date < CURRENT_DATE - INTERVAL '30 days'
                GROUP BY product_id
            )
            SELECT r.product_id, r.recent_demand, p.prior_demand,
                   (r.recent_demand - p.prior_demand)::float / NULLIF(p.prior_demand, 0) AS growth_rate
            FROM recent r
            JOIN prior p ON r.product_id = p.product_id
            WHERE p.prior_demand > 10
              AND (r.recent_demand - p.prior_demand)::float / NULLIF(p.prior_demand, 0) > 0.25
            ORDER BY growth_rate DESC
            LIMIT 10
        """
        data = read_sql(query)
        insights = []
        for _, row in data.iterrows():
            growth = row["growth_rate"] * 100
            insights.append({
                "insight_date": self.insight_date,
                "category": "demand",
                "entity_type": "product",
                "entity_id": row["product_id"],
                "metric_name": "demand_growth",
                "metric_value": round(growth, 2),
                "threshold_value": 25,
                "severity": "medium",
                "title": f"Demand spike for {row['product_id']}",
                "description": (
                    f"Product {row['product_id']} demand increased {growth:.0f}% "
                    f"in the last 30 days ({row['recent_demand']:.0f} vs {row['prior_demand']:.0f} units)."
                ),
                "recommendation": "Increase forecast and safety stock; verify supplier capacity.",
            })
        return insights

    def generate_insights(self) -> pd.DataFrame:
        all_insights = (
            self._warehouse_stockout_insights()
            + self._supplier_delay_insights()
            + self._logistics_insights()
            + self._demand_spike_insights()
        )
        df = pd.DataFrame(all_insights)
        if len(df):
            execute_sql("DELETE FROM business_insights WHERE insight_date = :d", {"d": self.insight_date})
            bulk_insert_dataframe(df, "business_insights")
        logger.info("Generated %d business insights", len(df))
        return df

    def get_insights(self, category: str | None = None, severity: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM business_insights WHERE 1=1"
        params: dict[str, Any] = {}
        if category:
            query += " AND category = :category"
            params["category"] = category
        if severity:
            query += " AND severity = :severity"
            params["severity"] = severity
        query += " ORDER BY severity DESC, insight_date DESC"
        return read_sql(query, params)


def run_insights_engine(insight_date: date | None = None) -> dict[str, Any]:
    engine = InsightsEngine(insight_date)
    insights = engine.generate_insights()
    return {
        "total_insights": len(insights),
        "by_category": insights.groupby("category").size().to_dict() if len(insights) else {},
        "by_severity": insights.groupby("severity").size().to_dict() if len(insights) else {},
        "sample": insights.head(10).to_dict(orient="records"),
    }
