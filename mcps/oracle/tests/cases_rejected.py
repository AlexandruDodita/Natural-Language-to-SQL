"""Catalog of malicious/invalid inputs that guards.validate_query() must reject.

Each entry is (sql, expected_reason_substring). The reason substring is
matched case-insensitively against the QueryRejected message.

These exercise guards.py in isolation -- validate_query() never opens a
connection, so nothing here reaches the database.
"""

# More than one statement in the buffer (sqlparse splits on top-level ';').
MULTI_STATEMENT = [
    ("SELECT 1 FROM dual; SELECT 2 FROM dual", "single sql statement"),
    ("SELECT 1 FROM dual; DELETE FROM orders", "single sql statement"),
    ("SELECT 1 FROM dual; COMMIT", "single sql statement"),
    ("SELECT 1 FROM dual; BEGIN NULL; END;", "single sql statement"),
    ("DECLARE x NUMBER; BEGIN NULL; END;", "single sql statement"),
    ("DECLARE v NUMBER; BEGIN v := 1; END;", "single sql statement"),
    ("DECLARE PRAGMA AUTONOMOUS_TRANSACTION; BEGIN NULL; END;", "single sql statement"),
]

# Comments are rejected on raw substrings before parsing (see guards.py:
# malformed comments tokenize inconsistently, so no comment form is allowed,
# benign or not).
COMMENTS = [
    ("SELECT * FROM t -- this table stores COMMIT history\nWHERE 1 = 1", "comments are not allowed"),
    ("SELECT * FROM t /* GRANT and REVOKE are just words here */ WHERE 1 = 1", "comments are not allowed"),
    ("SELECT 1 FROM dual -- x\n; DROP TABLE t", "comments are not allowed"),
    ("SELECT 1 FROM dual /* c */ ; DROP TABLE t", "comments are not allowed"),
    ("SELECT 1 FROM dual /* unterminated", "comments are not allowed"),
    ("SELECT 1 */ FROM dual", "comments are not allowed"),
    ("SELECT * FROM t WHERE c = '--'", "comments are not allowed"),
]

# Database links execute with the link's stored credentials and can reach
# schemas this server's grants never allowed. `@` is rejected at the token
# level, so literals containing '@' remain fine (see cases_allowed).
DB_LINKS = [
    ("SELECT * FROM t@remote_link", "database links"),
    ("SELECT * FROM t@remote.domain.com WHERE x = 1", "database links"),
    ("SELECT * FROM owner.t@prod", "database links"),
    ("SELECT id FROM t1 JOIN t2@link ON t1.id = t2.id", "database links"),
]

# Single buffer, but contains a bare semicolon.
SEMICOLONS = [
    ("SELECT 1 FROM dual;", "semicolon"),
    ("BEGIN NULL; END;", "semicolon"),
    ("BEGIN my_proc(); END;", "semicolon"),
    ("BEGIN EXECUTE IMMEDIATE 'DROP TABLE t'; END;", "semicolon"),
    ("<<lbl>> BEGIN NULL; END;", "semicolon"),
    ("CREATE OR REPLACE FUNCTION f RETURN NUMBER IS BEGIN RETURN 1; END;", "semicolon"),
    ("CREATE PROCEDURE p IS BEGIN NULL; END;", "semicolon"),
    ("CREATE OR REPLACE PACKAGE pkg AS END;", "semicolon"),
    ("CREATE TRIGGER trg BEFORE INSERT ON t BEGIN NULL; END;", "semicolon"),
]

DML_DDL_STATEMENTS = [
    ("INSERT INTO t (x) VALUES (1)", "only select statements"),
    ("UPDATE t SET x = 1", "only select statements"),
    ("DELETE FROM t", "only select statements"),
    ("MERGE INTO t USING s ON (1=1) WHEN MATCHED THEN UPDATE SET x = 1", "only select statements"),
    ("DROP TABLE t", "only select statements"),
    ("ALTER TABLE t ADD (x NUMBER)", "only select statements"),
    ("CREATE TABLE t2 AS SELECT * FROM t", "only select statements"),
    ("CREATE VIEW v AS SELECT * FROM t", "only select statements"),
    ("CREATE OR REPLACE VIEW v AS SELECT * FROM t", "only select statements"),
    ("TRUNCATE TABLE t", "only select statements"),
    ("GRANT SELECT ON t TO u", "only select statements"),
    ("REVOKE SELECT ON t FROM u", "only select statements"),
    ("COMMENT ON TABLE t IS 'x'", "only select statements"),
]

