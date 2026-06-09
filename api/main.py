"""FastAPI application for Supply Chain Intelligence Platform."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.database import read_sql
from src.forecasting import run_forecasting
from src.insights_engine import run_insights_engine
from src.inventory_analysis import analyze_inventory
from src.inventory_optimization import run_optimization
from src.kpi_engine import run_kpi_engine
from src.logistics_analysis import analyze_logistics
from src.reporting import generate_reports
from src.supplier_analysis import analyze_suppliers

app = FastAPI(
    title="Supply Chain Intelligence Platform",
    description="Enterprise supply chain analytics, forecasting, and optimization API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    version: str


class KPIResponse(BaseModel):
    data: dict[str, Any]


@app.get("/", tags=["Root"])
def root():
    return {
        "platform": "Supply Chain Intelligence & Demand Forecasting",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "kpis": "/api/kpis/executive",
            "inventory": "/api/inventory/health",
            "suppliers": "/api/suppliers/performance",
            "logistics": "/api/logistics/summary",
            "insights": "/api/insights",
            "forecasts": "/api/forecasts",
            "recommendations": "/api/inventory/recommendations",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    try:
        read_sql("SELECT 1 AS ok")
        return HealthResponse(status="healthy", version="1.0.0")
    except Exception:
        return HealthResponse(status="degraded", version="1.0.0")


# ---- KPI Endpoints ----

@app.get("/api/kpis/executive", tags=["KPIs"])
def get_executive_kpis():
    df = read_sql("SELECT * FROM v_executive_dashboard LIMIT 1")
    if df.empty:
        raise HTTPException(404, "No executive KPIs calculated yet. Run the pipeline first.")
    return df.to_dict(orient="records")[0]


@app.get("/api/kpis/inventory", tags=["KPIs"])
def get_inventory_kpis(warehouse_id: str | None = None):
    query = "SELECT * FROM kpi_inventory WHERE calculation_date = (SELECT MAX(calculation_date) FROM kpi_inventory)"
    if warehouse_id:
        query += f" AND warehouse_id = '{warehouse_id}'"
    return read_sql(query).to_dict(orient="records")


@app.get("/api/kpis/supplier", tags=["KPIs"])
def get_supplier_kpis(top_n: int = Query(20, ge=1, le=100)):
    df = read_sql("""
        SELECT * FROM kpi_supplier
        WHERE calculation_date = (SELECT MAX(calculation_date) FROM kpi_supplier)
        ORDER BY supplier_rank LIMIT :n
    """, {"n": top_n})
    return df.to_dict(orient="records")


@app.get("/api/kpis/logistics", tags=["KPIs"])
def get_logistics_kpis():
    df = read_sql("""
        SELECT * FROM kpi_logistics
        WHERE calculation_date = (SELECT MAX(calculation_date) FROM kpi_logistics)
        ORDER BY delayed_shipment_rate DESC
    """)
    return df.to_dict(orient="records")


# ---- Inventory Endpoints ----

@app.get("/api/inventory/health", tags=["Inventory"])
def inventory_health():
    return analyze_inventory()


@app.get("/api/inventory/alerts", tags=["Inventory"])
def inventory_alerts(severity: str | None = None):
    query = "SELECT * FROM inventory_alerts ORDER BY alert_date DESC"
    if severity:
        query = f"SELECT * FROM inventory_alerts WHERE severity = '{severity}' ORDER BY alert_date DESC"
    return read_sql(query).head(100).to_dict(orient="records")


@app.get("/api/inventory/overstocked", tags=["Inventory"])
def overstocked_items():
    from src.inventory_analysis import InventoryAnalyzer
    return InventoryAnalyzer().get_overstocked_items().head(50).to_dict(orient="records")


@app.get("/api/inventory/understocked", tags=["Inventory"])
def understocked_items():
    from src.inventory_analysis import InventoryAnalyzer
    return InventoryAnalyzer().get_understocked_items().head(50).to_dict(orient="records")


@app.get("/api/inventory/recommendations", tags=["Inventory"])
def inventory_recommendations():
    return run_optimization()


# ---- Supplier Endpoints ----

@app.get("/api/suppliers/performance", tags=["Suppliers"])
def supplier_performance():
    return analyze_suppliers()


@app.get("/api/suppliers/{supplier_id}/scorecard", tags=["Suppliers"])
def supplier_scorecard(supplier_id: str):
    from src.supplier_analysis import SupplierAnalyzer
    return {"scorecard": SupplierAnalyzer().format_scorecard(supplier_id)}


@app.get("/api/suppliers/rankings", tags=["Suppliers"])
def supplier_rankings(top_n: int = Query(20, ge=1, le=100)):
    from src.supplier_analysis import SupplierAnalyzer
    return SupplierAnalyzer().rank_suppliers(top_n).to_dict(orient="records")


# ---- Logistics Endpoints ----

@app.get("/api/logistics/summary", tags=["Logistics"])
def logistics_summary():
    return analyze_logistics()


@app.get("/api/logistics/delayed", tags=["Logistics"])
def delayed_shipments(limit: int = Query(50, ge=1, le=500)):
    from src.logistics_analysis import LogisticsAnalyzer
    return LogisticsAnalyzer().get_delayed_shipments().head(limit).to_dict(orient="records")


# ---- Forecasting Endpoints ----

@app.get("/api/forecasts", tags=["Forecasting"])
def get_forecasts(product_id: str | None = None, horizon: int = Query(3, ge=1, le=12)):
    query = """
        SELECT * FROM forecasts
        WHERE horizon_months = :horizon
    """
    params: dict = {"horizon": horizon}
    if product_id:
        query += " AND product_id = :pid"
        params["pid"] = product_id
    query += " ORDER BY forecast_date LIMIT 500"
    return read_sql(query, params).to_dict(orient="records")


@app.post("/api/forecasts/run", tags=["Forecasting"])
def run_forecast_pipeline(quick: bool = False):
    return run_forecasting(quick=quick)


# ---- Insights Endpoints ----

@app.get("/api/insights", tags=["Insights"])
def get_insights(category: str | None = None, severity: str | None = None):
    from src.insights_engine import InsightsEngine
    df = InsightsEngine().get_insights(category, severity)
    return df.head(50).to_dict(orient="records")


@app.post("/api/insights/generate", tags=["Insights"])
def generate_insights():
    return run_insights_engine()


# ---- Pipeline Endpoints ----

@app.post("/api/pipeline/kpis", tags=["Pipeline"])
def run_kpis():
    return {"status": "success", "kpis": {k: len(v) for k, v in run_kpi_engine().items()}}


@app.post("/api/pipeline/reports", tags=["Pipeline"])
def run_reports():
    return generate_reports()


# ---- Analytics Queries ----

@app.get("/api/analytics/top-products", tags=["Analytics"])
def top_products(limit: int = Query(20, ge=1, le=100)):
    df = read_sql("""
        SELECT p.product_id, p.product_name, p.category,
               SUM(o.quantity) AS total_quantity,
               SUM(o.total_amount) AS total_revenue
        FROM orders o JOIN products p ON o.product_id = p.product_id
        WHERE o.order_status = 'Delivered'
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY total_revenue DESC LIMIT :limit
    """, {"limit": limit})
    return df.to_dict(orient="records")


@app.get("/api/analytics/regional-demand", tags=["Analytics"])
def regional_demand():
    df = read_sql("""
        SELECT customer_region AS region,
               COUNT(*) AS order_count,
               SUM(quantity) AS total_quantity,
               SUM(total_amount) AS total_revenue
        FROM orders WHERE order_status = 'Delivered'
        GROUP BY customer_region ORDER BY total_revenue DESC
    """)
    return df.to_dict(orient="records")
