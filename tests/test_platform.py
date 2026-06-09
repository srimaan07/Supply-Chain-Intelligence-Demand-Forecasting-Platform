"""Unit tests for Supply Chain Intelligence Platform."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_generator import SupplyChainDataGenerator
from src.etl import SupplyChainETL
from src.forecasting import mape
from src.inventory_optimization import InventoryOptimizer


class TestDataGenerator:
    def test_generate_products_count(self):
        gen = SupplyChainDataGenerator(n_products=100, n_suppliers=10, n_warehouses=5, n_orders=1000)
        products = gen.generate_products()
        assert len(products) == 100
        assert "product_id" in products.columns
        assert products["unit_cost"].min() >= 0

    def test_generate_orders_count(self):
        gen = SupplyChainDataGenerator(n_products=100, n_suppliers=10, n_warehouses=5, n_orders=1000)
        products = gen.generate_products()
        warehouses = gen.generate_warehouses()
        suppliers = gen.generate_suppliers()
        orders = gen.generate_orders(products, warehouses, suppliers)
        assert len(orders) == 1000
        assert orders["quantity"].min() >= 1

    def test_generate_suppliers_count(self):
        gen = SupplyChainDataGenerator(n_suppliers=120)
        suppliers = gen.generate_suppliers()
        assert len(suppliers) == 120
        assert suppliers["reliability_score"].between(0, 100).all()


class TestETL:
    def _make_sample_data(self, tmp_path):
        gen = SupplyChainDataGenerator(n_products=50, n_suppliers=10, n_warehouses=5, n_orders=200)
        return gen.generate_all(tmp_path)

    def test_transform_cleans_duplicates(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        datasets = self._make_sample_data(raw_dir)
        datasets["products"] = pd.concat([datasets["products"], datasets["products"].iloc[:5]])
        for name, df in datasets.items():
            df.to_csv(raw_dir / f"{name}.csv", index=False)

        etl = SupplyChainETL(raw_dir=raw_dir, processed_dir=tmp_path / "processed")
        raw = etl.extract()
        processed = etl.transform(raw)
        assert len(processed["products"]) <= 50

    def test_transform_fixes_negative_stock(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        datasets = self._make_sample_data(raw_dir)
        datasets["inventory"].loc[0, "current_stock"] = -10
        for name, df in datasets.items():
            df.to_csv(raw_dir / f"{name}.csv", index=False)

        etl = SupplyChainETL(raw_dir=raw_dir, processed_dir=tmp_path / "processed")
        raw = etl.extract()
        processed = etl.transform(raw)
        assert processed["inventory"]["current_stock"].min() >= 0

    def test_transform_computes_stock_status(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        datasets = self._make_sample_data(raw_dir)
        for name, df in datasets.items():
            df.to_csv(raw_dir / f"{name}.csv", index=False)

        etl = SupplyChainETL(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed")
        raw = etl.extract()
        processed = etl.transform(raw)
        assert "stock_status" in processed["inventory"].columns
        assert processed["inventory"]["stock_status"].notna().all()


class TestForecasting:
    def test_mape_calculation(self):
        y_true = np.array([100, 200, 300])
        y_pred = np.array([110, 190, 310])
        result = mape(y_true, y_pred)
        assert result > 0
        assert result < 20

    def test_mape_zero_handling(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([0, 0, 0])
        assert mape(y_true, y_pred) == 0.0


class TestInventoryOptimization:
    def test_eoq_calculation(self):
        optimizer = InventoryOptimizer()
        eoq = optimizer.calculate_eoq(annual_demand=10000, unit_cost=25.0)
        assert eoq > 0
        assert isinstance(eoq, int)

    def test_eoq_zero_demand(self):
        optimizer = InventoryOptimizer()
        assert optimizer.calculate_eoq(0, 25.0) == 0

    def test_safety_stock_calculation(self):
        optimizer = InventoryOptimizer()
        safety = optimizer.calculate_safety_stock(avg_demand=10, lead_time_days=7)
        assert safety >= 0
        assert isinstance(safety, int)

    def test_safety_stock_increases_with_lead_time(self):
        optimizer = InventoryOptimizer()
        low = optimizer.calculate_safety_stock(10, 3)
        high = optimizer.calculate_safety_stock(10, 14)
        assert high >= low


class TestDataQuality:
    def test_order_dates_valid(self, tmp_path):
        gen = SupplyChainDataGenerator(n_products=50, n_suppliers=10, n_warehouses=5, n_orders=500)
        products = gen.generate_products()
        warehouses = gen.generate_warehouses()
        suppliers = gen.generate_suppliers()
        orders = gen.generate_orders(products, warehouses, suppliers)
        delivered = orders[orders["delivery_date"].notna()]
        assert (delivered["delivery_date"] >= delivered["order_date"]).all()

    def test_inventory_reorder_point_non_negative(self, tmp_path):
        gen = SupplyChainDataGenerator(n_products=50, n_suppliers=10, n_warehouses=5, n_orders=500)
        products = gen.generate_products()
        warehouses = gen.generate_warehouses()
        inventory = gen.generate_inventory(products, warehouses)
        assert (inventory["reorder_point"] >= 0).all()
        assert (inventory["safety_stock"] >= 0).all()
