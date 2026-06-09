"""
Logistics Intelligence Module.

Analyzes shipment delays, delivery performance, transportation
costs, and route efficiency with optimization recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.database import read_sql

logger = logging.getLogger(__name__)


class LogisticsAnalyzer:
    """Logistics and transportation analytics."""

    def get_logistics_summary(self) -> pd.DataFrame:
        return read_sql("SELECT * FROM v_logistics_summary ORDER BY delay_rate_pct DESC")

    def get_delayed_shipments(self) -> pd.DataFrame:
        query = """
            SELECT l.*, o.product_id, w.warehouse_name
            FROM logistics l
            LEFT JOIN orders o ON l.order_id = o.order_id
            LEFT JOIN warehouses w ON l.origin_warehouse = w.warehouse_id
            WHERE l.is_delayed = true
            ORDER BY l.delay_days DESC
        """
        return read_sql(query)

    def get_high_risk_routes(self, delay_threshold: float = 20) -> pd.DataFrame:
        summary = self.get_logistics_summary()
        return summary[summary["delay_rate_pct"] >= delay_threshold].sort_values(
            "delay_rate_pct", ascending=False
        )

    def get_expensive_routes(self, top_n: int = 20) -> pd.DataFrame:
        summary = self.get_logistics_summary()
        return summary.nlargest(top_n, "avg_shipping_cost")

    def get_carrier_performance(self) -> pd.DataFrame:
        query = """
            SELECT
                carrier,
                COUNT(*) AS total_shipments,
                AVG(shipping_cost) AS avg_cost,
                SUM(shipping_cost) AS total_cost,
                AVG(delay_days) AS avg_delay,
                AVG(CASE WHEN is_delayed THEN 1.0 ELSE 0.0 END) * 100 AS delay_rate_pct,
                AVG(actual_delivery - ship_date) AS avg_transit_days
            FROM logistics
            GROUP BY carrier
            ORDER BY delay_rate_pct ASC
        """
        return read_sql(query)

    def generate_recommendations(self) -> list[dict[str, Any]]:
        recommendations = []
        high_risk = self.get_high_risk_routes()
        expensive = self.get_expensive_routes(10)
        carriers = self.get_carrier_performance()

        for _, route in high_risk.head(5).iterrows():
            recommendations.append({
                "type": "route_delay",
                "entity": route["route"],
                "carrier": route["carrier"],
                "metric": f"{route['delay_rate_pct']:.1f}% delay rate",
                "recommendation": (
                    f"Route {route['route']} via {route['carrier']} has a "
                    f"{route['delay_rate_pct']:.1f}% delay rate. Consider alternative carriers or routes."
                ),
                "priority": "high",
            })

        for _, route in expensive.head(3).iterrows():
            recommendations.append({
                "type": "cost_optimization",
                "entity": route["route"],
                "carrier": route["carrier"],
                "metric": f"${route['avg_shipping_cost']:.2f} avg cost",
                "recommendation": (
                    f"Route {route['route']} has high transportation costs "
                    f"(${route['avg_shipping_cost']:.2f}/shipment). Negotiate rates or consolidate shipments."
                ),
                "priority": "medium",
            })

        if len(carriers) > 1:
            best = carriers.iloc[0]
            worst = carriers.iloc[-1]
            if worst["delay_rate_pct"] - best["delay_rate_pct"] > 10:
                recommendations.append({
                    "type": "carrier_switch",
                    "entity": worst["carrier"],
                    "metric": f"{worst['delay_rate_pct']:.1f}% delay vs {best['carrier']} at {best['delay_rate_pct']:.1f}%",
                    "recommendation": (
                        f"Consider shifting volume from {worst['carrier']} to {best['carrier']} "
                        f"to reduce delays by ~{worst['delay_rate_pct'] - best['delay_rate_pct']:.1f}%."
                    ),
                    "priority": "high",
                })

        return recommendations

    def summary(self) -> dict[str, Any]:
        summary = self.get_logistics_summary()
        delayed = self.get_delayed_shipments()
        return {
            "total_shipments": int(summary["total_shipments"].sum()),
            "total_shipping_cost": float(summary["total_shipping_cost"].sum()),
            "avg_delay_rate_pct": float(summary["delay_rate_pct"].mean()),
            "delayed_shipments": len(delayed),
            "high_risk_routes": len(self.get_high_risk_routes()),
            "carriers_used": len(self.get_carrier_performance()),
        }


def analyze_logistics() -> dict[str, Any]:
    analyzer = LogisticsAnalyzer()
    return {
        "summary": analyzer.summary(),
        "recommendations": analyzer.generate_recommendations(),
        "high_risk_routes": analyzer.get_high_risk_routes().head(10).to_dict(orient="records"),
        "carrier_performance": analyzer.get_carrier_performance().to_dict(orient="records"),
    }
