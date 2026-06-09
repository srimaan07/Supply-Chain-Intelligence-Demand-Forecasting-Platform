-- ============================================================
-- ADVANCED QUERIES (26-45): Window Functions, CTEs, Cohort
-- ============================================================

-- Q26: Running total of daily revenue
SELECT
    order_date,
    SUM(total_amount) AS daily_revenue,
    SUM(SUM(total_amount)) OVER (ORDER BY order_date) AS running_revenue,
    COUNT(*) AS daily_orders
FROM orders
WHERE order_status = 'Delivered'
GROUP BY order_date
ORDER BY order_date;

-- Q27: Product demand ranking by category
SELECT
    product_id,
    product_name,
    category,
    total_demand,
    RANK() OVER (PARTITION BY category ORDER BY total_demand DESC) AS category_rank,
    DENSE_RANK() OVER (ORDER BY total_demand DESC) AS overall_rank,
    PERCENT_RANK() OVER (ORDER BY total_demand DESC) AS demand_percentile
FROM (
    SELECT p.product_id, p.product_name, p.category, SUM(o.quantity) AS total_demand
    FROM orders o JOIN products p ON o.product_id = p.product_id
    WHERE o.order_status = 'Delivered'
    GROUP BY p.product_id, p.product_name, p.category
) sub
ORDER BY category, category_rank;

-- Q28: Month-over-month demand growth (LAG)
WITH monthly_demand AS (
    SELECT
        DATE_TRUNC('month', demand_date) AS month,
        SUM(demand_quantity) AS total_demand
    FROM demand_history
    GROUP BY 1
)
SELECT
    month,
    total_demand,
    LAG(total_demand) OVER (ORDER BY month) AS prev_month_demand,
    total_demand - LAG(total_demand) OVER (ORDER BY month) AS demand_change,
    ROUND(
        (total_demand - LAG(total_demand) OVER (ORDER BY month))::numeric /
        NULLIF(LAG(total_demand) OVER (ORDER BY month), 0) * 100, 2
    ) AS mom_growth_pct
FROM monthly_demand
ORDER BY month;

-- Q29: Warehouse performance ranking
SELECT
    warehouse_id,
    warehouse_name,
    region,
    total_inventory_value,
    stock_out_rate,
    RANK() OVER (ORDER BY stock_out_rate ASC) AS stock_out_rank,
    RANK() OVER (ORDER BY total_inventory_value DESC) AS value_rank,
    NTILE(4) OVER (ORDER BY stock_out_rate) AS performance_quartile
FROM (
    SELECT
        w.warehouse_id, w.warehouse_name, w.region,
        SUM(i.inventory_value) AS total_inventory_value,
        SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END)::float /
            NULLIF(COUNT(*), 0) AS stock_out_rate
    FROM warehouses w
    JOIN inventory i ON w.warehouse_id = i.warehouse_id
    GROUP BY w.warehouse_id, w.warehouse_name, w.region
) wh;

-- Q30: Cohort analysis - first order month retention
WITH first_orders AS (
    SELECT
        product_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM orders
    WHERE order_status = 'Delivered'
    GROUP BY product_id
),
order_months AS (
    SELECT
        o.product_id,
        f.cohort_month,
        DATE_TRUNC('month', o.order_date) AS order_month,
        SUM(o.quantity) AS quantity
    FROM orders o
    JOIN first_orders f ON o.product_id = f.product_id
    WHERE o.order_status = 'Delivered'
    GROUP BY o.product_id, f.cohort_month, DATE_TRUNC('month', o.order_date)
)
SELECT
    cohort_month,
    order_month,
    (EXTRACT(YEAR FROM age(order_month, cohort_month)) * 12 +
     EXTRACT(MONTH FROM age(order_month, cohort_month))) AS period_number,
    COUNT(DISTINCT product_id) AS active_products,
    SUM(quantity) AS total_demand
FROM order_months
GROUP BY cohort_month, order_month
ORDER BY cohort_month, period_number;

