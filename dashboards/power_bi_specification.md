# Power BI Dashboard Specifications

## Overview

This document provides complete specifications for building the executive Power BI dashboard connected to the PostgreSQL `supply_chain` database.

## Data Connection

```
Server: localhost:5432
Database: supply_chain
Authentication: Database (sc_admin)
```

### Recommended Tables/Views
- `v_executive_dashboard`
- `v_inventory_health`
- `v_supplier_performance`
- `v_logistics_summary`
- `kpi_inventory`, `kpi_supplier`, `kpi_logistics`, `kpi_service`
- `forecasts`, `inventory_recommendations`, `business_insights`
- `orders`, `products`, `warehouses`, `suppliers`, `logistics`

---

## Page 1: Executive Summary

### KPI Cards
| KPI | Source | DAX Measure |
|-----|--------|-------------|
| Total Products | kpi_executive | `Total Products = MAX(kpi_executive[total_products])` |
| Total Inventory Value | kpi_executive | `Total Inventory Value = MAX(kpi_executive[total_inventory_value])` |
| Stock-Out Rate | kpi_executive | `Stock Out Rate = MAX(kpi_executive[stock_out_rate]) * 100` |
| Fill Rate | kpi_executive | `Fill Rate = MAX(kpi_executive[fill_rate]) * 100` |
| Forecast Accuracy | kpi_executive | `Forecast Accuracy = MAX(kpi_executive[forecast_accuracy]) * 100` |

### Visuals
1. **KPI Cards Row** - 5 cards across top
2. **Revenue Trend** - Line chart: `orders[order_date]` vs `SUM(orders[total_amount])`
3. **Orders by Status** - Donut chart: `orders[order_status]`
4. **Regional Revenue** - Map/Bar: `orders[customer_region]` vs revenue
5. **Top Insights** - Table: `business_insights` filtered by severity = high/critical

### Filters
- Date Range (order_date)
- Region (customer_region)
- Category (products.category)

---

## Page 2: Inventory Dashboard

### KPI Cards
- Total SKUs, Stock-Outs, Reorder Required, Overstocked Value, Avg Turnover

### Visuals
1. **Inventory by Warehouse** - Stacked bar: warehouse vs inventory_value
2. **Inventory Turnover** - Bar chart by category
3. **Dead Stock Analysis** - Table: items where days_of_inventory > 180
4. **Reorder Alerts** - Table: inventory_alerts sorted by severity
5. **Health Status Distribution** - Pie chart: v_inventory_health[health_status]
6. **ABC Analysis** - Run SQL Q34, import as view

### Drill-Through
- Warehouse → Product-level inventory detail
- Category → SKU list

---

## Page 3: Supplier Dashboard

### KPI Cards
- Avg On-Time %, Total Suppliers, High-Risk Suppliers, Avg Lead Time

### Visuals
1. **Supplier Ranking** - Bar chart: supplier_scorecards by rank_position
2. **Reliability Scores** - Scatter: reliability vs on_time_pct
3. **Delivery Performance** - Line: monthly on-time % trend
4. **Supplier Scorecard Table** - Grade, rank, metrics
5. **Defect Rate Analysis** - Bar by supplier

### Filters
- Supplier Name, Country, Grade (A-D)

---

## Page 4: Logistics Dashboard

### KPI Cards
- Total Shipments, Avg Delay Rate, Total Shipping Cost, Carriers Used

### Visuals
1. **Delayed Shipments** - Table with conditional formatting
2. **Transportation Costs** - Bar by carrier
3. **Route Analysis** - Matrix: route x carrier with delay rate
4. **Cost per KM** - Scatter plot
5. **Delivery Status** - Donut chart

### Filters
- Carrier, Route, Date Range

---

## Page 5: Forecast Dashboard

### KPI Cards
- Forecasts Generated, Best Model, Avg MAPE, Recommendations Pending

### Visuals
1. **Demand Forecast** - Line chart: actual vs predicted by month
2. **Forecast by Horizon** - Small multiples: 3/6/12 month
3. **Inventory Recommendations** - Table with priority color coding
4. **Capacity Planning** - Warehouse utilization vs forecasted demand
5. **Model Comparison** - Bar: RMSE/MAPE by model from forecasts table

### Filters
- Product, Warehouse, Horizon, Model

---

## DAX Measures Library

```dax
-- Inventory Turnover
Inventory Turnover = DIVIDE(SUM(orders[quantity]), AVERAGE(inventory[current_stock]), 0)

-- Days of Inventory
Days of Inventory = DIVIDE(365, [Inventory Turnover], 0)

-- On-Time Delivery %
On Time Delivery % =
    DIVIDE(
        CALCULATE(COUNT(orders[order_id]), orders[is_on_time] = TRUE()),
        CALCULATE(COUNT(orders[order_id]), orders[order_status] = "Delivered"),
        0
    ) * 100

-- Stock Out Rate
Stock Out Rate =
    DIVIDE(
        CALCULATE(COUNT(inventory[inventory_id]), inventory[current_stock] <= 0),
        COUNT(inventory[inventory_id]),
        0
    ) * 100

-- Fill Rate
Fill Rate = AVERAGE(orders[fill_rate]) * 100

-- Delay Rate
Delay Rate =
    DIVIDE(
        CALCULATE(COUNT(logistics[shipment_id]), logistics[is_delayed] = TRUE()),
        COUNT(logistics[shipment_id]),
        0
    ) * 100

-- Revenue YTD
Revenue YTD = TOTALYTD(SUM(orders[total_amount]), orders[order_date])

-- MoM Revenue Growth
MoM Growth =
    VAR CurrentMonth = [Revenue YTD]
    VAR PrevMonth = CALCULATE([Revenue YTD], DATEADD(orders[order_date], -1, MONTH))
    RETURN DIVIDE(CurrentMonth - PrevMonth, PrevMonth, 0) * 100
```

---

## Data Model Relationships

```
products (1) ---- (*) inventory
products (1) ---- (*) orders
products (1) ---- (*) demand_history
warehouses (1) ---- (*) inventory
warehouses (1) ---- (*) orders
suppliers (1) ---- (*) orders
orders (1) ---- (0..1) logistics
products (*) ---- (*) suppliers (via product_suppliers)
```

---

## Theme & Formatting

- Primary Color: #1B4965 (Navy)
- Accent: #62B6CB (Teal)
- Alert Critical: #E63946
- Alert Warning: #F4A261
- Alert Success: #2A9D8F
- Font: Segoe UI
- Number Format: Currency ($), Percentage (1 decimal)

---

## Refresh Schedule

- DirectQuery or Scheduled Refresh: Daily at 6:00 AM
- Pipeline trigger: Run `python scripts/run_pipeline.py --full` before refresh
