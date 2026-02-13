-- ============================================================
-- TEST 03: Data Genuineness & Quality
-- Verify distributions, ranges, and realism of seeded data
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_count  INTEGER;
    v_val    NUMERIC;
    v_min    NUMERIC;
    v_max    NUMERIC;
    v_ratio  NUMERIC;
    v_summer INTEGER;
    v_winter INTEGER;
    rec      RECORD;
BEGIN
    RAISE NOTICE '--- 03: Data Genuineness ---';

    -- 3.1 Row count minimums
    SELECT count(*) INTO v_count FROM locations;
    ASSERT v_count >= 10, format('locations: %s rows (expected >=10)', v_count);

    SELECT count(*) INTO v_count FROM employees;
    ASSERT v_count >= 40, format('employees: %s rows (expected >=40)', v_count);

    SELECT count(*) INTO v_count FROM vehicles;
    ASSERT v_count >= 80, format('vehicles: %s rows (expected >=80)', v_count);

    SELECT count(*) INTO v_count FROM clients;
    ASSERT v_count >= 600, format('clients: %s rows (expected >=600)', v_count);

    SELECT count(*) INTO v_count FROM reservations;
    ASSERT v_count >= 3000, format('reservations: %s rows (expected >=3000)', v_count);

    SELECT count(*) INTO v_count FROM payments;
    ASSERT v_count >= 2500, format('payments: %s rows (expected >=2500)', v_count);

    SELECT count(*) INTO v_count FROM maintenance_records;
    ASSERT v_count >= 400, format('maintenance_records: %s rows (expected >=400)', v_count);

    SELECT count(*) INTO v_count FROM reviews;
    ASSERT v_count >= 1200, format('reviews: %s rows (expected >=1200)', v_count);

    SELECT SUM(n_live_tup) INTO v_count FROM pg_stat_user_tables;
    ASSERT v_count >= 5000, format('Total rows: %s (expected >=5000)', v_count);
    RAISE NOTICE '[PASS] 3.1  Row counts: % total rows across 9 tables', v_count;

    -- 3.2 Every location has employees
    SELECT count(DISTINCT location_id) INTO v_count FROM employees;
    ASSERT v_count = 10, format('Only %s/10 locations have employees', v_count);
    RAISE NOTICE '[PASS] 3.2  All 10 locations have employees';

    -- 3.3 All 5 vehicle categories are represented in vehicles
    SELECT count(DISTINCT category_id) INTO v_count FROM vehicles;
    ASSERT v_count = 5, format('Only %s/5 categories have vehicles', v_count);
    RAISE NOTICE '[PASS] 3.3  All 5 vehicle categories represented';

    -- 3.4 Salary ranges are realistic by role
    FOR rec IN
        SELECT role, MIN(salary) as min_sal, MAX(salary) as max_sal, ROUND(AVG(salary)) as avg_sal
        FROM employees GROUP BY role
    LOOP
        IF rec.role = 'manager' THEN
            ASSERT rec.min_sal >= 50000 AND rec.max_sal <= 75000,
                format('Manager salary out of range: %s-%s', rec.min_sal, rec.max_sal);
        ELSIF rec.role = 'mechanic' THEN
            ASSERT rec.min_sal >= 38000 AND rec.max_sal <= 55000,
                format('Mechanic salary out of range: %s-%s', rec.min_sal, rec.max_sal);
        ELSIF rec.role = 'agent' THEN
            ASSERT rec.min_sal >= 33000 AND rec.max_sal <= 48000,
                format('Agent salary out of range: %s-%s', rec.min_sal, rec.max_sal);
        END IF;
    END LOOP;
    RAISE NOTICE '[PASS] 3.4  Employee salaries are realistic per role';

    -- 3.5 Vehicle daily rates match category tiers
    FOR rec IN
        SELECT vc.name, MIN(v.daily_rate) as min_rate, MAX(v.daily_rate) as max_rate
        FROM vehicles v JOIN vehicle_categories vc ON v.category_id = vc.id
        GROUP BY vc.name
    LOOP
        IF rec.name = 'Economy' THEN
            ASSERT rec.max_rate <= 50, format('Economy max rate too high: %s', rec.max_rate);
        ELSIF rec.name = 'Luxury' THEN
            ASSERT rec.min_rate >= 85, format('Luxury min rate too low: %s', rec.min_rate);
        END IF;
    END LOOP;
    RAISE NOTICE '[PASS] 3.5  Vehicle daily rates match category tiers';

    -- 3.6 Seasonal booking pattern: summer > winter
    SELECT count(*) INTO v_summer FROM reservations
    WHERE EXTRACT(MONTH FROM pickup_date) IN (6, 7, 8);

    SELECT count(*) INTO v_winter FROM reservations
    WHERE EXTRACT(MONTH FROM pickup_date) IN (12, 1, 2);

    ASSERT v_summer > v_winter,
        format('Summer bookings (%s) should exceed winter (%s)', v_summer, v_winter);
    v_ratio := round(v_summer::NUMERIC / NULLIF(v_winter, 0), 2);
    RAISE NOTICE '[PASS] 3.6  Seasonal pattern: summer=%, winter=% (ratio %x)', v_summer, v_winter, v_ratio;

    -- 3.7 Reservation status distribution
    FOR rec IN
        SELECT status, count(*) as cnt,
               round(100.0 * count(*) / (SELECT count(*) FROM reservations), 1) as pct
        FROM reservations GROUP BY status ORDER BY cnt DESC
    LOOP
        IF rec.status = 'completed' THEN
            ASSERT rec.pct BETWEEN 55 AND 85,
                format('completed %% is %s (expected 55-85%%)', rec.pct);
        ELSIF rec.status = 'cancelled' THEN
            ASSERT rec.pct BETWEEN 3 AND 20,
                format('cancelled %% is %s (expected 3-20%%)', rec.pct);
        END IF;
    END LOOP;
    RAISE NOTICE '[PASS] 3.7  Reservation status distribution is realistic';

    -- 3.8 Payment method distribution
    FOR rec IN
        SELECT payment_method, count(*) as cnt,
               round(100.0 * count(*) / (SELECT count(*) FROM payments), 1) as pct
        FROM payments GROUP BY payment_method ORDER BY cnt DESC
    LOOP
        IF rec.payment_method = 'credit_card' THEN
            ASSERT rec.pct BETWEEN 45 AND 75,
                format('credit_card %% is %s (expected 45-75%%)', rec.pct);
        END IF;
    END LOOP;
    RAISE NOTICE '[PASS] 3.8  Payment method distribution is realistic';

    -- 3.9 Reviews only for completed reservations
    SELECT count(*) INTO v_count
    FROM reviews r
    JOIN reservations res ON r.reservation_id = res.id
    WHERE res.status != 'completed';
    ASSERT v_count = 0,
        format('Found %s reviews for non-completed reservations', v_count);
    RAISE NOTICE '[PASS] 3.9  Reviews exist only for completed reservations';

    -- 3.10 Review rating distribution is skewed toward 4-5
    SELECT round(avg(rating), 2) INTO v_val FROM reviews;
    ASSERT v_val BETWEEN 3.5 AND 4.8,
        format('Average rating %s is outside realistic range 3.5-4.8', v_val);
    RAISE NOTICE '[PASS] 3.10 Average review rating: % (realistic skew)', v_val;

    -- 3.11 No cancelled reservations have payments > 0
    SELECT count(*) INTO v_count
    FROM reservations r
    JOIN payments p ON p.reservation_id = r.id
    WHERE r.status = 'cancelled';
    ASSERT v_count = 0,
        format('Found %s payments for cancelled reservations', v_count);
    RAISE NOTICE '[PASS] 3.11 No payments for cancelled reservations';

    -- 3.12 Client ages are realistic (25-65ish at registration)
    SELECT MIN(EXTRACT(YEAR FROM age(registration_date, date_of_birth))) INTO v_min FROM clients;
    SELECT MAX(EXTRACT(YEAR FROM age(registration_date, date_of_birth))) INTO v_max FROM clients;
    ASSERT v_min >= 20, format('Youngest client at registration was %s years old', v_min);
    ASSERT v_max <= 80, format('Oldest client at registration was %s years old', v_max);
    RAISE NOTICE '[PASS] 3.12 Client ages at registration: %-% years', v_min, v_max;

    -- 3.13 Reservation durations are mostly 1-14 days
    SELECT round(avg(return_date - pickup_date), 1) INTO v_val FROM reservations;
    ASSERT v_val BETWEEN 2 AND 8,
        format('Average reservation duration %s days (expected 2-8)', v_val);
    RAISE NOTICE '[PASS] 3.13 Average reservation duration: % days', v_val;

    -- 3.14 Multiple distinct first and last names (not repetitive)
    SELECT count(DISTINCT first_name) INTO v_count FROM clients;
    ASSERT v_count >= 50, format('Only %s distinct first names (expected >=50)', v_count);
    SELECT count(DISTINCT last_name) INTO v_count FROM clients;
    ASSERT v_count >= 50, format('Only %s distinct last names (expected >=50)', v_count);
    RAISE NOTICE '[PASS] 3.14 Name diversity: 50+ distinct first and last names';

    -- 3.15 Vehicles span multiple makes
    SELECT count(DISTINCT make) INTO v_count FROM vehicles;
    ASSERT v_count >= 10, format('Only %s distinct makes (expected >=10)', v_count);
    RAISE NOTICE '[PASS] 3.15 Vehicle fleet has % distinct makes', v_count;

    -- 3.16 Dates span 2022-2025
    SELECT MIN(pickup_date) INTO rec FROM reservations;
    ASSERT rec.min IS NOT NULL AND EXTRACT(YEAR FROM rec.min) = 2022,
        'Earliest reservation should be in 2022';
    SELECT MAX(pickup_date) INTO rec FROM reservations;
    ASSERT rec.max IS NOT NULL AND EXTRACT(YEAR FROM rec.max) >= 2025,
        'Latest reservation should be in 2025';
    RAISE NOTICE '[PASS] 3.16 Reservation dates span 2022-2025';

    -- 3.17 Maintenance records cover multiple types
    SELECT count(DISTINCT maintenance_type) INTO v_count FROM maintenance_records;
    ASSERT v_count >= 7, format('Only %s maintenance types used (expected >=7)', v_count);
    RAISE NOTICE '[PASS] 3.17 Maintenance records cover % distinct types', v_count;

    RAISE NOTICE '--- 03: All data quality tests passed ---';
END $$;