-- Q31: Moving average of weekly shipments
SELECT
    DATE_TRUNC('week', ship_date) AS week,
    COUNT(*) AS shipments,
    AVG(COUNT(*)) OVER (ORDER BY DATE_TRUNC('week', ship_date) ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS ma_4week,
    SUM(COUNT(*)) OVER (ORDER BY DATE_TRUNC('week', ship_date)) AS cumulative_shipments
FROM logistics
WHERE ship_date IS NOT NULL
GROUP BY DATE_TRUNC('week', ship_date)
ORDER BY week;

-- Q32: Supplier lead time variance analysis
SELECT
    s.supplier_id,
    s.supplier_name,
    s.lead_time_days AS contracted_lead_time,
    ROUND(AVG(o.delivery_date - o.order_date), 2) AS avg_actual_lead_time,
    ROUND(STDDEV(o.delivery_date - o.order_date), 2) AS lead_time_stddev,
    ROUND(AVG(o.delivery_date - o.order_date) - s.lead_time_days, 2) AS lead_time_variance,
    COUNT(*) AS order_count
FROM suppliers s
JOIN orders o ON s.supplier_id = o.supplier_id
WHERE o.order_status = 'Delivered' AND o.delivery_date IS NOT NULL
GROUP BY s.supplier_id, s.supplier_name, s.lead_time_days
HAVING COUNT(*) >= 10
ORDER BY lead_time_variance DESC;

-- Q33: Top 3 products per warehouse (ROW_NUMBER)
SELECT * FROM (
    SELECT
        w.warehouse_name,
        p.product_name,
        SUM(o.quantity) AS total_quantity,
        ROW_NUMBER() OVER (PARTITION BY w.warehouse_id ORDER BY SUM(o.quantity) DESC) AS rn
    FROM orders o
    JOIN products p ON o.product_id = p.product_id
    JOIN warehouses w ON o.warehouse_id = w.warehouse_id
    WHERE o.order_status = 'Delivered'
    GROUP BY w.warehouse_id, w.warehouse_name, p.product_name
) ranked WHERE rn <= 3;

-- Q34: Inventory ABC analysis
WITH product_value AS (
    SELECT
        p.product_id,
        p.product_name,
        SUM(i.inventory_value) AS total_value,
        SUM(SUM(i.inventory_value)) OVER () AS grand_total
    FROM inventory i
    JOIN products p ON i.product_id = p.product_id
    GROUP BY p.product_id, p.product_name
),
cumulative AS (
    SELECT *,
        SUM(total_value) OVER (ORDER BY total_value DESC) AS cumulative_value,
        SUM(total_value) OVER (ORDER BY total_value DESC) / grand_total AS cumulative_pct
    FROM product_value
)
SELECT *,
    CASE
        WHEN cumulative_pct <= 0.80 THEN 'A'
        WHEN cumulative_pct <= 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM cumulative
ORDER BY total_value DESC;

-- Q35: Route efficiency score
SELECT
    route,
    carrier,
    COUNT(*) AS shipments,
    ROUND(AVG(shipping_cost), 2) AS avg_cost,
    ROUND(AVG(delay_days), 2) AS avg_delay,
    ROUND(AVG(distance_km), 0) AS avg_distance,
    ROUND(
        (1 - AVG(delay_days)::float / NULLIF(AVG(delay_days) OVER (), 0)) * 50 +
        (1 - AVG(shipping_cost) / NULLIF(MAX(shipping_cost) OVER (), 0)) * 50, 2
    ) AS efficiency_score
FROM logistics
GROUP BY route, carrier
ORDER BY efficiency_score DESC;

-- Q36: Year-over-year comparison
SELECT
    EXTRACT(YEAR FROM order_date) AS year,
    EXTRACT(MONTH FROM order_date) AS month,
    COUNT(*) AS orders,
    SUM(total_amount) AS revenue,
    LAG(SUM(total_amount)) OVER (PARTITION BY EXTRACT(MONTH FROM order_date) ORDER BY EXTRACT(YEAR FROM order_date)) AS prev_year_revenue
FROM orders
WHERE order_status = 'Delivered'
GROUP BY EXTRACT(YEAR FROM order_date), EXTRACT(MONTH FROM order_date)
ORDER BY year, month;

-- Q37: Stock-out frequency by product category
SELECT
    p.category,
    COUNT(*) AS total_skus,
    SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END) AS stock_outs,
    ROUND(SUM(CASE WHEN i.current_stock <= 0 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) AS stock_out_pct,
    ROUND(AVG(i.inventory_turnover), 2) AS avg_turnover
FROM inventory i
JOIN products p ON i.product_id = p.product_id
GROUP BY p.category
ORDER BY stock_out_pct DESC;

-- Q38: Demand forecast accuracy (where actuals exist)
SELECT
    f.product_id,
    f.model_name,
    f.horizon_months,
    ROUND(AVG(f.mape), 2) AS avg_mape,
    ROUND(AVG(f.rmse), 2) AS avg_rmse,
    COUNT(*) AS forecast_count
FROM forecasts f
WHERE f.mape IS NOT NULL
GROUP BY f.product_id, f.model_name, f.horizon_months
ORDER BY avg_mape ASC
LIMIT 20;

-- Q39: Executive KPI trend
SELECT
    calculation_date,
    total_inventory_value,
    stock_out_rate * 100 AS stock_out_pct,
    fill_rate * 100 AS fill_rate_pct,
    LAG(stock_out_rate * 100) OVER (ORDER BY calculation_date) AS prev_stock_out_pct,
    stock_out_rate * 100 - LAG(stock_out_rate * 100) OVER (ORDER BY calculation_date) AS stock_out_change
FROM kpi_executive
ORDER BY calculation_date;

-- Q40: Supplier scorecard with window ranking
SELECT
    sc.supplier_id,
    s.supplier_name,
    sc.reliability_score,
    sc.on_time_pct,
    sc.overall_grade,
    sc.rank_position,
    PERCENT_RANK() OVER (ORDER BY sc.on_time_pct DESC) AS percentile,
    sc.on_time_pct - AVG(sc.on_time_pct) OVER () AS vs_avg
FROM supplier_scorecards sc
JOIN suppliers s ON sc.supplier_id = s.supplier_id
WHERE sc.scorecard_date = (SELECT MAX(scorecard_date) FROM supplier_scorecards)
ORDER BY sc.rank_position;

-- Q41: Inventory recommendation priority queue
SELECT
    r.product_id,
    p.product_name,
    r.warehouse_id,
    r.current_stock,
    r.recommended_reorder,
    r.expected_demand,
    r.priority,
    ROW_NUMBER() OVER (PARTITION BY r.priority ORDER BY r.expected_demand DESC) AS priority_rank
FROM inventory_recommendations r
JOIN products p ON r.product_id = p.product_id
WHERE r.status = 'pending'
ORDER BY
    CASE r.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    priority_rank;

-- Q42: Business insights severity dashboard
SELECT
    category,
    severity,
    COUNT(*) AS insight_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (PARTITION BY category) * 100, 2) AS pct_of_category
