-- ============================================================
-- Car Rental Service — Seed Data
-- Pure PostgreSQL generation (arrays, generate_series, random)
-- ============================================================

-- Deterministic-ish seed (reset on each run of this script)
SELECT setseed(0.42);

-- ============================================================
-- 1. Locations (~10)
-- ============================================================
INSERT INTO locations (name, city, address, phone) VALUES
    ('Downtown Hub',        'New York',     '350 5th Avenue, NY 10118',          '(212) 555-0101'),
    ('Airport Terminal',    'Los Angeles',  '1 World Way, LA 90045',             '(310) 555-0102'),
    ('Central Station',     'Chicago',      '225 S Canal St, Chicago 60606',     '(312) 555-0103'),
    ('Harbor Point',        'Miami',        '1000 Biscayne Blvd, Miami 33132',  '(305) 555-0104'),
    ('Tech District',       'San Francisco','101 Market St, SF 94105',           '(415) 555-0105'),
    ('Capitol Branch',      'Washington DC','1200 Pennsylvania Ave, DC 20004',   '(202) 555-0106'),
    ('Lakeside Office',     'Seattle',      '400 Pine St, Seattle 98101',        '(206) 555-0107'),
    ('Desert Gateway',      'Phoenix',      '3400 E Sky Harbor, Phoenix 85034',  '(480) 555-0108'),
    ('Peachtree Center',    'Atlanta',      '225 Peachtree St NE, Atlanta 30303','(404) 555-0109'),
    ('Historic Quarter',    'Boston',       '100 Summer St, Boston 02110',       '(617) 555-0110');

-- ============================================================
-- 2. Vehicle Categories (5)
-- ============================================================
INSERT INTO vehicle_categories (name, description, daily_rate_min, daily_rate_max) VALUES
    ('Economy',  'Small fuel-efficient cars for budget-conscious travelers',  25.00,  45.00),
    ('Compact',  'Mid-size sedans with good comfort and fuel economy',        40.00,  65.00),
    ('SUV',      'Spacious sport utility vehicles for families and groups',   55.00,  95.00),
    ('Luxury',   'Premium vehicles with top-tier comfort and features',       90.00, 180.00),
    ('Van',      'Large passenger and cargo vans for groups or moving',       60.00, 110.00);

-- ============================================================
-- 3. Vehicles (~80)
-- ============================================================
DO $$
DECLARE
    v_makes TEXT[][] := ARRAY[
        -- category 1: Economy
        ARRAY['Toyota',  'Yaris'],
        ARRAY['Honda',   'Fit'],
        ARRAY['Nissan',  'Versa'],
        ARRAY['Hyundai', 'Accent'],
        ARRAY['Kia',     'Rio'],
        ARRAY['Chevrolet','Spark'],
        -- category 2: Compact
        ARRAY['Toyota',  'Corolla'],
        ARRAY['Honda',   'Civic'],
        ARRAY['Mazda',   '3'],
        ARRAY['Hyundai', 'Elantra'],
        ARRAY['Volkswagen','Jetta'],
        ARRAY['Nissan',  'Sentra'],
        -- category 3: SUV
        ARRAY['Toyota',  'RAV4'],
        ARRAY['Honda',   'CR-V'],
        ARRAY['Ford',    'Escape'],
        ARRAY['Jeep',    'Cherokee'],
        ARRAY['Chevrolet','Equinox'],
        ARRAY['Hyundai', 'Tucson'],
        -- category 4: Luxury
        ARRAY['BMW',     '3 Series'],
        ARRAY['Mercedes','C-Class'],
        ARRAY['Audi',    'A4'],
        ARRAY['Lexus',   'ES'],
        ARRAY['Tesla',   'Model 3'],
        ARRAY['Cadillac','CT5'],
        -- category 5: Van
        ARRAY['Toyota',  'Sienna'],
        ARRAY['Honda',   'Odyssey'],
        ARRAY['Chrysler','Pacifica'],
        ARRAY['Ford',    'Transit'],
        ARRAY['Mercedes','Sprinter'],
        ARRAY['Kia',     'Carnival']
    ];
    v_colors TEXT[] := ARRAY['White','Black','Silver','Gray','Blue','Red','Green','Pearl White','Midnight Blue','Burgundy'];
    v_cat_id INTEGER;
    v_loc_id INTEGER;
    v_idx INTEGER;
    v_year INTEGER;
    v_rate NUMERIC;
    v_mileage INTEGER;
    v_plate TEXT;
    v_make TEXT;
    v_model TEXT;
    v_color TEXT;
    v_status TEXT;
    v_status_roll DOUBLE PRECISION;
    plate_suffix INTEGER := 1000;
