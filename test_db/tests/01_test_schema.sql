-- ============================================================
-- TEST 01: Schema Validation
-- Verify tables, columns, foreign keys, indexes, constraints
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_count INTEGER;
    v_expected_tables TEXT[] := ARRAY[
        'locations','employees','vehicle_categories','vehicles',
        'clients','reservations','payments','maintenance_records','reviews'
    ];
    v_tbl TEXT;
BEGIN
    RAISE NOTICE '--- 01: Schema Validation ---';

    -- 1.1 All 9 tables exist
    SELECT count(*) INTO v_count FROM pg_tables WHERE schemaname = 'public';
    ASSERT v_count = 9,
        format('Expected 9 tables, found %s', v_count);
    RAISE NOTICE '[PASS] 1.1  All 9 tables exist';

    -- 1.2 Each expected table exists by name
    FOREACH v_tbl IN ARRAY v_expected_tables LOOP
        SELECT count(*) INTO v_count FROM pg_tables
        WHERE schemaname = 'public' AND tablename = v_tbl;
        ASSERT v_count = 1,
            format('Table "%s" not found', v_tbl);
    END LOOP;
    RAISE NOTICE '[PASS] 1.2  All table names match expected list';

    -- 1.3 Foreign key count (should be at least 10 FK constraints)
    SELECT count(*) INTO v_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public';
    ASSERT v_count >= 10,
        format('Expected >=10 foreign keys, found %s', v_count);
    RAISE NOTICE '[PASS] 1.3  % foreign key constraints found', v_count;

    -- 1.4 CHECK constraint count (enums on status, payment_method, role, etc.)
    SELECT count(*) INTO v_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'CHECK' AND table_schema = 'public';
    ASSERT v_count >= 8,
        format('Expected >=8 CHECK constraints, found %s', v_count);
    RAISE NOTICE '[PASS] 1.4  % CHECK constraints found', v_count;

    -- 1.5 Index count (we created 10 custom indexes + PK/UNIQUE indexes)
    SELECT count(*) INTO v_count
    FROM pg_indexes WHERE schemaname = 'public';
    ASSERT v_count >= 15,
        format('Expected >=15 indexes, found %s', v_count);
    RAISE NOTICE '[PASS] 1.5  % indexes found', v_count;

    -- 1.6 Verify key columns exist with correct types
    -- reservations.total_cost should be numeric
    SELECT count(*) INTO v_count
    FROM information_schema.columns
    WHERE table_name = 'reservations' AND column_name = 'total_cost'
      AND data_type = 'numeric';
    ASSERT v_count = 1, 'reservations.total_cost should be NUMERIC';
    RAISE NOTICE '[PASS] 1.6  Monetary columns use NUMERIC type';

    -- 1.7 Verify SERIAL primary keys (integer + has default sequence)
    SELECT count(*) INTO v_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND column_name = 'id'
      AND data_type = 'integer'
      AND column_default LIKE 'nextval%';
    ASSERT v_count = 9,
        format('Expected 9 SERIAL PKs, found %s', v_count);
    RAISE NOTICE '[PASS] 1.7  All 9 tables use SERIAL primary keys';

    -- 1.8 Verify reservations has date constraint (return_date >= pickup_date)
    SELECT count(*) INTO v_count
    FROM information_schema.check_constraints cc
    JOIN information_schema.table_constraints tc
      ON cc.constraint_name = tc.constraint_name
    WHERE tc.table_name = 'reservations'
      AND cc.check_clause LIKE '%return_date%pickup_date%';
    ASSERT v_count >= 1, 'Missing date range CHECK on reservations';
    RAISE NOTICE '[PASS] 1.8  Reservations date range constraint exists';

    -- 1.9 Verify vehicles.year has CHECK constraint
    SELECT count(*) INTO v_count
    FROM information_schema.check_constraints cc
    JOIN information_schema.table_constraints tc
      ON cc.constraint_name = tc.constraint_name
    WHERE tc.table_name = 'vehicles'
      AND cc.check_clause LIKE '%year%';
    ASSERT v_count >= 1, 'Missing year CHECK on vehicles';
    RAISE NOTICE '[PASS] 1.9  Vehicles year range constraint exists';

    -- 1.10 Verify reviews.rating has CHECK constraint (1-5)
    SELECT count(*) INTO v_count
    FROM information_schema.check_constraints cc
    JOIN information_schema.table_constraints tc
      ON cc.constraint_name = tc.constraint_name
    WHERE tc.table_name = 'reviews'
      AND cc.check_clause LIKE '%rating%';
    ASSERT v_count >= 1, 'Missing rating CHECK on reviews';
    RAISE NOTICE '[PASS] 1.10 Reviews rating range constraint exists';

    RAISE NOTICE '--- 01: All schema tests passed ---';
END $$;
