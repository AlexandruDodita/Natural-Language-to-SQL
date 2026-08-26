-- ============================================================
-- Read-only Oracle user for the MCP server
-- ============================================================
-- Mirrors test_app_db/init/03_readonly_user.sql on the PostgreSQL side, so
-- both arms are queried through an equally-restricted database principal and
-- the security comparison is like-for-like.
--
-- Grants are per-table and SELECT-only. Deliberately NOT granted:
--   * SELECT ANY TABLE  — would expose every schema in the database
--   * EXECUTE on anything — an Oracle definer's-rights PL/SQL function with
--     an autonomous transaction can WRITE from inside a plain SELECT, so
--     withholding EXECUTE is what actually makes "read-only" true here.
--     This is the layer the mcps/oracle guards back up, not replace.
--
-- Runs after 01_schema.sql. Requires privileges to CREATE USER: if the
-- container entrypoint executes these scripts as the application user rather
-- than as SYSDBA, this file will fail and must be run manually as SYSDBA:
--   docker compose exec oracle_db sqlplus -S sys/oracle@FREEPDB1 as sysdba \
--       @/container-entrypoint-initdb.d/03_readonly_user.sql

CREATE USER mcp_readonly IDENTIFIED BY "mcp_readonly_pass";

GRANT CREATE SESSION TO mcp_readonly;

GRANT SELECT ON car_rental.locations           TO mcp_readonly;
GRANT SELECT ON car_rental.employees           TO mcp_readonly;
GRANT SELECT ON car_rental.vehicle_categories  TO mcp_readonly;
GRANT SELECT ON car_rental.vehicles            TO mcp_readonly;
GRANT SELECT ON car_rental.clients             TO mcp_readonly;
GRANT SELECT ON car_rental.reservations        TO mcp_readonly;
GRANT SELECT ON car_rental.payments            TO mcp_readonly;
GRANT SELECT ON car_rental.maintenance_records TO mcp_readonly;
GRANT SELECT ON car_rental.reviews             TO mcp_readonly;