BEGIN
    FOR i IN 1..80 LOOP
        -- Determine category (1-5) based on index ranges
        IF i <= 18 THEN
            v_cat_id := 1; v_idx := ((i - 1) % 6) + 1;         -- Economy (indices 1-6)
        ELSIF i <= 34 THEN
            v_cat_id := 2; v_idx := ((i - 1) % 6) + 7;         -- Compact (indices 7-12)
        ELSIF i <= 52 THEN
            v_cat_id := 3; v_idx := ((i - 1) % 6) + 13;        -- SUV (indices 13-18)
        ELSIF i <= 64 THEN
            v_cat_id := 4; v_idx := ((i - 1) % 6) + 19;        -- Luxury (indices 19-24)
        ELSE
            v_cat_id := 5; v_idx := ((i - 1) % 6) + 25;        -- Van (indices 25-30)
        END IF;

        v_make  := v_makes[v_idx][1];
        v_model := v_makes[v_idx][2];
        v_loc_id := (i % 10) + 1;
        v_year   := 2018 + (random() * 6)::INTEGER;
        v_color  := v_colors[1 + (random() * (array_length(v_colors, 1) - 1))::INTEGER];
        v_mileage := (5000 + random() * 80000)::INTEGER;

        -- Daily rate within category range
        SELECT daily_rate_min + random() * (daily_rate_max - daily_rate_min)
          INTO v_rate
          FROM vehicle_categories WHERE id = v_cat_id;
        v_rate := round(v_rate, 2);

        -- License plate
        plate_suffix := plate_suffix + 1;
        v_plate := chr(65 + (i % 26)) || chr(65 + ((i * 3) % 26)) || chr(65 + ((i * 7) % 26))
                   || '-' || plate_suffix::TEXT;

        -- Status: 80% available, 10% rented, 5% maintenance, 5% retired
        v_status_roll := random();
        IF v_status_roll < 0.80 THEN v_status := 'available';
        ELSIF v_status_roll < 0.90 THEN v_status := 'rented';
        ELSIF v_status_roll < 0.95 THEN v_status := 'maintenance';
        ELSE v_status := 'retired';
        END IF;

        INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, color, daily_rate, mileage, status)
        VALUES (v_cat_id, v_loc_id, v_make, v_model, v_year, v_plate, v_color, v_rate, v_mileage, v_status);
    END LOOP;
END $$;

-- ============================================================
-- 4. Employees (~40)
-- ============================================================
DO $$
DECLARE
    first_names TEXT[] := ARRAY[
        'James','Mary','Robert','Patricia','John','Jennifer','Michael','Linda',
        'David','Elizabeth','William','Barbara','Richard','Susan','Joseph','Jessica',
        'Thomas','Sarah','Christopher','Karen','Daniel','Lisa','Matthew','Nancy',
        'Anthony','Betty','Mark','Margaret','Donald','Sandra','Steven','Ashley',
        'Andrew','Dorothy','Paul','Kimberly','Joshua','Emily','Kenneth','Donna'
    ];
    last_names TEXT[] := ARRAY[
        'Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
        'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
        'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
        'White','Harris','Sanchez','Clark','Ramirez','Lewis','Robinson','Walker',
        'Young','Allen','King','Wright','Scott','Torres','Nguyen','Hill','Flores'
    ];
    roles TEXT[] := ARRAY['manager','agent','agent','agent','mechanic','receptionist','agent','mechanic'];
    v_role TEXT;
    v_salary NUMERIC;
    v_hire DATE;
    v_fn TEXT;
    v_ln TEXT;
