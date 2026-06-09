"""
Supply Chain KPI Engine.

Calculates enterprise KPIs across inventory, supplier, logistics,
and service dimensions and persists to dedicated tables.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

from src.database import bulk_insert_dataframe, execute_sql, read_sql

logger = logging.getLogger(__name__)

CARRYING_COST_RATE = 0.25


class KPIEngine:
    """Calculate and store supply chain KPIs."""

    def __init__(self, calculation_date: date | None = None):
        self.calculation_date = calculation_date or date.today()

    def calculate_inventory_kpis(self) -> pd.DataFrame:
        query = """
            SELECT
                i.warehouse_id,
                i.product_id,
                i.current_stock,
                i.inventory_value,
                i.inventory_turnover,
                i.days_of_inventory,
                i.stock_status,
                p.unit_cost
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
        """
        inv = read_sql(query)
        orders = read_sql("""
            SELECT warehouse_id, product_id, quantity, fill_rate, order_status
            FROM orders
        """)

        stock_outs = inv[inv["current_stock"] <= 0]
        stock_out_rate = len(stock_outs) / max(len(inv), 1)

        delivered = orders[orders["order_status"] == "Delivered"]
        fill_rate = delivered["fill_rate"].mean() if len(delivered) else 0

        records = []
        for wh_id, group in inv.groupby("warehouse_id"):
            wh_orders = delivered[delivered["warehouse_id"] == wh_id]
            wh_stock_out = group[group["current_stock"] <= 0]
            records.append({
                "calculation_date": self.calculation_date,
                "warehouse_id": wh_id,
                "product_id": None,
                "inventory_turnover": group["inventory_turnover"].mean(),
                "days_sales_inventory": group["days_of_inventory"].mean(),
                "carrying_cost": group["inventory_value"].sum() * CARRYING_COST_RATE / 365,
                "inventory_accuracy": 1 - (len(wh_stock_out) / max(len(group), 1)),
                "stock_out_rate": len(wh_stock_out) / max(len(group), 1),
                "fill_rate": wh_orders["fill_rate"].mean() if len(wh_orders) else fill_rate,
                "total_inventory_value": group["inventory_value"].sum(),
            })

        df = pd.DataFrame(records)
        execute_sql("DELETE FROM kpi_inventory WHERE calculation_date = :d", {"d": self.calculation_date})
        bulk_insert_dataframe(df, "kpi_inventory")
        logger.info("Inventory KPIs calculated for %d warehouses", len(df))
        return df

    def calculate_supplier_kpis(self) -> pd.DataFrame:
        query = """
            SELECT
                s.supplier_id,
                s.supplier_name,
                s.reliability_score,
                s.lead_time_days,
                s.defect_rate,
                o.order_id,
                o.is_on_time,
                o.delivery_date,
                o.order_date,
                o.total_amount
            FROM suppliers s
            LEFT JOIN orders o ON s.supplier_id = o.supplier_id
        """
        data = read_sql(query)

        records = []
        for sid, group in data.groupby("supplier_id"):
            orders = group.dropna(subset=["order_id"])
            on_time = orders["is_on_time"].mean() * 100 if len(orders) else group["reliability_score"].iloc[0]
            actual_lt = (
                (orders["delivery_date"] - orders["order_date"]).dt.days.mean()
                if len(orders) and orders["delivery_date"].notna().any()
                else group["lead_time_days"].iloc[0]
            )
            records.append({
                "calculation_date": self.calculation_date,
                "supplier_id": sid,
                "reliability_score": group["reliability_score"].iloc[0],
                "on_time_delivery_pct": round(on_time, 2) if pd.notna(on_time) else 0,
                "avg_lead_time": round(actual_lt, 2) if pd.notna(actual_lt) else 0,
                "defect_rate": group["defect_rate"].iloc[0],
                "total_orders": len(orders),
                "total_spend": orders["total_amount"].sum() if len(orders) else 0,
            })

        df = pd.DataFrame(records)
        df["supplier_rank"] = df["on_time_delivery_pct"].rank(ascending=False, method="min").astype(int)
        execute_sql("DELETE FROM kpi_supplier WHERE calculation_date = :d", {"d": self.calculation_date})
        bulk_insert_dataframe(df, "kpi_supplier")
        logger.info("Supplier KPIs calculated for %d suppliers", len(df))
        return df

    def calculate_logistics_kpis(self) -> pd.DataFrame:
        query = """
            SELECT carrier, route, shipping_cost, delay_days, is_delayed,
                   ship_date, actual_delivery, delivery_status
            FROM logistics
        """
        data = read_sql(query)

        records = []
        for (carrier, route), group in data.groupby(["carrier", "route"]):
            delivered = group[group["actual_delivery"].notna()]
            transit = (
                (delivered["actual_delivery"] - delivered["ship_date"]).dt.days.mean()
                if len(delivered) else 0
            )
            records.append({
                "calculation_date": self.calculation_date,
                "carrier": carrier,
                "route": route,
                "avg_delivery_time": round(transit, 2) if pd.notna(transit) else 0,
                "transportation_cost": group["shipping_cost"].sum(),
                "delayed_shipment_rate": group["is_delayed"].mean(),
                "total_shipments": len(group),
                "on_time_pct": round((1 - group["is_delayed"].mean()) * 100, 2),
            })

        df = pd.DataFrame(records)
        execute_sql("DELETE FROM kpi_logistics WHERE calculation_date = :d", {"d": self.calculation_date})
        bulk_insert_dataframe(df, "kpi_logistics")
        logger.info("Logistics KPIs calculated for %d carrier-route pairs", len(df))
        return df

    def calculate_service_kpis(self) -> pd.DataFrame:
        query = """
            SELECT o.warehouse_id, o.fill_rate, o.order_status,
                   o.delivery_date, o.order_date, i.current_stock, i.reorder_point
            FROM orders o
            LEFT JOIN inventory i ON o.product_id = i.product_id AND o.warehouse_id = i.warehouse_id
        """
        data = read_sql(query)

        records = []
        for wh_id, group in data.groupby("warehouse_id"):
            delivered = group[group["order_status"] == "Delivered"]
            cycle_time = (
                (delivered["delivery_date"] - delivered["order_date"]).dt.days.mean()
                if len(delivered) else 0
            )
            stock_out_freq = (group["current_stock"] <= 0).mean()
            records.append({
                "calculation_date": self.calculation_date,
                "warehouse_id": wh_id,
                "fill_rate": group["fill_rate"].mean(),
                "order_accuracy": 1 - (group["order_status"] == "Returned").mean(),
                "stock_out_frequency": stock_out_freq,
                "avg_order_cycle_time": round(cycle_time, 2) if pd.notna(cycle_time) else 0,
                "customer_satisfaction": max(0, 100 - stock_out_freq * 100 - (1 - group["fill_rate"].mean()) * 50),
            })

        df = pd.DataFrame(records)
        execute_sql("DELETE FROM kpi_service WHERE calculation_date = :d", {"d": self.calculation_date})
        bulk_insert_dataframe(df, "kpi_service")
        logger.info("Service KPIs calculated for %d warehouses", len(df))
        return df

    def calculate_executive_kpis(self) -> pd.DataFrame:
        inv = read_sql("SELECT inventory_value, current_stock FROM inventory")
        products = read_sql("SELECT COUNT(*) as cnt FROM products WHERE is_active = true")
        orders = read_sql("SELECT fill_rate, order_status, total_amount FROM orders")
        supplier = read_sql("SELECT on_time_delivery_pct FROM kpi_supplier WHERE calculation_date = :d",
                           {"d": self.calculation_date})

        stock_out_rate = (inv["current_stock"] <= 0).mean()
        fill_rate = orders[orders["order_status"] == "Delivered"]["fill_rate"].mean()
        revenue = orders[orders["order_status"] == "Delivered"]["total_amount"].sum()

        record = {
            "calculation_date": self.calculation_date,
            "total_products": int(products["cnt"].iloc[0]),
            "total_inventory_value": inv["inventory_value"].sum(),
            "stock_out_rate": stock_out_rate,
            "fill_rate": fill_rate if pd.notna(fill_rate) else 0,
            "forecast_accuracy": 0.85,  # Updated after forecasting runs
            "avg_supplier_reliability": supplier["on_time_delivery_pct"].mean() if len(supplier) else 0,
            "total_orders": len(orders),
            "revenue": revenue,
        }
        df = pd.DataFrame([record])
        execute_sql("DELETE FROM kpi_executive WHERE calculation_date = :d", {"d": self.calculation_date})
        bulk_insert_dataframe(df, "kpi_executive")
        logger.info("Executive KPIs calculated")
        return df

    def run_all(self) -> dict[str, pd.DataFrame]:
        return {
            "inventory": self.calculate_inventory_kpis(),
            "supplier": self.calculate_supplier_kpis(),
            "logistics": self.calculate_logistics_kpis(),
            "service": self.calculate_service_kpis(),
            "executive": self.calculate_executive_kpis(),
        }


def run_kpi_engine(calculation_date: date | None = None) -> dict[str, pd.DataFrame]:
    return KPIEngine(calculation_date).run_all()
