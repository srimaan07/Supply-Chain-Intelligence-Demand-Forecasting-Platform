-- ============================================================
-- INTERMEDIATE QUERIES (11-25): CTEs, Subqueries, CASE
-- ============================================================

-- Q11: Warehouse performance with CASE classification
SELECT
    w.warehouse_id,
    w.warehouse_name,
    w.region,
    COUNT(i.inventory_id) AS total_skus,
    SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END) AS stock_outs,
    SUM(CASE WHEN i.current_stock <= i.reorder_point THEN 1 ELSE 0 END) AS reorder_needed,
    CASE
        WHEN SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) > 0.1 THEN 'Poor'
        WHEN SUM(CASE WHEN i.current_stock <= i.reorder_point THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) > 0.2 THEN 'Fair'
        ELSE 'Good'
    END AS performance_rating
FROM warehouses w
JOIN inventory i ON w.warehouse_id = i.warehouse_id
GROUP BY w.warehouse_id, w.warehouse_name, w.region
ORDER BY stock_outs DESC;

-- Q12: Suppliers causing delays (CTE)
WITH supplier_delays AS (
    SELECT
        s.supplier_id,
        s.supplier_name,
        COUNT(o.order_id) AS total_orders,
        SUM(CASE WHEN o.is_on_time = false THEN 1 ELSE 0 END) AS late_orders,
        AVG(o.delivery_date - o.order_date) AS avg_lead_time
    FROM suppliers s
    JOIN orders o ON s.supplier_id = o.supplier_id
    WHERE o.order_status = 'Delivered'
    GROUP BY s.supplier_id, s.supplier_name
)
SELECT *,
    ROUND(late_orders::numeric / NULLIF(total_orders, 0) * 100, 2) AS delay_pct
FROM supplier_delays
WHERE late_orders > 0
ORDER BY delay_pct DESC;

-- Q13: Products creating stock-outs
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(DISTINCT i.warehouse_id) AS warehouses_affected,
    SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END) AS stock_out_locations
FROM products p
JOIN inventory i ON p.product_id = i.product_id
GROUP BY p.product_id, p.product_name, p.category
HAVING SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END) > 0
ORDER BY stock_out_locations DESC;

-- Q14: Regional demand analysis
SELECT
    o.customer_region AS region,
    COUNT(DISTINCT o.product_id) AS unique_products,
    COUNT(*) AS total_orders,
    SUM(o.quantity) AS total_units,
    ROUND(SUM(o.total_amount), 2) AS total_revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
WHERE o.order_status = 'Delivered'
GROUP BY o.customer_region
ORDER BY total_revenue DESC;

-- Q15: Inventory value by category (subquery)
SELECT
    p.category,
    COUNT(DISTINCT i.product_id) AS products,
    SUM(i.current_stock) AS total_units,
    ROUND(SUM(i.inventory_value), 2) AS total_value,
    ROUND(AVG(i.inventory_turnover), 2) AS avg_turnover
FROM inventory i
JOIN products p ON i.product_id = p.product_id
WHERE i.product_id IN (
    SELECT product_id FROM products WHERE is_active = true
)
GROUP BY p.category
ORDER BY total_value DESC;