BEGIN
    FOR loc IN 1..10 LOOP
        FOR emp IN 1..4 LOOP
            v_fn := first_names[1 + (random() * (array_length(first_names, 1) - 1))::INTEGER];
            v_ln := last_names[1 + (random() * (array_length(last_names, 1) - 1))::INTEGER];
            v_role := roles[emp]; -- 1 manager, 2-3 agents+mechanic, 4 receptionist per location

            IF v_role = 'manager' THEN
                v_salary := 55000 + (random() * 15000)::INTEGER;
            ELSIF v_role = 'mechanic' THEN
                v_salary := 40000 + (random() * 10000)::INTEGER;
            ELSIF v_role = 'agent' THEN
                v_salary := 35000 + (random() * 10000)::INTEGER;
            ELSE
                v_salary := 30000 + (random() * 8000)::INTEGER;
            END IF;

            v_hire := '2020-01-01'::DATE + (random() * 1800)::INTEGER;

            INSERT INTO employees (location_id, first_name, last_name, role, salary, hire_date, email, phone)
            VALUES (
                loc, v_fn, v_ln, v_role, v_salary, v_hire,
                lower(v_fn || '.' || v_ln || emp::TEXT || '@carrental.com'),
                '(555) ' || lpad((100 + (random() * 899)::INTEGER)::TEXT, 3, '0') || '-' || lpad((1000 + (random() * 8999)::INTEGER)::TEXT, 4, '0')
            );
        END LOOP;
    END LOOP;
END $$;

-- ============================================================
-- 5. Clients (~600)
-- ============================================================
DO $$
DECLARE
    first_names TEXT[] := ARRAY[
        'James','Mary','Robert','Patricia','John','Jennifer','Michael','Linda',
        'David','Elizabeth','William','Barbara','Richard','Susan','Joseph','Jessica',
        'Thomas','Sarah','Christopher','Karen','Daniel','Lisa','Matthew','Nancy',
        'Anthony','Betty','Mark','Margaret','Donald','Sandra','Steven','Ashley',
        'Andrew','Dorothy','Paul','Kimberly','Joshua','Emily','Kenneth','Donna',
        'George','Carol','Edward','Michelle','Brian','Amanda','Ronald','Melissa',
        'Timothy','Deborah','Jason','Stephanie','Jeffrey','Rebecca','Ryan','Sharon',
        'Jacob','Laura','Gary','Cynthia','Nicholas','Kathleen','Eric','Amy',
        'Jonathan','Angela','Stephen','Shirley','Larry','Brenda','Justin','Emma',
        'Scott','Anna','Brandon','Pamela','Benjamin','Nicole','Samuel','Helen',
        'Raymond','Samantha','Gregory','Katherine','Frank','Christine','Alexander','Debra',
        'Patrick','Rachel','Jack','Carolyn','Dennis','Janet','Jerry','Catherine',
        'Tyler','Maria','Aaron','Heather','Jose','Diane','Adam','Ruth',
        'Nathan','Julie','Henry','Olivia','Zachary','Joyce','Douglas','Virginia'
    ];
    last_names TEXT[] := ARRAY[
        'Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
        'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
        'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
        'White','Harris','Sanchez','Clark','Ramirez','Lewis','Robinson','Walker',
        'Young','Allen','King','Wright','Scott','Torres','Nguyen','Hill','Flores',
        'Green','Adams','Nelson','Baker','Hall','Rivera','Campbell','Mitchell',
        'Carter','Roberts','Gomez','Phillips','Evans','Turner','Diaz','Parker',
        'Cruz','Edwards','Collins','Reyes','Stewart','Morris','Morales','Murphy',
        'Cook','Rogers','Gutierrez','Ortiz','Morgan','Cooper','Peterson','Bailey',
        'Reed','Kelly','Howard','Ramos','Kim','Cox','Ward','Richardson',
        'Watson','Brooks','Chavez','Wood','James','Bennett','Gray','Mendoza',
        'Ruiz','Hughes','Price','Alvarez','Castillo','Sanders','Patel','Myers',
        'Long','Ross','Foster','Jimenez','Powell','Jenkins','Perry','Russell',
        'Sullivan','Bell','Coleman','Butler','Henderson','Barnes','Gonzales','Fisher'
    ];
    v_fn TEXT;
    v_ln TEXT;
    v_email TEXT;
    v_dob DATE;
    v_reg DATE;
    v_dl TEXT;
