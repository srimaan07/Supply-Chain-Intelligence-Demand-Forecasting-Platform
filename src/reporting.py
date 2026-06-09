"""
Reporting Module.

Generates executive reports, summary statistics,
and resume-ready deliverables.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import PROJECT_ROOT
from src.database import read_sql

logger = logging.getLogger(__name__)

RESUME_BULLETS = [
    "Developed a Supply Chain Intelligence Platform using Python, SQL, PostgreSQL, and Power BI, analyzing over 500K supply chain transactions across 10,000+ products, 120 suppliers, and 25 warehouses.",
    "Built end-to-end ETL pipelines with Pandas processing 520K+ order records, implementing data quality checks for missing values, duplicates, negative stock, and date inconsistencies.",
    "Designed and implemented a KPI engine tracking 20+ enterprise metrics including inventory turnover, days sales of inventory, fill rate, stock-out rate, and supplier on-time delivery.",
    "Built demand forecasting models using Linear Regression, Random Forest, XGBoost, and Facebook Prophet, evaluating performance with RMSE, MAE, and MAPE metrics.",
    "Implemented inventory optimization algorithms calculating EOQ, safety stock, and reorder quantities, reducing stock-out risks through predictive analytics.",
    "Created 40+ advanced SQL analytics queries utilizing window functions, CTEs, cohort analysis, and ranking for warehouse, supplier, and logistics performance analysis.",
    "Designed executive Power BI dashboards with drill-down capabilities tracking inventory health, supplier scorecards, logistics efficiency, and demand forecasts.",
    "Developed a FastAPI REST API exposing supply chain analytics endpoints with automated business insights and recommendation engine.",
    "Containerized the entire platform using Docker and Docker Compose with PostgreSQL, enabling reproducible deployment for portfolio demonstration.",
    "Implemented automated insights engine generating actionable recommendations for stock-out prevention, supplier contract review, and route optimization.",
]


class ReportGenerator:
    """Generate reports and portfolio deliverables."""

    def __init__(self, reports_dir: Path | None = None):
        self.reports_dir = reports_dir or (PROJECT_ROOT / "reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def executive_summary(self) -> dict[str, Any]:
        try:
            exec_kpi = read_sql(
                "SELECT * FROM kpi_executive ORDER BY calculation_date DESC LIMIT 1"
            )
            inventory = read_sql("SELECT COUNT(*) as cnt, SUM(inventory_value) as val FROM inventory")
            orders = read_sql("SELECT COUNT(*) as cnt FROM orders")
            insights = read_sql("SELECT COUNT(*) as cnt FROM business_insights")

            return {
                "report_date": date.today().isoformat(),
                "executive_kpis": exec_kpi.to_dict(orient="records")[0] if len(exec_kpi) else {},
                "inventory_records": int(inventory["cnt"].iloc[0]),
                "total_inventory_value": float(inventory["val"].iloc[0]) if inventory["val"].iloc[0] else 0,
                "total_orders": int(orders["cnt"].iloc[0]),
                "active_insights": int(insights["cnt"].iloc[0]),
            }
        except Exception as e:
            logger.warning("Could not generate executive summary: %s", e)
            return {"report_date": date.today().isoformat(), "status": "pending_data_load"}

    def generate_resume_bullets(self) -> str:
        content = "# Resume Bullets - Supply Chain Intelligence Platform\n\n"
        content += "## ATS-Friendly Bullet Points\n\n"
        for bullet in RESUME_BULLETS:
            content += f"- {bullet}\n"
        content += "\n## Skills Demonstrated\n\n"
        content += "- **Languages:** Python, SQL\n"
        content += "- **Frameworks:** FastAPI, Pandas, Scikit-learn, XGBoost, Prophet\n"
        content += "- **Databases:** PostgreSQL\n"
        content += "- **BI Tools:** Power BI, Plotly\n"
        content += "- **DevOps:** Docker, Git\n"
        content += "- **Domains:** Supply Chain Analytics, Demand Forecasting, Inventory Optimization\n"

        path = self.reports_dir / "resume_bullets.md"
        path.write_text(content)
        logger.info("Resume bullets saved to %s", path)
        return content

    def generate_data_dictionary(self) -> str:
        tables = [
            ("products", "Product master data with pricing and categorization"),
            ("warehouses", "Warehouse locations, capacity, and utilization"),
            ("suppliers", "Supplier profiles with lead times and reliability scores"),
            ("inventory", "Current stock levels with reorder points and derived metrics"),
            ("orders", "Order transactions with delivery and fill rate data"),
            ("logistics", "Shipment tracking with carrier and route information"),
            ("demand_history", "Daily demand aggregates for forecasting"),
            ("kpi_inventory", "Warehouse-level inventory KPIs"),
            ("kpi_supplier", "Supplier performance KPIs with rankings"),
            ("kpi_logistics", "Carrier and route logistics KPIs"),
            ("forecasts", "Demand forecast outputs from ML models"),
            ("inventory_recommendations", "EOQ and reorder optimization recommendations"),
            ("business_insights", "Automated actionable business insights"),
        ]
        content = "# Data Dictionary\n\n"
        for table, desc in tables:
            content += f"## {table}\n{desc}\n\n"

        path = self.reports_dir / "data_dictionary.md"
        path.write_text(content)
        return content

    def save_executive_report(self) -> Path:
        summary = self.executive_summary()
        content = f"# Executive Summary Report\n\n"
        content += f"Generated: {datetime.utcnow().isoformat()}Z\n\n"
        for key, value in summary.items():
            content += f"- **{key.replace('_', ' ').title()}:** {value}\n"

        path = self.reports_dir / "executive_summary.md"
        path.write_text(content)
        return path

    def run_all(self) -> dict[str, Any]:
        return {
            "executive_summary": self.executive_summary(),
            "resume_bullets": self.generate_resume_bullets(),
            "data_dictionary": self.generate_data_dictionary(),
            "executive_report_path": str(self.save_executive_report()),
        }


def generate_reports() -> dict[str, Any]:
    return ReportGenerator().run_all()