-- Q16: Fill rate by warehouse
SELECT
    w.warehouse_id,
    w.warehouse_name,
    COUNT(o.order_id) AS orders,
    ROUND(AVG(o.fill_rate) * 100, 2) AS avg_fill_rate_pct,
    SUM(CASE WHEN o.order_status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_orders
FROM warehouses w
LEFT JOIN orders o ON w.warehouse_id = o.warehouse_id
GROUP BY w.warehouse_id, w.warehouse_name
ORDER BY avg_fill_rate_pct ASC;

-- Q17: High-cost logistics routes
SELECT
    route,
    carrier,
    COUNT(*) AS shipment_count,
    ROUND(AVG(shipping_cost), 2) AS avg_cost,
    ROUND(AVG(distance_km), 0) AS avg_distance_km,
    ROUND(AVG(shipping_cost / NULLIF(distance_km, 0)), 4) AS cost_per_km
FROM logistics
WHERE distance_km > 0
GROUP BY route, carrier
HAVING AVG(shipping_cost) > (SELECT AVG(shipping_cost) FROM logistics)
ORDER BY avg_cost DESC;

-- Q18: Product profitability analysis
SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.unit_cost,
    p.selling_price,
    ROUND((p.selling_price - p.unit_cost) / NULLIF(p.selling_price, 0) * 100, 2) AS margin_pct,
    COALESCE(SUM(o.quantity), 0) AS units_sold,
    COALESCE(SUM(o.total_amount), 0) AS revenue
FROM products p
LEFT JOIN orders o ON p.product_id = o.product_id AND o.order_status = 'Delivered'
GROUP BY p.product_id, p.product_name, p.category, p.unit_cost, p.selling_price
ORDER BY revenue DESC
LIMIT 50;

-- Q19: Dead inventory identification
SELECT
    p.product_id,
    p.product_name,
    w.warehouse_name,
    i.current_stock,
    i.days_of_inventory,
    i.inventory_value,
    i.stock_status
FROM inventory i
JOIN products p ON i.product_id = p.product_id
JOIN warehouses w ON i.warehouse_id = w.warehouse_id
WHERE i.days_of_inventory > 180 OR i.stock_status = 'Dead Inventory'
ORDER BY i.inventory_value DESC;

-- Q20: Fast-moving products
SELECT
    p.product_id,
    p.product_name,
    p.category,
    AVG(i.inventory_turnover) AS avg_turnover,
    SUM(i.current_stock) AS total_stock
FROM inventory i
JOIN products p ON i.product_id = p.product_id
WHERE i.inventory_turnover > 12
GROUP BY p.product_id, p.product_name, p.category
ORDER BY avg_turnover DESC
LIMIT 30;

-- Q21: Order delivery performance by month
SELECT
    DATE_TRUNC('month', order_date) AS order_month,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END) AS on_time,
    SUM(CASE WHEN NOT is_on_time THEN 1 ELSE 0 END) AS late,
    ROUND(SUM(CASE WHEN is_on_time THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS on_time_pct
FROM orders
WHERE order_status = 'Delivered'
GROUP BY 1
ORDER BY 1;

-- Q22: Supplier defect rate impact
SELECT
    s.supplier_id,
    s.supplier_name,
    s.defect_rate,
    s.reliability_score,
    COUNT(o.order_id) AS orders,
    SUM(CASE WHEN o.order_status = 'Returned' THEN 1 ELSE 0 END) AS returns,
    ROUND(SUM(CASE WHEN o.order_status = 'Returned' THEN 1 ELSE 0 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 2) AS return_rate_pct
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
GROUP BY s.supplier_id, s.supplier_name, s.defect_rate, s.reliability_score
ORDER BY return_rate_pct DESC;

-- Q23: Cross-warehouse inventory comparison
SELECT
    p.category,
    w.region,
    COUNT(*) AS sku_count,
    ROUND(AVG(i.current_stock), 0) AS avg_stock,
    ROUND(AVG(i.days_of_inventory), 1) AS avg_doi
FROM inventory i
JOIN products p ON i.product_id = p.product_id
JOIN warehouses w ON i.warehouse_id = w.warehouse_id
GROUP BY p.category, w.region
ORDER BY p.category, w.region;

-- Q24: Shipment status breakdown
SELECT
    delivery_status,
    COUNT(*) AS count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) AS pct,
    ROUND(AVG(delay_days), 1) AS avg_delay,
    ROUND(AVG(shipping_cost), 2) AS avg_cost
FROM logistics
GROUP BY delivery_status
ORDER BY count DESC;

-- Q25: Reorder alert summary
SELECT
    stock_status,
    COUNT(*) AS item_count,
    ROUND(SUM(inventory_value), 2) AS total_value_at_risk
FROM inventory
WHERE stock_status IN ('Stock Out', 'Reorder Required', 'Low Stock')
GROUP BY stock_status
ORDER BY item_count DESC;