# Non-SELECT statements that carry no bare semicolon of their own.
NON_SELECT_STATEMENTS = [
    ("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY'", "only select statements"),
    ("ALTER SYSTEM FLUSH SHARED_POOL", "only select statements"),
    ("EXPLAIN PLAN FOR SELECT * FROM t", "only select statements"),
    ("ANALYZE TABLE t COMPUTE STATISTICS", "only select statements"),
    ("FLASHBACK TABLE t TO TIMESTAMP SYSTIMESTAMP", "only select statements"),
    ("PURGE TABLE t", "only select statements"),
    ("RENAME t TO t2", "only select statements"),
    ("SET ROLE dba", "only select statements"),
    ("DECLARE v NUMBER", "only select statements"),
]

TRANSACTION_CONTROL = [
    ("COMMIT", "only select statements"),
    ("ROLLBACK", "only select statements"),
    ("SAVEPOINT x", "only select statements"),
    ("SET TRANSACTION READ WRITE", "only select statements"),
    ("SET TRANSACTION READ ONLY", "only select statements"),
    ("LOCK TABLE t IN EXCLUSIVE MODE", "only select statements"),
]

# PL/SQL smuggled through the CTE inline-function feature.
PLSQL_INLINE_FUNCTIONS = [
    (
        "WITH FUNCTION f RETURN NUMBER IS BEGIN RETURN 1; END; SELECT f() FROM dual",
        "single sql statement",
    ),
    (
        "WITH FUNCTION f RETURN NUMBER IS BEGIN RETURN 1 END SELECT f() FROM dual",
        "only select statements",
    ),
]

# Known side-effecting packages caught by the package/schema regex.
SIDE_EFFECTING_PACKAGES = [
    ("SELECT DBMS_LOCK.SLEEP(10) FROM dual", "disallowed package"),
    ("SELECT dbms_lock.sleep(10) FROM dual", "disallowed package"),
    ("SELECT DBMS_RANDOM.VALUE FROM dual", "disallowed package"),
    ("SELECT DBMS_RANDOM.VALUE() FROM dual", "disallowed package"),
    ("SELECT UTL_HTTP.REQUEST('http://x') FROM dual", "disallowed package"),
    ("SELECT UTL_INADDR.GET_HOST_ADDRESS('x') FROM dual", "disallowed package"),
    ("SELECT UTL_FILE.FOPEN('d', 'f', 'r') FROM dual", "disallowed package"),
    ("SELECT DBMS_XMLGEN.GETXML('SELECT 1 FROM dual') FROM dual", "disallowed package"),
    ("SELECT SYS.DBMS_LOB.GETLENGTH(x) FROM t", "disallowed package"),
    ("SELECT * FROM SYS.ALL_USERS", "disallowed package"),
]

# The core defense: a read-only SELECT must not invoke a user/PL/SQL function.
# Every un-allowlisted call in any clause is rejected.
USER_FUNCTION_CALLS = [
    ("SELECT my_udf(1) FROM dual", "allowlist"),
    ("SELECT do_writes(1) FROM dual", "allowlist"),
    ("SELECT app_pkg_localfunc(1) FROM dual", "allowlist"),
    ("SELECT My_Udf(1) FROM dual", "allowlist"),
    ('SELECT "my_udf"(1) FROM dual', "allowlist"),
    ('SELECT "MixedCaseFn"(1) FROM dual', "allowlist"),
    ("SELECT * FROM t WHERE evil(x) = 1", "allowlist"),
    ("SELECT * FROM t ORDER BY evil(x)", "allowlist"),
    ("SELECT * FROM t GROUP BY evil(x)", "allowlist"),
    ("SELECT a FROM t GROUP BY a HAVING evil(COUNT(*)) > 1", "allowlist"),
    ("SELECT (SELECT evil(1) FROM dual) FROM t", "allowlist"),
    ("SELECT CASE WHEN evil(x) = 1 THEN 1 ELSE 0 END FROM t", "allowlist"),
    ("SELECT * FROM t1 JOIN t2 ON evil(t1.id) = t2.id", "allowlist"),
    ("SELECT NVL(evil(a), 0) FROM t", "allowlist"),
    ("SELECT my_object_type(1, 2) FROM dual", "allowlist"),
    ("SELECT * FROM TABLE(my_pipelined(1))", "allowlist"),
    ("SELECT * FROM TABLE(evil_pipe(1))", "allowlist"),
    # A CTE named like a function must not launder a real call to that name.
    ("WITH evil AS (SELECT 1 FROM dual) SELECT evil(1) FROM dual", "allowlist"),
    # MATCH_RECOGNIZE is unsupported by design (config.py): its clause names
    # sit in call position and are not on the allowlist.
    (
        "SELECT * FROM t MATCH_RECOGNIZE (MEASURES 1 AS m PATTERN (a) DEFINE a AS x = 1)",
        "allowlist",
    ),
]