FROM business_insights
GROUP BY category, severity
ORDER BY category, insight_count DESC;

-- Q43: Which warehouses perform best? (Composite score)
WITH warehouse_metrics AS (
    SELECT
        w.warehouse_id,
        w.warehouse_name,
        w.region,
        COALESCE(AVG(ks.fill_rate), 0) AS fill_rate,
        COALESCE(AVG(ks.stock_out_frequency), 0) AS stock_out_freq,
        COALESCE(AVG(ki.inventory_turnover), 0) AS turnover,
        SUM(i.inventory_value) AS inventory_value
    FROM warehouses w
    LEFT JOIN kpi_service ks ON w.warehouse_id = ks.warehouse_id
    LEFT JOIN kpi_inventory ki ON w.warehouse_id = ki.warehouse_id
    LEFT JOIN inventory i ON w.warehouse_id = i.warehouse_id
    GROUP BY w.warehouse_id, w.warehouse_name, w.region
)
SELECT *,
    ROUND(fill_rate * 40 + (1 - stock_out_freq) * 30 + LEAST(turnover / 20, 1) * 30, 2) AS composite_score,
    RANK() OVER (ORDER BY fill_rate * 40 + (1 - stock_out_freq) * 30 + LEAST(turnover / 20, 1) * 30 DESC) AS overall_rank
FROM warehouse_metrics
ORDER BY composite_score DESC;

-- Q44: Frequently delayed shipment routes
SELECT
    l.route,
    l.carrier,
    COUNT(*) AS total_shipments,
    SUM(CASE WHEN l.is_delayed THEN 1 ELSE 0 END) AS delayed_count,
    ROUND(SUM(CASE WHEN l.is_delayed THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) AS delay_rate,
    ROUND(AVG(l.delay_days), 1) AS avg_delay_days,
    RANK() OVER (ORDER BY SUM(CASE WHEN l.is_delayed THEN 1 ELSE 0 END)::numeric / COUNT(*) DESC) AS delay_rank
FROM logistics l
GROUP BY l.route, l.carrier
HAVING COUNT(*) >= 5
ORDER BY delay_rate DESC
LIMIT 20;

-- Q45: Regional demand with 7-day moving average
SELECT
    region,
    demand_date,
    demand_quantity,
    AVG(demand_quantity) OVER (
        PARTITION BY region ORDER BY demand_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS ma_7day,
    SUM(demand_quantity) OVER (PARTITION BY region ORDER BY demand_date) AS cumulative_demand
FROM demand_history
WHERE region IS NOT NULL
ORDER BY region, demand_date;
