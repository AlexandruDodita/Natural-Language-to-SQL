-- Read-only role for the AI SQL runner
CREATE USER readonly_user WITH PASSWORD 'readonly_pass';
GRANT CONNECT ON DATABASE car_rental TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
-- Ensure future tables are also covered
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;
