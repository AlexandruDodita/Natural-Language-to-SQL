-- Provisioning script for a dedicated read-only MCP user.
-- Run by a DBA against the target database. Replace <SCHEMA_OWNER> and
-- <PASSWORD>, and list the actual tables the MCP server should expose.
--
-- This is the real security boundary: the app-level guards in guards.py are
-- defense in depth, not a substitute for this. In particular, this user must
-- receive ZERO EXECUTE grants on any procedure, function, or package -- that
-- closes the Oracle-specific hole where a SELECT calls a definer's-rights
-- function that performs writes via an autonomous transaction.
--
-- When deploying with this user, set in .env:
--   ORACLE_USER=mcp_readonly
--   ORACLE_TARGET_SCHEMA=<SCHEMA_OWNER>
-- The server filters ALL_* dictionary views on ORACLE_TARGET_SCHEMA and sets
-- CURRENT_SCHEMA per session, so granted tables resolve without a prefix.

CREATE USER mcp_readonly IDENTIFIED BY "<PASSWORD>";

GRANT CREATE SESSION TO mcp_readonly;

-- Per-table SELECT grants (repeat for every table the MCP server should see).
-- Do NOT grant SELECT ANY TABLE -- keep this list explicit and reviewed.
GRANT SELECT ON <SCHEMA_OWNER>.<TABLE_NAME> TO mcp_readonly;
-- GRANT SELECT ON <SCHEMA_OWNER>.<OTHER_TABLE> TO mcp_readonly;

-- Explicitly NOT granted, and must stay that way:
--   EXECUTE on any PROCEDURE / FUNCTION / PACKAGE
--   INSERT / UPDATE / DELETE / MERGE on any object
--   CREATE ANY / ALTER ANY / DROP ANY
--   SELECT ANY TABLE, SELECT ANY DICTIONARY

-- Optional hardening: cap resource usage for this user via a profile.
-- CREATE PROFILE mcp_readonly_profile LIMIT
--   SESSIONS_PER_USER 5
--   CPU_PER_CALL 30000
--   CONNECT_TIME 480;
-- ALTER USER mcp_readonly PROFILE mcp_readonly_profile;
