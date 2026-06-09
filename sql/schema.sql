-- Supply Chain Intelligence Platform - PostgreSQL Schema
-- Optimized for analytics workloads with proper indexing

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    product_id          VARCHAR(20) PRIMARY KEY,
    product_name        VARCHAR(255) NOT NULL,
    category            VARCHAR(100) NOT NULL,
    subcategory         VARCHAR(100),
    unit_cost           DECIMAL(12, 2) NOT NULL CHECK (unit_cost >= 0),
    selling_price       DECIMAL(12, 2) NOT NULL CHECK (selling_price >= 0),
    weight_kg           DECIMAL(8, 3),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id        VARCHAR(20) PRIMARY KEY,
    warehouse_name      VARCHAR(255) NOT NULL,
    location            VARCHAR(255) NOT NULL,
    region              VARCHAR(100) NOT NULL,
    state               VARCHAR(50),
    capacity_units      INTEGER NOT NULL CHECK (capacity_units > 0),
    current_utilization DECIMAL(5, 2) DEFAULT 0,
    manager_name        VARCHAR(255),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id         VARCHAR(20) PRIMARY KEY,
    supplier_name       VARCHAR(255) NOT NULL,
    country             VARCHAR(100),
    lead_time_days      INTEGER NOT NULL CHECK (lead_time_days >= 0),
    reliability_score   DECIMAL(5, 2) CHECK (reliability_score BETWEEN 0 AND 100),
    defect_rate         DECIMAL(5, 4) DEFAULT 0,
    contact_email       VARCHAR(255),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_suppliers (
    product_id          VARCHAR(20) REFERENCES products(product_id),
    supplier_id         VARCHAR(20) REFERENCES suppliers(supplier_id),
    unit_cost           DECIMAL(12, 2),
    is_primary          BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (product_id, supplier_id)
);

-- ============================================================
-- FACT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id        SERIAL PRIMARY KEY,
    product_id          VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id),
    current_stock       INTEGER NOT NULL DEFAULT 0,
    reorder_point       INTEGER NOT NULL DEFAULT 0,
    safety_stock        INTEGER NOT NULL DEFAULT 0,
    max_stock           INTEGER,
    last_restocked      DATE,
    inventory_value     DECIMAL(14, 2),
    days_of_inventory   DECIMAL(10, 2),
    inventory_turnover  DECIMAL(10, 4),
    stock_status        VARCHAR(50),
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id            VARCHAR(30) PRIMARY KEY,
    product_id          VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) REFERENCES warehouses(warehouse_id),
    supplier_id         VARCHAR(20) REFERENCES suppliers(supplier_id),
    customer_region     VARCHAR(100),
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          DECIMAL(12, 2),
    total_amount        DECIMAL(14, 2),
    order_date          DATE NOT NULL,
    expected_delivery   DATE,
    delivery_date       DATE,
    order_status        VARCHAR(50) NOT NULL,
    is_on_time          BOOLEAN,
    fill_rate           DECIMAL(5, 4),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logistics (
    shipment_id         VARCHAR(30) PRIMARY KEY,
    order_id            VARCHAR(30) REFERENCES orders(order_id),
    carrier             VARCHAR(100) NOT NULL,
    route               VARCHAR(255) NOT NULL,
    origin_warehouse    VARCHAR(20) REFERENCES warehouses(warehouse_id),
    destination_region  VARCHAR(100),
    shipping_cost       DECIMAL(12, 2) NOT NULL CHECK (shipping_cost >= 0),
    distance_km         DECIMAL(10, 2),
    ship_date           DATE,
    expected_delivery   DATE,
    actual_delivery     DATE,
    delivery_status     VARCHAR(50) NOT NULL,
    delay_days          INTEGER DEFAULT 0,
    is_delayed          BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demand_history (
    id                  SERIAL PRIMARY KEY,
    product_id          VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) REFERENCES warehouses(warehouse_id),
    region              VARCHAR(100),
    demand_date         DATE NOT NULL,
    demand_quantity     INTEGER NOT NULL CHECK (demand_quantity >= 0),
    revenue             DECIMAL(14, 2),
    UNIQUE (product_id, warehouse_id, demand_date)
);

