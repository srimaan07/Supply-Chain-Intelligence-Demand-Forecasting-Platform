-- ============================================================
-- SUPPLY CHAIN INTELLIGENCE PLATFORM
-- 40+ SQL Analytics Queries
-- Categories: Basic, Intermediate, Advanced
-- ============================================================

-- ============================================================
-- BASIC QUERIES (1-10): Joins, Aggregations, Group By
-- ============================================================

-- Q1: Total products by category
-- SELECT category, COUNT(*) AS product_count
-- FROM products GROUP BY category ORDER BY product_count DESC;

-- Q2: Average unit cost and selling price by category
-- SELECT category,
--        ROUND(AVG(unit_cost), 2) AS avg_cost,
--        ROUND(AVG(selling_price), 2) AS avg_price,
--        ROUND(AVG(selling_price - unit_cost), 2) AS avg_margin
-- FROM products GROUP BY category;

-- Q3: Inventory summary by warehouse
-- SELECT w.warehouse_id, w.warehouse_name, w.region,
--        COUNT(i.inventory_id) AS sku_count,
--        SUM(i.current_stock) AS total_units,
--        ROUND(SUM(i.inventory_value), 2) AS total_value
-- FROM warehouses w
-- JOIN inventory i ON w.warehouse_id = i.warehouse_id
-- GROUP BY w.warehouse_id, w.warehouse_name, w.region;

-- Q4: Order count and revenue by order status
-- SELECT order_status, COUNT(*) AS order_count,
--        SUM(total_amount) AS total_revenue,
--        AVG(quantity) AS avg_quantity
-- FROM orders GROUP BY order_status;

-- Q5: Top 10 products by revenue
-- SELECT p.product_id, p.product_name, p.category,
--        SUM(o.total_amount) AS revenue, SUM(o.quantity) AS units_sold
-- FROM orders o JOIN products p ON o.product_id = p.product_id
-- WHERE o.order_status = 'Delivered'
-- GROUP BY p.product_id, p.product_name, p.category
-- ORDER BY revenue DESC LIMIT 10;

-- Q6: Supplier order volume
-- SELECT s.supplier_id, s.supplier_name, COUNT(o.order_id) AS orders,
--        SUM(o.total_amount) AS total_spend
-- FROM suppliers s LEFT JOIN orders o ON s.supplier_id = o.supplier_id
-- GROUP BY s.supplier_id, s.supplier_name ORDER BY total_spend DESC;

-- Q7: Logistics cost by carrier
-- SELECT carrier, COUNT(*) AS shipments,
--        ROUND(AVG(shipping_cost), 2) AS avg_cost,
--        ROUND(SUM(shipping_cost), 2) AS total_cost
-- FROM logistics GROUP BY carrier ORDER BY total_cost DESC;

-- Q8: Warehouse capacity utilization
-- SELECT warehouse_id, warehouse_name, capacity_units,
--        current_utilization * 100 AS utilization_pct
-- FROM warehouses ORDER BY current_utilization DESC;

-- Q9: Products with zero stock
-- SELECT p.product_id, p.product_name, w.warehouse_name, i.current_stock
-- FROM inventory i
-- JOIN products p ON i.product_id = p.product_id
-- JOIN warehouses w ON i.warehouse_id = w.warehouse_id
-- WHERE i.current_stock <= 0;

-- Q10: Monthly order trend
-- SELECT DATE_TRUNC('month', order_date) AS month,
--        COUNT(*) AS orders, SUM(total_amount) AS revenue
-- FROM orders GROUP BY 1 ORDER BY 1;
