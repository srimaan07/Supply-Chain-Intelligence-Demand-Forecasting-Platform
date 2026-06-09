#!/usr/bin/env python3
"""
Master pipeline runner for Supply Chain Intelligence Platform.

Usage:
    python scripts/run_pipeline.py --full
    python scripts/run_pipeline.py --quick
    python scripts/run_pipeline.py --etl-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_generator import generate_sample_data
from src.etl import run_etl
from src.forecasting import run_forecasting
from src.insights_engine import run_insights_engine
from src.inventory_analysis import analyze_inventory
from src.inventory_optimization import run_optimization
from src.kpi_engine import run_kpi_engine
from src.logistics_analysis import analyze_logistics
from src.reporting import generate_reports
from src.supplier_analysis import analyze_suppliers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def run_full_pipeline(quick: bool = False) -> dict:
    logger.info("=" * 60)
    logger.info("SUPPLY CHAIN INTELLIGENCE PLATFORM - FULL PIPELINE")
    logger.info("=" * 60)

    logger.info("Phase 1: Generating synthetic data...")
    datasets = generate_sample_data(quick=quick)
    logger.info("Generated %d datasets", len(datasets))

    logger.info("Phase 2: Running ETL pipeline...")
    etl_counts = run_etl()
    logger.info("ETL complete: %s", etl_counts)

    logger.info("Phase 3: Calculating KPIs...")
    kpis = run_kpi_engine()

    logger.info("Phase 4: Inventory analysis...")
    inventory = analyze_inventory()

    logger.info("Phase 5: Supplier analysis...")
    suppliers = analyze_suppliers()

    logger.info("Phase 6: Logistics analysis...")
    logistics = analyze_logistics()

    logger.info("Phase 7: Demand forecasting...")
    forecasts = run_forecasting(quick=quick)

    logger.info("Phase 8: Inventory optimization...")
    optimization = run_optimization()

    logger.info("Phase 9: Generating insights...")
    insights = run_insights_engine()

    logger.info("Phase 10: Generating reports...")
    reports = generate_reports()

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)

    return {
        "etl": etl_counts,
        "kpis": {k: len(v) for k, v in kpis.items()},
        "inventory": inventory["summary"],
        "suppliers": suppliers["summary"],
        "logistics": logistics["summary"],
        "forecasts": forecasts,
        "optimization": optimization["summary"],
        "insights": insights,
        "reports": reports,
    }


def main():
    parser = argparse.ArgumentParser(description="Supply Chain Intelligence Pipeline")
    parser.add_argument("--full", action="store_true", help="Run full pipeline")
    parser.add_argument("--quick", action="store_true", help="Use smaller dataset for testing")
    parser.add_argument("--generate-only", action="store_true", help="Generate data only")
    parser.add_argument("--etl-only", action="store_true", help="Run ETL only")
    args = parser.parse_args()

    if args.generate_only:
        generate_sample_data(quick=args.quick)
    elif args.etl_only:
        run_etl()
    else:
        run_full_pipeline(quick=args.quick)


if __name__ == "__main__":
    main()