-- ============================================================
-- KPI TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS kpi_inventory (
    id                  SERIAL PRIMARY KEY,
    calculation_date    DATE NOT NULL,
    warehouse_id        VARCHAR(20) REFERENCES warehouses(warehouse_id),
    product_id          VARCHAR(20) REFERENCES products(product_id),
    inventory_turnover  DECIMAL(10, 4),
    days_sales_inventory DECIMAL(10, 2),
    carrying_cost       DECIMAL(14, 2),
    inventory_accuracy  DECIMAL(5, 4),
    stock_out_rate      DECIMAL(5, 4),
    fill_rate           DECIMAL(5, 4),
    total_inventory_value DECIMAL(16, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_supplier (
    id                  SERIAL PRIMARY KEY,
    calculation_date    DATE NOT NULL,
    supplier_id         VARCHAR(20) NOT NULL REFERENCES suppliers(supplier_id),
    reliability_score   DECIMAL(5, 2),
    on_time_delivery_pct DECIMAL(5, 2),
    avg_lead_time       DECIMAL(8, 2),
    defect_rate         DECIMAL(5, 4),
    total_orders        INTEGER,
    total_spend         DECIMAL(16, 2),
    supplier_rank       INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_logistics (
    id                  SERIAL PRIMARY KEY,
    calculation_date    DATE NOT NULL,
    carrier             VARCHAR(100),
    route               VARCHAR(255),
    avg_delivery_time   DECIMAL(8, 2),
    transportation_cost DECIMAL(14, 2),
    delayed_shipment_rate DECIMAL(5, 4),
    total_shipments     INTEGER,
    on_time_pct         DECIMAL(5, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_service (
    id                  SERIAL PRIMARY KEY,
    calculation_date    DATE NOT NULL,
    warehouse_id        VARCHAR(20) REFERENCES warehouses(warehouse_id),
    fill_rate           DECIMAL(5, 4),
    order_accuracy      DECIMAL(5, 4),
    stock_out_frequency DECIMAL(5, 4),
    avg_order_cycle_time DECIMAL(8, 2),
    customer_satisfaction DECIMAL(5, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_executive (
    id                  SERIAL PRIMARY KEY,
    calculation_date    DATE NOT NULL UNIQUE,
    total_products      INTEGER,
    total_inventory_value DECIMAL(16, 2),
    stock_out_rate      DECIMAL(5, 4),
    fill_rate           DECIMAL(5, 4),
    forecast_accuracy   DECIMAL(5, 4),
    avg_supplier_reliability DECIMAL(5, 2),
    total_orders        INTEGER,
    revenue             DECIMAL(18, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- FORECASTING & OPTIMIZATION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS forecasts (
    id                  SERIAL PRIMARY KEY,
    product_id          VARCHAR(20) REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) REFERENCES warehouses(warehouse_id),
    region              VARCHAR(100),
    forecast_date       DATE NOT NULL,
    horizon_months      INTEGER NOT NULL,
    model_name          VARCHAR(50) NOT NULL,
    predicted_demand    DECIMAL(12, 2) NOT NULL,
    lower_bound         DECIMAL(12, 2),
    upper_bound         DECIMAL(12, 2),
    rmse                DECIMAL(12, 4),
    mae                 DECIMAL(12, 4),
    mape                DECIMAL(8, 4),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_recommendations (
    id                  SERIAL PRIMARY KEY,
    product_id          VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id),
    recommendation_date DATE NOT NULL,
    current_stock       INTEGER,
    recommended_reorder INTEGER,
    expected_demand     DECIMAL(12, 2),
    safety_stock        INTEGER,
    eoq                 INTEGER,
    reorder_point       INTEGER,
    priority            VARCHAR(20),
    status              VARCHAR(50) DEFAULT 'pending',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_insights (
    id                  SERIAL PRIMARY KEY,
    insight_date        DATE NOT NULL,
    category            VARCHAR(50) NOT NULL,
    entity_type         VARCHAR(50),
    entity_id           VARCHAR(50),
    metric_name         VARCHAR(100),
    metric_value        DECIMAL(14, 4),
    threshold_value     DECIMAL(14, 4),
    severity            VARCHAR(20),
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL,
    recommendation      TEXT NOT NULL,
    is_acknowledged     BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_alerts (
    id                  SERIAL PRIMARY KEY,
    alert_date          DATE NOT NULL,
    product_id          VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id        VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id),
    alert_type          VARCHAR(50) NOT NULL,
    current_stock       INTEGER,
    reorder_point       INTEGER,
    message             TEXT,
    severity            VARCHAR(20),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_scorecards (
    id                  SERIAL PRIMARY KEY,
    scorecard_date      DATE NOT NULL,
    supplier_id         VARCHAR(20) NOT NULL REFERENCES suppliers(supplier_id),
    reliability_score   DECIMAL(5, 2),
    avg_lead_time       DECIMAL(8, 2),
    on_time_pct         DECIMAL(5, 2),
    defect_rate         DECIMAL(5, 4),
    overall_grade       VARCHAR(5),
    rank_position       INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- ETL AUDIT
-- ============================================================

CREATE TABLE IF NOT EXISTS etl_audit_log (
    id                  SERIAL PRIMARY KEY,
    pipeline_name       VARCHAR(100) NOT NULL,
    stage               VARCHAR(50) NOT NULL,
    records_processed   INTEGER,
    records_failed      INTEGER,
    status              VARCHAR(20) NOT NULL,
    error_message       TEXT,
    started_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    duration_seconds    DECIMAL(10, 2)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(stock_status);
CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_orders_supplier ON orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_orders_warehouse ON orders(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_logistics_carrier ON logistics(carrier);
CREATE INDEX IF NOT EXISTS idx_logistics_route ON logistics(route);
CREATE INDEX IF NOT EXISTS idx_logistics_status ON logistics(delivery_status);
CREATE INDEX IF NOT EXISTS idx_demand_history_date ON demand_history(demand_date);
CREATE INDEX IF NOT EXISTS idx_demand_history_product ON demand_history(product_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_product ON forecasts(product_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_date ON forecasts(forecast_date);
CREATE INDEX IF NOT EXISTS idx_kpi_inventory_date ON kpi_inventory(calculation_date);
CREATE INDEX IF NOT EXISTS idx_kpi_supplier_date ON kpi_supplier(calculation_date);
CREATE INDEX IF NOT EXISTS idx_insights_category ON business_insights(category);
CREATE INDEX IF NOT EXISTS idx_insights_severity ON business_insights(severity);

-- ============================================================
-- VIEWS FOR ANALYTICS
-- ============================================================

CREATE OR REPLACE VIEW v_inventory_health AS
SELECT
    i.inventory_id,
    p.product_id,
    p.product_name,
    p.category,
    w.warehouse_id,
    w.warehouse_name,
    w.region,
    i.current_stock,
    i.reorder_point,
    i.safety_stock,
    i.inventory_turnover,
    i.days_of_inventory,
    i.stock_status,
    i.inventory_value,
    CASE
        WHEN i.current_stock <= 0 THEN 'Stock Out'
        WHEN i.current_stock <= i.reorder_point THEN 'Reorder Required'
        WHEN i.current_stock <= i.safety_stock THEN 'Low Stock'
        WHEN i.max_stock IS NOT NULL AND i.current_stock > i.max_stock THEN 'Overstocked'
        WHEN i.days_of_inventory > 180 THEN 'Dead Inventory'
        WHEN i.inventory_turnover > 12 THEN 'Fast Moving'
        ELSE 'Healthy'
    END AS health_status
FROM inventory i
JOIN products p ON i.product_id = p.product_id
JOIN warehouses w ON i.warehouse_id = w.warehouse_id;

CREATE OR REPLACE VIEW v_supplier_performance AS
SELECT
    s.supplier_id,
    s.supplier_name,
    s.lead_time_days AS contracted_lead_time,
    s.reliability_score,
    s.defect_rate,
    COUNT(o.order_id) AS total_orders,
    AVG(CASE WHEN o.is_on_time THEN 1.0 ELSE 0.0 END) * 100 AS on_time_pct,
    AVG(o.delivery_date - o.order_date) AS avg_actual_lead_time,
    SUM(o.total_amount) AS total_spend
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
GROUP BY s.supplier_id, s.supplier_name, s.lead_time_days, s.reliability_score, s.defect_rate;

CREATE OR REPLACE VIEW v_logistics_summary AS
SELECT
    l.carrier,
    l.route,
    COUNT(*) AS total_shipments,
    AVG(l.shipping_cost) AS avg_shipping_cost,
    SUM(l.shipping_cost) AS total_shipping_cost,
    AVG(l.delay_days) AS avg_delay_days,
    AVG(CASE WHEN l.is_delayed THEN 1.0 ELSE 0.0 END) * 100 AS delay_rate_pct,
    AVG(l.actual_delivery - l.ship_date) AS avg_transit_days
FROM logistics l
GROUP BY l.carrier, l.route;

CREATE OR REPLACE VIEW v_executive_dashboard AS
SELECT
    ke.calculation_date,
    ke.total_products,
    ke.total_inventory_value,
    ke.stock_out_rate * 100 AS stock_out_rate_pct,
    ke.fill_rate * 100 AS fill_rate_pct,
    ke.forecast_accuracy * 100 AS forecast_accuracy_pct,
    ke.avg_supplier_reliability,
    ke.total_orders,
    ke.revenue
FROM kpi_executive ke
ORDER BY ke.calculation_date DESC;
