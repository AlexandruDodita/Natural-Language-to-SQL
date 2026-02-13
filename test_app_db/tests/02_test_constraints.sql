-- ============================================================
-- TEST 02: Constraint Strictness
-- Attempt invalid inserts/updates — every one MUST fail.
-- Uses savepoints so one failure doesn't abort the block.
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_passed INTEGER := 0;
    v_total  INTEGER := 0;
BEGIN
    RAISE NOTICE '--- 02: Constraint Strictness ---';

    -- Helper: each test does BEGIN/EXCEPTION inside a subtransaction

    -- 2.1 Invalid vehicle status
    v_total := v_total + 1;
    BEGIN
        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, daily_rate, mileage, status)
        VALUES (1, 1, 'Test', 'Car', 2020, 'ZZZ-TEST01', 50, 0, 'stolen');
        RAISE NOTICE '[FAIL] 2.1  Invalid vehicle status "stolen" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.1  Rejected invalid vehicle status "stolen"';
    END;

    -- 2.2 Invalid reservation status
    v_total := v_total + 1;
    BEGIN
        INSERT INTO reservations (client_id, vehicle_id, pickup_location, return_location, pickup_date, return_date, status, total_cost)
        VALUES (1, 1, 1, 1, '2024-01-01', '2024-01-05', 'expired', 200);
        RAISE NOTICE '[FAIL] 2.2  Invalid reservation status "expired" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.2  Rejected invalid reservation status "expired"';
    END;

    -- 2.3 Invalid payment method
    v_total := v_total + 1;
    BEGIN
        INSERT INTO payments (reservation_id, amount, payment_method, payment_date, status)
        VALUES (1, 100, 'bitcoin', '2024-01-01', 'completed');
        RAISE NOTICE '[FAIL] 2.3  Invalid payment method "bitcoin" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.3  Rejected invalid payment method "bitcoin"';
    END;

    -- 2.4 Invalid employee role
    v_total := v_total + 1;
    BEGIN
        INSERT INTO employees (location_id, first_name, last_name, role, salary, hire_date)
        VALUES (1, 'Test', 'User', 'intern', 20000, '2024-01-01');
        RAISE NOTICE '[FAIL] 2.4  Invalid role "intern" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.4  Rejected invalid employee role "intern"';
    END;

    -- 2.5 Vehicle year out of range (too old)
    v_total := v_total + 1;
    BEGIN
        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, daily_rate, mileage, status)
        VALUES (1, 1, 'Test', 'Car', 2005, 'ZZZ-TEST02', 50, 0, 'available');
        RAISE NOTICE '[FAIL] 2.5  Year 2005 was accepted (below 2015)';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.5  Rejected vehicle year 2005 (below minimum 2015)';
    END;

    -- 2.6 Vehicle year out of range (too new)
    v_total := v_total + 1;
    BEGIN
        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, daily_rate, mileage, status)
        VALUES (1, 1, 'Test', 'Car', 2030, 'ZZZ-TEST03', 50, 0, 'available');
        RAISE NOTICE '[FAIL] 2.6  Year 2030 was accepted (above 2025)';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.6  Rejected vehicle year 2030 (above maximum 2025)';
    END;

    -- 2.7 Review rating out of range (0)
    v_total := v_total + 1;
    BEGIN
        INSERT INTO reviews (reservation_id, rating, comment, review_date)
        VALUES (1, 0, 'Invalid', '2024-01-01');
        RAISE NOTICE '[FAIL] 2.7  Rating 0 was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.7  Rejected review rating 0 (below minimum 1)';
    END;

    -- 2.8 Review rating out of range (6)
    v_total := v_total + 1;
    BEGIN
        INSERT INTO reviews (reservation_id, rating, comment, review_date)
        VALUES (1, 6, 'Invalid', '2024-01-01');
        RAISE NOTICE '[FAIL] 2.8  Rating 6 was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.8  Rejected review rating 6 (above maximum 5)';
    END;

    -- 2.9 Reservation with return_date < pickup_date
    v_total := v_total + 1;
    BEGIN
        INSERT INTO reservations (client_id, vehicle_id, pickup_location, return_location, pickup_date, return_date, status, total_cost)
        VALUES (1, 1, 1, 1, '2024-01-10', '2024-01-05', 'confirmed', 200);
        RAISE NOTICE '[FAIL] 2.9  return_date before pickup_date was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.9  Rejected return_date before pickup_date';
    END;

    -- 2.10 Duplicate license plate (uniqueness)
    v_total := v_total + 1;
    DECLARE
        v_existing_plate TEXT;
    BEGIN
        SELECT license_plate INTO v_existing_plate FROM vehicles LIMIT 1;
        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, daily_rate, mileage, status)
        VALUES (1, 1, 'Dupe', 'Car', 2022, v_existing_plate, 50, 0, 'available');
        RAISE NOTICE '[FAIL] 2.10 Duplicate license plate was accepted';
    EXCEPTION WHEN unique_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.10 Rejected duplicate license plate';
    END;

    -- 2.11 Duplicate client email (uniqueness)
    v_total := v_total + 1;
    DECLARE
        v_existing_email TEXT;
    BEGIN
        SELECT email INTO v_existing_email FROM clients LIMIT 1;
        INSERT INTO clients (first_name, last_name, email, drivers_license, date_of_birth)
        VALUES ('Dupe', 'Client', v_existing_email, 'DL-DUPE-01', '1990-01-01');
        RAISE NOTICE '[FAIL] 2.11 Duplicate email was accepted';
    EXCEPTION WHEN unique_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.11 Rejected duplicate client email';
    END;

    -- 2.12 FK violation — reservation referencing non-existent client
    v_total := v_total + 1;
    BEGIN
        INSERT INTO reservations (client_id, vehicle_id, pickup_location, return_location, pickup_date, return_date, status, total_cost)
        VALUES (99999, 1, 1, 1, '2024-01-01', '2024-01-05', 'confirmed', 200);
        RAISE NOTICE '[FAIL] 2.12 Non-existent client_id 99999 was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.12 Rejected FK to non-existent client';
    END;

    -- 2.13 FK violation — vehicle referencing non-existent category
    v_total := v_total + 1;
    BEGIN
        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, daily_rate, mileage, status)
        VALUES (999, 1, 'Ghost', 'Cat', 2022, 'ZZZ-FK01', 50, 0, 'available');
        RAISE NOTICE '[FAIL] 2.13 Non-existent category_id 999 was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.13 Rejected FK to non-existent vehicle category';
    END;

    -- 2.14 FK violation — payment referencing non-existent reservation
    v_total := v_total + 1;
    BEGIN
        INSERT INTO payments (reservation_id, amount, payment_method, payment_date, status)
        VALUES (99999, 50, 'cash', '2024-01-01', 'completed');
        RAISE NOTICE '[FAIL] 2.14 Non-existent reservation_id 99999 was accepted';
    EXCEPTION WHEN foreign_key_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.14 Rejected FK to non-existent reservation';
    END;

    -- 2.15 Invalid maintenance type
    v_total := v_total + 1;
    BEGIN
        INSERT INTO maintenance_records (vehicle_id, maintenance_type, cost, maintenance_date)
        VALUES (1, 'paint_job', 500, '2024-01-01');
        RAISE NOTICE '[FAIL] 2.15 Invalid maintenance type "paint_job" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.15 Rejected invalid maintenance type "paint_job"';
    END;

    -- 2.16 Invalid payment status
    v_total := v_total + 1;
    BEGIN
        INSERT INTO payments (reservation_id, amount, payment_method, payment_date, status)
        VALUES (1, 50, 'cash', '2024-01-01', 'void');
        RAISE NOTICE '[FAIL] 2.16 Invalid payment status "void" was accepted';
    EXCEPTION WHEN check_violation THEN
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.16 Rejected invalid payment status "void"';
    END;

    -- 2.17 ON DELETE CASCADE — deleting a location cascades to employees
    v_total := v_total + 1;
    DECLARE
        v_loc_id INTEGER;
        v_emp_before INTEGER;
        v_emp_after INTEGER;
    BEGIN
        -- Create a temp location + employee, then delete location
        INSERT INTO locations (name, city, address) VALUES ('Temp Branch', 'Nowhere', '123 Test St')
            RETURNING id INTO v_loc_id;
        INSERT INTO employees (location_id, first_name, last_name, role, salary, hire_date)
            VALUES (v_loc_id, 'Temp', 'Worker', 'agent', 30000, '2024-01-01');
        SELECT count(*) INTO v_emp_before FROM employees WHERE location_id = v_loc_id;
        DELETE FROM locations WHERE id = v_loc_id;
        SELECT count(*) INTO v_emp_after FROM employees WHERE location_id = v_loc_id;
        ASSERT v_emp_before = 1 AND v_emp_after = 0,
            'CASCADE delete did not remove employee';
        v_passed := v_passed + 1;
        RAISE NOTICE '[PASS] 2.17 ON DELETE CASCADE works (location -> employees)';
    END;

    -- Summary
    RAISE NOTICE '--- 02: Passed %/% constraint tests ---', v_passed, v_total;
    ASSERT v_passed = v_total,
        format('Some constraint tests failed: %s/%s', v_passed, v_total);
END $$;
