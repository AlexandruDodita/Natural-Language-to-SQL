-- ============================================================
-- Defense in depth: row-level security, restricted roles, resource limits
--
-- The RAG service already rewrites every query's AST to inject the user's
-- authorization predicates (see rag-service/policy.py). This file makes the
-- database enforce the same rules independently, so a bug in the application
-- layer cannot leak another branch's data.
--
-- IMPORTANT: the existing `readonly_user` setup from 03_readonly_user.sql is
-- preserved. Enabling RLS would otherwise hide every row from it, so it gets an
-- explicit permissive policy. Nothing that works today stops working.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Restricted roles (NOLOGIN: they are only ever reached with SET ROLE)
-- ------------------------------------------------------------
CREATE ROLE app_manager NOLOGIN;
CREATE ROLE app_agent   NOLOGIN;
CREATE ROLE app_analyst NOLOGIN;

GRANT USAGE ON SCHEMA public TO app_manager, app_agent, app_analyst;

-- The executor connects as readonly_user and switches role per request.
GRANT app_manager, app_agent, app_analyst TO readonly_user;

-- ------------------------------------------------------------
-- 2. Table and column privileges
-- ------------------------------------------------------------
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_manager;

-- Agents and analysts never see salaries: column-level privileges, so even a
-- query that slips past the application layer is rejected by the server.
GRANT SELECT ON
    locations, vehicle_categories, vehicles, clients, reservations,
    payments, maintenance_records, reviews
TO app_agent, app_analyst;

GRANT SELECT (id, location_id, first_name, last_name, role, hire_date, email, phone, created_at)
    ON employees TO app_agent, app_analyst;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO app_manager, app_agent, app_analyst;

-- ------------------------------------------------------------
-- 3. Row-level security
--
-- The scope is carried by the session GUC `app.location_id`, set by the
-- executor with set_config(..., is_local => true) inside the transaction.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_current_location() RETURNS INTEGER
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.location_id', true), '')::INTEGER
$$;

ALTER TABLE employees            ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles             ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations         ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments             ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients              ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_records  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews              ENABLE ROW LEVEL SECURITY;

-- 3a. Backwards compatibility: the current execution path is unaffected.
CREATE POLICY p_readonly_employees  ON employees           FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_vehicles   ON vehicles            FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_reserv     ON reservations        FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_payments   ON payments            FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_clients    ON clients             FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_maint      ON maintenance_records FOR SELECT TO readonly_user USING (true);
CREATE POLICY p_readonly_reviews    ON reviews             FOR SELECT TO readonly_user USING (true);

-- 3b. Managers and analysts read company-wide (column privileges still apply).
CREATE POLICY p_manager_employees ON employees           FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_vehicles  ON vehicles            FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_reserv    ON reservations        FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_payments  ON payments            FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_clients   ON clients             FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_maint     ON maintenance_records FOR SELECT TO app_manager, app_analyst USING (true);
CREATE POLICY p_manager_reviews   ON reviews             FOR SELECT TO app_manager, app_analyst USING (true);

-- 3c. Agents are confined to their own branch. A missing app.location_id
--     yields NULL, so the predicate is false and nothing is returned
--     (fail closed).
CREATE POLICY p_agent_employees ON employees FOR SELECT TO app_agent
    USING (location_id = app_current_location());

CREATE POLICY p_agent_vehicles ON vehicles FOR SELECT TO app_agent
    USING (location_id = app_current_location());

CREATE POLICY p_agent_reservations ON reservations FOR SELECT TO app_agent
    USING (pickup_location = app_current_location());

CREATE POLICY p_agent_payments ON payments FOR SELECT TO app_agent
    USING (reservation_id IN (
        SELECT r.id FROM reservations r
        WHERE r.pickup_location = app_current_location()
    ));

CREATE POLICY p_agent_clients ON clients FOR SELECT TO app_agent
    USING (id IN (
        SELECT r.client_id FROM reservations r
        WHERE r.pickup_location = app_current_location()
    ));

CREATE POLICY p_agent_maintenance ON maintenance_records FOR SELECT TO app_agent
    USING (vehicle_id IN (
        SELECT v.id FROM vehicles v
        WHERE v.location_id = app_current_location()
    ));

CREATE POLICY p_agent_reviews ON reviews FOR SELECT TO app_agent
    USING (reservation_id IN (
        SELECT r.id FROM reservations r
        WHERE r.pickup_location = app_current_location()
    ));

-- ------------------------------------------------------------
-- 4. Resource limits (role level, so they apply to every connection without
--    any application change)
-- ------------------------------------------------------------
ALTER ROLE readonly_user SET statement_timeout = '5s';
ALTER ROLE readonly_user SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE readonly_user SET default_transaction_read_only = on;
ALTER ROLE readonly_user SET lock_timeout = '2s';
ALTER ROLE readonly_user CONNECTION LIMIT 10;

ALTER ROLE app_manager SET statement_timeout = '5s';
ALTER ROLE app_agent   SET statement_timeout = '5s';
ALTER ROLE app_analyst SET statement_timeout = '5s';

-- Table comments double as retrieval documents for the RAG service.
COMMENT ON TABLE locations           IS 'Branch offices of the rental company';
COMMENT ON TABLE employees           IS 'Staff assigned to a branch; salary is restricted data';
COMMENT ON TABLE vehicle_categories  IS 'Vehicle classes with their daily rate range';
COMMENT ON TABLE vehicles            IS 'Fleet: make, model, year, daily rate, mileage and availability status';
COMMENT ON TABLE clients             IS 'Customers who rent vehicles';
COMMENT ON TABLE reservations        IS 'Rental bookings: client, vehicle, pickup and return branch, dates and total cost';
COMMENT ON TABLE payments            IS 'Payments settled against reservations';
COMMENT ON TABLE maintenance_records IS 'Service and repair history per vehicle, with cost';
COMMENT ON TABLE reviews             IS 'Customer ratings (1-5) and comments left after a rental';
