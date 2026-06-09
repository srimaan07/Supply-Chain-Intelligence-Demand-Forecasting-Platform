"""
Synthetic supply chain data generator.

Generates realistic datasets meeting portfolio requirements:
- 10,000+ products
- 100+ suppliers
- 20+ warehouses
- 500,000+ order transactions
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import get_settings

logger = logging.getLogger(__name__)

CATEGORIES = {
    "Electronics": ["Smartphones", "Laptops", "Tablets", "Accessories", "Audio"],
    "Apparel": ["Men", "Women", "Kids", "Footwear", "Accessories"],
    "Home & Kitchen": ["Furniture", "Appliances", "Cookware", "Decor", "Storage"],
    "Grocery": ["Beverages", "Snacks", "Dairy", "Frozen", "Pantry"],
    "Health & Beauty": ["Skincare", "Haircare", "Vitamins", "Personal Care"],
    "Sports": ["Equipment", "Apparel", "Outdoor", "Fitness"],
    "Automotive": ["Parts", "Accessories", "Tools", "Fluids"],
    "Toys": ["Action Figures", "Board Games", "Educational", "Outdoor Toys"],
}

REGIONS = ["North", "South", "East", "West", "Central", "Northeast", "Southeast", "Midwest"]
STATES = {
    "North": ["NY", "MA", "PA", "NJ"],
    "South": ["TX", "FL", "GA", "NC"],
    "East": ["VA", "MD", "SC", "TN"],
    "West": ["CA", "WA", "OR", "AZ"],
    "Central": ["IL", "OH", "MI", "IN"],
    "Northeast": ["CT", "RI", "NH", "ME"],
    "Southeast": ["AL", "MS", "LA", "KY"],
    "Midwest": ["MN", "WI", "IA", "MO"],
}

CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "XPO Logistics", "Old Dominion", "Saia", "Estes"]
SUPPLIER_PREFIXES = [
    "Global", "Premier", "Atlas", "Summit", "Pacific", "Northern", "Southern",
    "Eastern", "Western", "Prime", "Elite", "Core", "Vertex", "Nova", "Apex",
]
ORDER_STATUSES = ["Delivered", "Shipped", "Processing", "Cancelled", "Returned", "Pending"]
DELIVERY_STATUSES = ["Delivered", "In Transit", "Delayed", "Lost", "Returned"]


class SupplyChainDataGenerator:
    """Generates synthetic supply chain datasets with configurable scale."""

    def __init__(
        self,
        n_products: int = 10_000,
        n_suppliers: int = 120,
        n_warehouses: int = 25,
        n_orders: int = 520_000,
        seed: int | None = None,
    ):
        self.n_products = n_products
        self.n_suppliers = n_suppliers
        self.n_warehouses = n_warehouses
        self.n_orders = n_orders
        self.rng = np.random.default_rng(seed or get_settings().random_seed)
        self.end_date = date.today()
        self.start_date = self.end_date - timedelta(days=730)

    def generate_products(self) -> pd.DataFrame:
        categories = list(CATEGORIES.keys())
        cat_weights = self.rng.dirichlet(np.ones(len(categories)))

        rows = []
        for i in range(1, self.n_products + 1):
            cat = self.rng.choice(categories, p=cat_weights)
            subcat = self.rng.choice(CATEGORIES[cat])
            unit_cost = round(float(self.rng.lognormal(3.0, 0.8)), 2)
            margin = float(self.rng.uniform(0.15, 0.55))
            selling_price = round(unit_cost * (1 + margin), 2)
            rows.append(
                {
                    "product_id": f"P{i:05d}",
                    "product_name": f"{subcat} Item {i}",
                    "category": cat,
                    "subcategory": subcat,
                    "unit_cost": unit_cost,
                    "selling_price": selling_price,
                    "weight_kg": round(float(self.rng.uniform(0.1, 25.0)), 3),
                    "is_active": bool(self.rng.random() > 0.02),
                }
            )
        return pd.DataFrame(rows)

    def generate_warehouses(self) -> pd.DataFrame:
        rows = []
        for i in range(1, self.n_warehouses + 1):
            region = REGIONS[(i - 1) % len(REGIONS)]
            state = self.rng.choice(STATES[region])
            capacity = int(self.rng.integers(50_000, 500_000))
            rows.append(
                {
                    "warehouse_id": f"W{i:03d}",
                    "warehouse_name": f"{region} Distribution Center {i}",
                    "location": f"{state}, USA",
                    "region": region,
                    "state": state,
                    "capacity_units": capacity,
                    "current_utilization": round(float(self.rng.uniform(0.4, 0.95)), 2),
                    "manager_name": f"Manager {i}",
                    "is_active": True,
                }
            )
        return pd.DataFrame(rows)

    def generate_suppliers(self) -> pd.DataFrame:
        rows = []
        for i in range(1, self.n_suppliers + 1):
            prefix = SUPPLIER_PREFIXES[i % len(SUPPLIER_PREFIXES)]
            rows.append(
                {
                    "supplier_id": f"S{i:03d}",
                    "supplier_name": f"{prefix} Supplier {i}",
                    "country": self.rng.choice(["USA", "China", "India", "Mexico", "Germany", "Vietnam"]),
                    "lead_time_days": int(self.rng.integers(2, 21)),
                    "reliability_score": round(float(self.rng.beta(8, 2) * 100), 2),
                    "defect_rate": round(float(self.rng.beta(1, 50)), 4),
                    "contact_email": f"supplier{i}@supplychain.com",
                    "is_active": bool(self.rng.random() > 0.03),
                }
            )
        return pd.DataFrame(rows)

    def generate_product_suppliers(
        self, products: pd.DataFrame, suppliers: pd.DataFrame
    ) -> pd.DataFrame:
        rows = []
        supplier_ids = suppliers["supplier_id"].tolist()
        for _, product in products.iterrows():
            n_links = int(self.rng.integers(1, 4))
            chosen = self.rng.choice(supplier_ids, size=n_links, replace=False)
            for j, sid in enumerate(chosen):
                rows.append(
                    {
                        "product_id": product["product_id"],
                        "supplier_id": sid,
                        "unit_cost": round(product["unit_cost"] * float(self.rng.uniform(0.85, 1.05)), 2),
                        "is_primary": j == 0,
                    }
                )
        return pd.DataFrame(rows)

    def generate_inventory(
        self, products: pd.DataFrame, warehouses: pd.DataFrame
    ) -> pd.DataFrame:
        rows = []
        inv_id = 1
        active_products = products[products["is_active"]].sample(
            frac=0.85, random_state=get_settings().random_seed
        )
        for _, product in active_products.iterrows():
            n_wh = int(self.rng.integers(1, min(4, self.n_warehouses + 1)))
            wh_sample = warehouses.sample(n=n_wh, random_state=int(inv_id))
            for _, wh in wh_sample.iterrows():
                reorder = int(self.rng.integers(50, 500))
                safety = int(reorder * float(self.rng.uniform(0.2, 0.5)))
                current = int(self.rng.integers(0, reorder * 3))
                rows.append(
                    {
                        "inventory_id": inv_id,
                        "product_id": product["product_id"],
                        "warehouse_id": wh["warehouse_id"],
                        "current_stock": current,
                        "reorder_point": reorder,
                        "safety_stock": safety,
                        "max_stock": reorder * 4,
                        "last_restocked": self.end_date - timedelta(days=int(self.rng.integers(1, 90))),
                    }
                )
                inv_id += 1
        return pd.DataFrame(rows)

    def generate_orders(
        self,
        products: pd.DataFrame,
        warehouses: pd.DataFrame,
        suppliers: pd.DataFrame,
    ) -> pd.DataFrame:
        product_ids = products["product_id"].values
        product_prices = products.set_index("product_id")["selling_price"].to_dict()
        wh_ids = warehouses["warehouse_id"].values
        wh_regions = warehouses.set_index("warehouse_id")["region"].to_dict()
        supplier_ids = suppliers["supplier_id"].values

        n = self.n_orders
        days_offset = self.rng.integers(0, (self.end_date - self.start_date).days, size=n)
        order_dates = [self.start_date + timedelta(days=int(d)) for d in days_offset]

        product_sample = self.rng.choice(product_ids, size=n)
        wh_sample = self.rng.choice(wh_ids, size=n)
        supplier_sample = self.rng.choice(supplier_ids, size=n)
        quantities = self.rng.integers(1, 50, size=n)
        statuses = self.rng.choice(
            ORDER_STATUSES, size=n, p=[0.72, 0.10, 0.08, 0.04, 0.03, 0.03]
        )

        rows = []
        for i in range(n):
            oid = f"ORD{i+1:07d}"
            pid = product_sample[i]
            qty = int(quantities[i])
            odate = order_dates[i]
            status = statuses[i]
            lead = int(self.rng.integers(1, 14))
            expected = odate + timedelta(days=lead)

            if status == "Delivered":
                delay = int(self.rng.integers(-2, 8))
                delivery = max(odate + timedelta(days=1), expected + timedelta(days=delay))
                is_on_time = delay <= 0
            elif status in ("Shipped", "Processing", "Pending"):
                delivery = None
                is_on_time = None
            else:
                delivery = odate + timedelta(days=int(self.rng.integers(1, 5)))
                is_on_time = False

            unit_price = product_prices[pid]
            fill = float(self.rng.uniform(0.85, 1.0)) if status != "Cancelled" else 0.0

            rows.append(
                {
                    "order_id": oid,
                    "product_id": pid,
                    "warehouse_id": wh_sample[i],
                    "supplier_id": supplier_sample[i],
                    "customer_region": wh_regions[wh_sample[i]],
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_amount": round(qty * unit_price, 2),
                    "order_date": odate,
                    "expected_delivery": expected,
                    "delivery_date": delivery,
                    "order_status": status,
                    "is_on_time": is_on_time,
                    "fill_rate": round(fill, 4),
                }
            )

        return pd.DataFrame(rows)

    def generate_logistics(self, orders: pd.DataFrame, warehouses: pd.DataFrame) -> pd.DataFrame:
        delivered = orders[orders["order_status"].isin(["Delivered", "Shipped"])].copy()
        sample_size = min(len(delivered), int(len(orders) * 0.85))
        sample = delivered.sample(n=sample_size, random_state=get_settings().random_seed)

        wh_regions = warehouses.set_index("warehouse_id")["region"].to_dict()
        rows = []
        for idx, (_, order) in enumerate(sample.iterrows()):
            carrier = self.rng.choice(CARRIERS)
            origin = order["warehouse_id"]
            dest = order["customer_region"]
            route = f"{origin} -> {dest}"
            ship_date = order["order_date"] + timedelta(days=int(self.rng.integers(0, 2)))
            expected = order["expected_delivery"]
            if order["delivery_date"] is not None and pd.notna(order["delivery_date"]):
                actual = order["delivery_date"]
                delay = max(0, (actual - expected).days)
                status = "Delayed" if delay > 0 else "Delivered"
            else:
                actual = None
                delay = 0
                status = "In Transit"

            rows.append(
                {
                    "shipment_id": f"SHP{idx+1:07d}",
                    "order_id": order["order_id"],
                    "carrier": carrier,
                    "route": route,
                    "origin_warehouse": origin,
                    "destination_region": dest,
                    "shipping_cost": round(float(self.rng.uniform(5, 150)), 2),
                    "distance_km": round(float(self.rng.uniform(50, 3000)), 2),
                    "ship_date": ship_date,
                    "expected_delivery": expected,
                    "actual_delivery": actual,
                    "delivery_status": status,
                    "delay_days": int(delay),
                    "is_delayed": delay > 0,
                }
            )
        return pd.DataFrame(rows)

    def generate_demand_history(
        self, orders: pd.DataFrame, warehouses: pd.DataFrame
    ) -> pd.DataFrame:
        delivered = orders[orders["order_status"] == "Delivered"].copy()
        agg = (
            delivered.groupby(["product_id", "warehouse_id", "order_date"])
            .agg(demand_quantity=("quantity", "sum"), revenue=("total_amount", "sum"))
            .reset_index()
        )
        agg = agg.rename(columns={"order_date": "demand_date"})
        wh_regions = warehouses.set_index("warehouse_id")["region"].to_dict()
        agg["region"] = agg["warehouse_id"].map(wh_regions)
        return agg

    def generate_all(self, output_dir: Path | None = None) -> dict[str, pd.DataFrame]:
        settings = get_settings()
        output_dir = output_dir or settings.raw_data_path
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating products (%d)...", self.n_products)
        products = self.generate_products()
        logger.info("Generating warehouses (%d)...", self.n_warehouses)
        warehouses = self.generate_warehouses()
        logger.info("Generating suppliers (%d)...", self.n_suppliers)
        suppliers = self.generate_suppliers()
        product_suppliers = self.generate_product_suppliers(products, suppliers)
        logger.info("Generating inventory records...")
        inventory = self.generate_inventory(products, warehouses)
        logger.info("Generating orders (%d)...", self.n_orders)
        orders = self.generate_orders(products, warehouses, suppliers)
        logger.info("Generating logistics records...")
        logistics = self.generate_logistics(orders, warehouses)
        logger.info("Generating demand history...")
        demand_history = self.generate_demand_history(orders, warehouses)

        datasets = {
            "products": products,
            "warehouses": warehouses,
            "suppliers": suppliers,
            "product_suppliers": product_suppliers,
            "inventory": inventory,
            "orders": orders,
            "logistics": logistics,
            "demand_history": demand_history,
        }

        for name, df in datasets.items():
            path = output_dir / f"{name}.csv"
            df.to_csv(path, index=False)
            logger.info("Saved %s: %d rows -> %s", name, len(df), path)

        return datasets


def generate_sample_data(
    output_dir: Path | None = None,
    quick: bool = False,
) -> dict[str, pd.DataFrame]:
    """Generate datasets. Use quick=True for testing with smaller volumes."""
    if quick:
        gen = SupplyChainDataGenerator(
            n_products=500, n_suppliers=50, n_warehouses=10, n_orders=5000
        )
    else:
        gen = SupplyChainDataGenerator()
    return gen.generate_all(output_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_sample_data()