BEGIN
    FOR i IN 1..600 LOOP
        v_fn := first_names[1 + (random() * (array_length(first_names, 1) - 1))::INTEGER];
        v_ln := last_names[1 + (random() * (array_length(last_names, 1) - 1))::INTEGER];
        -- Unique email with number suffix
        v_email := lower(v_fn || '.' || v_ln || i::TEXT || '@email.com');
        v_dob := '1960-01-01'::DATE + (random() * 18000)::INTEGER;  -- ages ~25-65
        v_reg := '2022-01-01'::DATE + (random() * 1095)::INTEGER;   -- 2022-2024
        v_dl  := 'DL' || lpad(i::TEXT, 6, '0') || chr(65 + (i % 26));

        INSERT INTO clients (first_name, last_name, email, phone, drivers_license, date_of_birth, registration_date)
        VALUES (
            v_fn, v_ln, v_email,
            '(555) ' || lpad((100 + (random() * 899)::INTEGER)::TEXT, 3, '0') || '-' || lpad((1000 + (random() * 8999)::INTEGER)::TEXT, 4, '0'),
            v_dl, v_dob, v_reg
        );
    END LOOP;
END $$;

-- ============================================================
-- 6. Reservations (~3000) with seasonal patterns
-- ============================================================
DO $$
DECLARE
    v_client INTEGER;
    v_vehicle INTEGER;
    v_pickup_loc INTEGER;
    v_return_loc INTEGER;
    v_pickup DATE;
    v_duration INTEGER;
    v_return DATE;
    v_status TEXT;
    v_status_roll DOUBLE PRECISION;
    v_daily_rate NUMERIC;
    v_total NUMERIC;
    v_month INTEGER;
    v_seasonal_boost DOUBLE PRECISION;
BEGIN
    FOR i IN 1..3000 LOOP
        v_client  := 1 + (random() * 599)::INTEGER;
        v_vehicle := 1 + (random() * 79)::INTEGER;

        -- Spread pickups across 2022-01 to 2025-06
        v_pickup := '2022-01-01'::DATE + (random() * 1276)::INTEGER;

        -- Seasonal weighting: re-roll dates in winter months to create summer bias
        v_month := EXTRACT(MONTH FROM v_pickup)::INTEGER;
        v_seasonal_boost := CASE
            WHEN v_month IN (6,7,8) THEN 0.0   -- summer: keep all
            WHEN v_month IN (5,9) THEN 0.15     -- shoulder: re-roll 15%
            WHEN v_month IN (12,1,2) THEN 0.35  -- winter: re-roll 35%
            ELSE 0.20                            -- other: re-roll 20%
        END;
        IF random() < v_seasonal_boost THEN
            -- Re-roll to a summer month
            v_pickup := ('2022-06-01'::DATE + (random() * 91)::INTEGER)
                        + (INTERVAL '1 year' * (random() * 3)::INTEGER);
            IF v_pickup > '2025-06-30'::DATE THEN
                v_pickup := '2025-06-01'::DATE + (random() * 29)::INTEGER;
            END IF;
        END IF;

        -- Duration: weighted toward 2-5 days
        v_duration := CASE
            WHEN random() < 0.10 THEN 1
            WHEN random() < 0.55 THEN 2 + (random() * 3)::INTEGER   -- 2-4 days
            WHEN random() < 0.85 THEN 5 + (random() * 3)::INTEGER   -- 5-7 days
            ELSE 8 + (random() * 6)::INTEGER                         -- 8-14 days
        END;
        v_return := v_pickup + v_duration;

        v_pickup_loc := 1 + (random() * 9)::INTEGER;
        -- 80% same-location return
        IF random() < 0.80 THEN
            v_return_loc := v_pickup_loc;
        ELSE
            v_return_loc := 1 + (random() * 9)::INTEGER;
        END IF;

        -- Status: 70% completed, 12% confirmed, 8% no_show, 10% cancelled
        v_status_roll := random();
        IF v_pickup > CURRENT_DATE THEN
            v_status := 'confirmed';
        ELSIF v_status_roll < 0.70 THEN
            v_status := 'completed';
        ELSIF v_status_roll < 0.82 THEN
            v_status := 'confirmed';
        ELSIF v_status_roll < 0.90 THEN
            v_status := 'no_show';
        ELSE
            v_status := 'cancelled';
        END IF;

        -- Calculate total cost
        SELECT daily_rate INTO v_daily_rate FROM vehicles WHERE id = v_vehicle;
        v_total := v_daily_rate * v_duration;
        -- Add small random surcharges (insurance, fees)
        v_total := v_total + (random() * 30)::NUMERIC(10,2);
        v_total := round(v_total, 2);

        IF v_status = 'cancelled' THEN
            v_total := 0;
        END IF;

        INSERT INTO reservations (client_id, vehicle_id, pickup_location, return_location, pickup_date, return_date, status, total_cost)
        VALUES (v_client, v_vehicle, v_pickup_loc, v_return_loc, v_pickup, v_return, v_status, v_total);
    END LOOP;