# Schema/package/type-method qualified calls (not covered by the package regex).
QUALIFIED_CALLS = [
    ("SELECT my_pkg.reader(1) FROM dual", "qualified"),
    ("SELECT app.util.f(1) FROM dual", "qualified"),
    ('SELECT "MY_PKG"."F"(1) FROM dual', "qualified"),
    ("SELECT apex_web_service.make_rest_request('x') FROM dual", "qualified"),
    ("SELECT owa_util.get_cgi_env('x') FROM dual", "qualified"),
    ("SELECT x.get_clob_val() FROM t", "qualified"),
]

LOCKING_AND_WRITING_CLAUSES = [
    ("SELECT * FROM t FOR UPDATE", "disallowed keyword"),
    ("SELECT * FROM t FOR UPDATE OF x NOWAIT", "disallowed keyword"),
    ("SELECT * FROM t FOR UPDATE SKIP LOCKED", "disallowed keyword"),
    ("SELECT x INTO y FROM t", "disallowed keyword"),
    ("SELECT x BULK COLLECT INTO y FROM t", "disallowed keyword"),
]

WRAPPER_ESCAPE = [
    ("SELECT * FROM t WHERE x = 'abc", "unterminated"),
    ("SELECT * FROM t WHERE x = 'a''b", "unterminated"),
]

DENYLIST_BYPASS = [
    ("SELECT * FROM secret_table", "not accessible"),
    ("SELECT * FROM SECRET_TABLE", "not accessible"),
    ('SELECT * FROM "SECRET_TABLE"', "not accessible"),
    ("SELECT * FROM owner.secret_table", "not accessible"),
    ('SELECT * FROM "OWNER"."SECRET_TABLE"', "not accessible"),
    ("SELECT * FROM t WHERE id IN (SELECT id FROM secret_table)", "not accessible"),
    ("SELECT * FROM t JOIN secret_table s ON s.id = t.id", "not accessible"),
    ("WITH s AS (SELECT * FROM secret_table) SELECT * FROM s", "not accessible"),
    ("SELECT * FROM t UNION ALL SELECT * FROM secret_table", "not accessible"),
]

GARBAGE_AND_ABUSE = [
    ("", "non-empty"),
    ("   ", "non-empty"),
    ("\x00SELECT 1 FROM dual", "control characters"),
    ("SELECT 1 FROM dual\x07", "control characters"),
    ("SELECT 1\x1bFROM dual", "control characters"),
    ("SELECT 1 FROM dual" + " " * 25_000, "maximum length"),
    ("this is not sql at all", "only select statements"),
]

REJECTED_CASES = (
    MULTI_STATEMENT
    + COMMENTS
    + DB_LINKS
    + SEMICOLONS
    + DML_DDL_STATEMENTS
    + NON_SELECT_STATEMENTS
    + TRANSACTION_CONTROL
    + PLSQL_INLINE_FUNCTIONS
    + SIDE_EFFECTING_PACKAGES
    + USER_FUNCTION_CALLS
    + QUALIFIED_CALLS
    + LOCKING_AND_WRITING_CLAUSES
    + WRAPPER_ESCAPE
    + DENYLIST_BYPASS
    + GARBAGE_AND_ABUSE
)

# Table names guards.is_table_allowed() must reject for the denylist test cases above.
DENYLISTED_TABLES = {"SECRET_TABLE"}
