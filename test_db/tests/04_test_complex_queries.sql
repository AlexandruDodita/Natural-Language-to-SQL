-- ============================================================
-- TEST 04: Complex Query Capability
-- Prove the DB supports real analytical workloads:
-- multi-joins, CTEs, window functions, subqueries, aggregations
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_count INTEGER;
    v_val   NUMERIC;
    rec     RECORD;
BEGIN
    RAISE NOTICE '--- 04: Complex Query Capability ---';

    -- 4.1 Revenue per location per month (3-table join + aggregation)
    SELECT count(*) INTO v_count FROM (
        SELECT
            l.name AS location,
            DATE_TRUNC('month', r.pickup_date) AS month,
            SUM(r.total_cost) AS revenue,
            COUNT(*) AS bookings
        FROM reservations r
        JOIN locations l ON r.pickup_location = l.id
        WHERE r.status = 'completed'
        GROUP BY l.name, DATE_TRUNC('month', r.pickup_date)
    ) sub;
    ASSERT v_count > 100, format('Revenue by location/month returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.1  Revenue per location per month: % rows', v_count;

    -- 4.2 Top vehicles by utilization rate (CTE + window function)
    SELECT count(*) INTO v_count FROM (
        WITH vehicle_days AS (
            SELECT
                v.id,
                v.make || ' ' || v.model AS vehicle,
                vc.name AS category,
                COUNT(r.id) AS total_rentals,
                SUM(r.return_date - r.pickup_date) AS total_days_rented
            FROM vehicles v
            JOIN vehicle_categories vc ON v.category_id = vc.id
            LEFT JOIN reservations r ON r.vehicle_id = v.id AND r.status = 'completed'
            GROUP BY v.id, v.make, v.model, vc.name
        )
        SELECT
            vehicle, category, total_rentals, total_days_rented,
            RANK() OVER (PARTITION BY category ORDER BY total_days_rented DESC) AS rank_in_category
        FROM vehicle_days
    ) sub;
    ASSERT v_count >= 80, format('Vehicle utilization query returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.2  Vehicle utilization with CTE + RANK(): % rows', v_count;

    -- 4.3 Customer lifetime value (multi-join + aggregation + HAVING)
    SELECT count(*) INTO v_count FROM (
        SELECT
            c.id,
            c.first_name || ' ' || c.last_name AS client,
            COUNT(DISTINCT r.id) AS total_reservations,
            SUM(p.amount) AS total_spent,
            ROUND(AVG(rev.rating), 2) AS avg_rating
        FROM clients c
        JOIN reservations r ON r.client_id = c.id
        JOIN payments p ON p.reservation_id = r.id
        LEFT JOIN reviews rev ON rev.reservation_id = r.id
        GROUP BY c.id, c.first_name, c.last_name
        HAVING SUM(p.amount) > 500
    ) sub;
    ASSERT v_count >= 50, format('High-value customers query returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.3  Customer lifetime value (HAVING > $500): % customers', v_count;

    -- 4.4 Month-over-month revenue growth (CTE + LAG window function)
    SELECT count(*) INTO v_count FROM (
        WITH monthly AS (
            SELECT
                DATE_TRUNC('month', pickup_date)::DATE AS month,
                SUM(total_cost) AS revenue
            FROM reservations
            WHERE status = 'completed'
            GROUP BY 1
        )
        SELECT
            month,
            revenue,
            LAG(revenue) OVER (ORDER BY month) AS prev_month,
            ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS growth_pct
        FROM monthly
    ) sub WHERE growth_pct IS NOT NULL;
    ASSERT v_count >= 30, format('MoM growth query returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.4  Month-over-month revenue growth (LAG): % months', v_count;

    -- 4.5 Maintenance cost vs revenue per vehicle (correlated subquery)
    SELECT count(*) INTO v_count FROM (
        SELECT
            v.id,
            v.make || ' ' || v.model AS vehicle,
            v.daily_rate,
            (SELECT COALESCE(SUM(r.total_cost), 0) FROM reservations r
             WHERE r.vehicle_id = v.id AND r.status = 'completed') AS total_revenue,
            (SELECT COALESCE(SUM(m.cost), 0) FROM maintenance_records m
             WHERE m.vehicle_id = v.id) AS total_maintenance,
            (SELECT COALESCE(SUM(r.total_cost), 0) FROM reservations r
             WHERE r.vehicle_id = v.id AND r.status = 'completed')
            -
            (SELECT COALESCE(SUM(m.cost), 0) FROM maintenance_records m
             WHERE m.vehicle_id = v.id) AS net_profit
        FROM vehicles v
    ) sub WHERE total_revenue > 0;
    ASSERT v_count >= 50, format('Vehicle profitability returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.5  Vehicle profitability (correlated subqueries): % vehicles', v_count;

    -- 4.6 Location performance dashboard (5-table join)
    SELECT count(*) INTO v_count FROM (
        SELECT
            l.id,
            l.name AS location,
            l.city,
            COUNT(DISTINCT e.id) AS staff_count,
            COUNT(DISTINCT v.id) AS fleet_size,
            COUNT(DISTINCT r.id) AS total_reservations,
            ROUND(COALESCE(SUM(r.total_cost), 0), 2) AS total_revenue,
            ROUND(COALESCE(AVG(rev.rating), 0), 2) AS avg_rating
        FROM locations l
        LEFT JOIN employees e ON e.location_id = l.id
        LEFT JOIN vehicles v ON v.location_id = l.id
        LEFT JOIN reservations r ON r.pickup_location = l.id AND r.status = 'completed'
        LEFT JOIN reviews rev ON rev.reservation_id = r.id
        GROUP BY l.id, l.name, l.city
    ) sub;
    ASSERT v_count = 10, format('Location dashboard returned %s rows (expected 10)', v_count);
    RAISE NOTICE '[PASS] 4.6  Location performance dashboard (5-table join): % locations', v_count;

    -- 4.7 Seasonal demand heatmap (EXTRACT + CASE pivot)
    SELECT count(*) INTO v_count FROM (
        SELECT
            vc.name AS category,
            SUM(CASE WHEN EXTRACT(QUARTER FROM r.pickup_date) = 1 THEN 1 ELSE 0 END) AS q1,
            SUM(CASE WHEN EXTRACT(QUARTER FROM r.pickup_date) = 2 THEN 1 ELSE 0 END) AS q2,
            SUM(CASE WHEN EXTRACT(QUARTER FROM r.pickup_date) = 3 THEN 1 ELSE 0 END) AS q3,
            SUM(CASE WHEN EXTRACT(QUARTER FROM r.pickup_date) = 4 THEN 1 ELSE 0 END) AS q4
        FROM reservations r
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN vehicle_categories vc ON v.category_id = vc.id
        GROUP BY vc.name
    ) sub;
    ASSERT v_count = 5, format('Seasonal demand heatmap returned %s rows (expected 5)', v_count);
    RAISE NOTICE '[PASS] 4.7  Seasonal demand heatmap (pivot): 5 categories x 4 quarters';

    -- 4.8 Running total of payments per client (window SUM)
    SELECT count(*) INTO v_count FROM (
        SELECT
            c.first_name || ' ' || c.last_name AS client,
            p.payment_date,
            p.amount,
            SUM(p.amount) OVER (PARTITION BY c.id ORDER BY p.payment_date
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
        FROM payments p
        JOIN reservations r ON p.reservation_id = r.id
        JOIN clients c ON r.client_id = c.id
    ) sub;
    ASSERT v_count >= 2500, format('Running totals returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.8  Running payment totals per client (window SUM): % rows', v_count;

    -- 4.9 Repeat customer analysis (HAVING + subquery + percentage)
    SELECT count(*) INTO v_count FROM (
        SELECT client_id, COUNT(*) AS visits
        FROM reservations
        WHERE status IN ('completed', 'active')
        GROUP BY client_id
        HAVING COUNT(*) >= 3
    ) sub;
    ASSERT v_count >= 20,
        format('Only %s repeat customers (3+ visits), expected >=20', v_count);
    RAISE NOTICE '[PASS] 4.9  Repeat customers (3+ visits): %', v_count;

    -- 4.10 Complex CTE chain: fleet age analysis → maintenance cost correlation
    SELECT count(*) INTO v_count FROM (
        WITH fleet_age AS (
            SELECT
                v.id,
                v.make || ' ' || v.model AS vehicle,
                2025 - v.year AS age_years,
                v.mileage,
                vc.name AS category
            FROM vehicles v
            JOIN vehicle_categories vc ON v.category_id = vc.id
        ),
        maint_costs AS (
            SELECT vehicle_id, SUM(cost) AS total_cost, COUNT(*) AS service_count
            FROM maintenance_records
            GROUP BY vehicle_id
        )
        SELECT
            fa.category,
            fa.age_years,
            COUNT(*) AS vehicle_count,
            ROUND(AVG(COALESCE(mc.total_cost, 0)), 2) AS avg_maintenance_cost,
            ROUND(AVG(COALESCE(mc.service_count, 0)), 1) AS avg_service_visits,
            ROUND(AVG(fa.mileage), 0) AS avg_mileage
        FROM fleet_age fa
        LEFT JOIN maint_costs mc ON mc.vehicle_id = fa.id
        GROUP BY fa.category, fa.age_years
        ORDER BY fa.category, fa.age_years
    ) sub;
    ASSERT v_count >= 15, format('Fleet age analysis returned only %s rows', v_count);
    RAISE NOTICE '[PASS] 4.10 Fleet age → maintenance correlation (chained CTEs): % rows', v_count;

    RAISE NOTICE '--- 04: All complex query tests passed ---';
END $$;