END $$;

-- ============================================================
-- 7. Payments (~2800 — one per non-cancelled reservation)
-- ============================================================
INSERT INTO payments (reservation_id, amount, payment_method, payment_date, status)
SELECT
    r.id,
    r.total_cost,
    CASE
        WHEN random() < 0.60 THEN 'credit_card'
        WHEN random() < 0.85 THEN 'debit_card'
        ELSE 'cash'
    END,
    r.pickup_date - (random() * 5)::INTEGER,  -- paid 0-5 days before pickup
    CASE
        WHEN r.status = 'no_show' AND random() < 0.3 THEN 'refunded'
        WHEN random() < 0.02 THEN 'pending'
        ELSE 'completed'
    END
FROM reservations r
WHERE r.status != 'cancelled';

-- ============================================================
-- 8. Maintenance Records (~400)
-- ============================================================
DO $$
DECLARE
    maint_types TEXT[] := ARRAY['oil_change','tire_rotation','brake_service','general_inspection',
                                'engine_repair','body_repair','transmission','ac_service','battery_replacement'];
    maint_descriptions TEXT[] := ARRAY[
        'Routine oil and filter change',
        'Rotated all four tires, checked tread depth',
        'Replaced front brake pads and rotors',
        'Full multi-point vehicle inspection',
        'Diagnosed and repaired engine misfire',
        'Fixed minor dent on rear quarter panel',
        'Transmission fluid flush and filter replacement',
        'Recharged AC refrigerant, replaced cabin filter',
        'Replaced 12V battery with new unit'
    ];
    v_vehicle INTEGER;
    v_type TEXT;
    v_desc TEXT;
    v_cost NUMERIC;
    v_date DATE;
    v_mileage INTEGER;
    v_idx INTEGER;
BEGIN
    FOR i IN 1..400 LOOP
        v_vehicle := 1 + (random() * 79)::INTEGER;
        v_idx := 1 + (random() * (array_length(maint_types, 1) - 1))::INTEGER;
        v_type := maint_types[v_idx];
        v_desc := maint_descriptions[v_idx];

        v_cost := CASE
            WHEN v_type = 'oil_change' THEN 40 + (random() * 30)::NUMERIC
            WHEN v_type = 'tire_rotation' THEN 30 + (random() * 20)::NUMERIC
            WHEN v_type = 'brake_service' THEN 150 + (random() * 200)::NUMERIC
            WHEN v_type = 'general_inspection' THEN 50 + (random() * 50)::NUMERIC
            WHEN v_type = 'engine_repair' THEN 300 + (random() * 700)::NUMERIC
            WHEN v_type = 'body_repair' THEN 200 + (random() * 500)::NUMERIC
            WHEN v_type = 'transmission' THEN 400 + (random() * 600)::NUMERIC
            WHEN v_type = 'ac_service' THEN 80 + (random() * 120)::NUMERIC
            ELSE 100 + (random() * 80)::NUMERIC  -- battery
        END;
        v_cost := round(v_cost, 2);

        v_date := '2022-01-01'::DATE + (random() * 1276)::INTEGER;

        SELECT mileage INTO v_mileage FROM vehicles WHERE id = v_vehicle;
        v_mileage := v_mileage - (random() * 20000)::INTEGER;
        IF v_mileage < 1000 THEN v_mileage := 1000 + (random() * 5000)::INTEGER; END IF;

        INSERT INTO maintenance_records (vehicle_id, maintenance_type, description, cost, maintenance_date, mileage_at_service, completed)
        VALUES (v_vehicle, v_type, v_desc, v_cost, v_date, v_mileage, random() > 0.03);
    END LOOP;
END $$;

-- ============================================================
-- 9. Reviews (~1200 — only for completed reservations)
-- ============================================================
DO $$
DECLARE
    positive_comments TEXT[] := ARRAY[
        'Great experience! Car was clean and well maintained.',
        'Excellent service, would definitely rent again.',
        'Very smooth pickup and return process.',
        'The car was in perfect condition. Highly recommend!',
        'Friendly staff and great vehicle selection.',
        'Best rental experience I''ve had. Five stars!',
        'Car drove beautifully. No complaints at all.',
        'Quick and easy. Professional service throughout.',
        'Wonderful experience from start to finish.',
        'Everything went perfectly. Will be back!'
    ];
    neutral_comments TEXT[] := ARRAY[
        'Decent experience overall. Car was okay.',
        'Average service, nothing special but got the job done.',
        'Car had some minor wear but was functional.',
        'Pickup took a bit longer than expected.',
        'Fine for the price. Met basic expectations.',
        'Acceptable condition. A bit dated interior.',
        'Service was adequate. Room for improvement.',
        'Got what I paid for. No major issues.'
    ];
    negative_comments TEXT[] := ARRAY[
        'Car was not clean when I picked it up.',
        'Had mechanical issues during the rental.',
        'Long wait times at pickup. Frustrating experience.',
        'Vehicle did not match the description online.',
        'Poor customer service. Would not recommend.',
        'Car broke down during my trip. Very disappointing.'
    ];
    v_res_id INTEGER;
    v_rating INTEGER;
    v_comment TEXT;
    v_rating_roll DOUBLE PRECISION;
    v_date DATE;
    v_counter INTEGER := 0;
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT id, return_date
        FROM reservations
        WHERE status = 'completed'
        ORDER BY random()
        LIMIT 1200
    LOOP
        v_res_id := rec.id;
        v_date := rec.return_date + (random() * 14)::INTEGER;  -- review 0-14 days after return

        -- Rating distribution: skewed toward 4-5
        v_rating_roll := random();
        IF v_rating_roll < 0.02 THEN
            v_rating := 1;
        ELSIF v_rating_roll < 0.07 THEN
            v_rating := 2;
        ELSIF v_rating_roll < 0.18 THEN
            v_rating := 3;
        ELSIF v_rating_roll < 0.50 THEN
            v_rating := 4;
        ELSE
            v_rating := 5;
        END IF;

        -- Pick comment based on rating
        IF v_rating >= 4 THEN
            v_comment := positive_comments[1 + (random() * (array_length(positive_comments, 1) - 1))::INTEGER];
        ELSIF v_rating = 3 THEN
            v_comment := neutral_comments[1 + (random() * (array_length(neutral_comments, 1) - 1))::INTEGER];
        ELSE
            v_comment := negative_comments[1 + (random() * (array_length(negative_comments, 1) - 1))::INTEGER];
        END IF;

        INSERT INTO reviews (reservation_id, rating, comment, review_date)
        VALUES (v_res_id, v_rating, v_comment, v_date);
    END LOOP;
END $$;

-- ============================================================
-- Final: Refresh statistics for query planner
-- ============================================================
ANALYZE;
