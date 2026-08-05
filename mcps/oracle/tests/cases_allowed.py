"""Catalog of legitimate queries that guards.validate_query() must NOT reject.

False-positive protection: these exercise trap words in safe positions, the
full range of SQL-native built-in functions, and Oracle SQL features that a
naive keyword/function filter would misflag. Nothing here reaches the database;
validate_query() only parses and inspects the SQL.
"""

BASIC = [
    "SELECT * FROM t",
    "SELECT a, b FROM t WHERE a = 1",
    "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id",
    "SELECT a, COUNT(*) FROM t GROUP BY a HAVING COUNT(*) > 1 ORDER BY a",
    "SELECT * FROM t1 UNION ALL SELECT * FROM t2",
    "SELECT * FROM t1 INTERSECT SELECT * FROM t2",
    "SELECT * FROM t1 MINUS SELECT * FROM t2",
    "SELECT * FROM (SELECT a FROM t) v WHERE v.a > 0",
    "SELECT * FROM t WHERE a IN (SELECT id FROM u)",
    "SELECT * FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.id = t.id)",
    "SELECT * FROM t FETCH FIRST 10 ROWS ONLY",
]

CTE_AND_ANALYTIC = [
    "WITH x AS (SELECT 1 FROM dual) SELECT * FROM x",
    "SELECT emp, ROW_NUMBER() OVER (ORDER BY sal) rn FROM emp",
    "SELECT * FROM t START WITH id = 1 CONNECT BY PRIOR id = parent_id",
    "SELECT SUM(x) OVER (PARTITION BY g ORDER BY y ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM t",
    "SELECT RANK() OVER (ORDER BY sal DESC), DENSE_RANK() OVER (ORDER BY sal) FROM emp",
    "SELECT LAG(x, 1) OVER (ORDER BY y), LEAD(x) OVER (ORDER BY y) FROM t",
    # recursive CTE with explicit column list -- `r (n)` is a query name, not a call
    "WITH r (n) AS (SELECT 1 FROM dual UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT n FROM r",
    "WITH a AS (SELECT 1 c FROM dual), b (c) AS (SELECT 2 FROM dual) SELECT * FROM a JOIN b ON 1 = 1",
]

TRAP_WORDS_IN_SAFE_POSITIONS = [
    "SELECT update_date, created_by FROM t",
    "SELECT merge_count, delete_flag, insert_ts FROM t",
    "SELECT * FROM t WHERE status = 'DELETE'",
    "SELECT * FROM t WHERE note = 'won''t DROP this'",
    "SELECT * FROM calls c WHERE c.duration > 60",
    # bare aggregate/function names used as column identifiers (no parens)
    "SELECT count, sum, avg FROM t",
    # dangerous-package names as string VALUES: only identifiers are scanned
    "SELECT * FROM t WHERE source_job = 'DBMS_SCHEDULER'",
    "SELECT * FROM t WHERE api = 'UTL_HTTP.REQUEST'",
    "SELECT * FROM t WHERE owner_col = 'SYS.ALL_USERS'",
    # '@' inside a string literal is data, not a database link
    "SELECT * FROM t WHERE email = 'user@example.com'",
    # a q-quoted literal keeps its contents (incl. ';' and keywords) in one token
    "SELECT q'[; DROP TABLE t]' FROM dual",
]

CONVERSION_AND_NULL_BUILTINS = [
    "SELECT TO_CHAR(SYSDATE, 'YYYY-MM-DD') FROM dual",
    "SELECT TO_NUMBER('42'), TO_DATE('2020-01-01', 'YYYY-MM-DD') FROM dual",
    "SELECT TO_TIMESTAMP('2020-01-01 00:00:00', 'YYYY-MM-DD HH24:MI:SS') FROM dual",
    "SELECT NVL(a, 0), NVL2(a, 1, 2), COALESCE(a, b, c), NULLIF(a, b) FROM t",
    "SELECT DECODE(a, 1, 'one', 2, 'two', 'other') FROM t",
    "SELECT GREATEST(a, b, c), LEAST(a, b, c) FROM t",
    "SELECT CAST(x AS VARCHAR2(10)), CAST(y AS NUMBER(10, 2)) FROM t",
    "SELECT CAST(x AS TIMESTAMP(6)) FROM t",
    "SELECT CAST(x AS INTERVAL DAY(2) TO SECOND(6)) FROM t",
    "SELECT CAST(x AS NUMBER(*, 0)) FROM t",
]

STRING_NUMERIC_DATE_BUILTINS = [
    "SELECT UPPER(a), LOWER(b), INITCAP(c) FROM t",
    "SELECT SUBSTR(a, 1, 3), INSTR(a, 'x'), LENGTH(a) FROM t",
    "SELECT LTRIM(RTRIM(a)), TRIM(BOTH ' ' FROM a), LPAD(a, 5, '0') FROM t",
    "SELECT REPLACE(a, 'x', 'y'), TRANSLATE(a, 'ab', 'cd') FROM t",
    "SELECT REGEXP_REPLACE(a, '^x', 'y'), REGEXP_SUBSTR(a, '\\d+') FROM t",
    "SELECT a FROM t WHERE REGEXP_LIKE(a, '^x')",
    "SELECT ABS(a), CEIL(b), FLOOR(c), ROUND(d, 2), TRUNC(e) FROM t",
    "SELECT MOD(a, 3), POWER(2, n), SQRT(a), SIGN(b) FROM t",
    "SELECT ADD_MONTHS(SYSDATE, 1), MONTHS_BETWEEN(a, b), LAST_DAY(c) FROM t",
    "SELECT EXTRACT(YEAR FROM d), EXTRACT(DAY FROM d) FROM t",
    "SELECT NUMTODSINTERVAL(5, 'DAY'), NUMTOYMINTERVAL(2, 'MONTH') FROM dual",
]

AGGREGATE_AND_WINDOW = [
    "SELECT AVG(x), SUM(x), MIN(x), MAX(x), MEDIAN(x), STDDEV(x), VARIANCE(x) FROM t",
    "SELECT COUNT(DISTINCT a) FROM t",
    "SELECT a, SUM(b) FROM t GROUP BY ROLLUP(a)",
    "SELECT a, b, SUM(c) FROM t GROUP BY CUBE(a, b)",
    "SELECT a, b, SUM(c) FROM t GROUP BY GROUPING SETS ((a), (b), ())",
    "SELECT LISTAGG(x, ',') WITHIN GROUP (ORDER BY x) FROM t",
    "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) FROM t",
    "SELECT MAX(sal) KEEP (DENSE_RANK FIRST ORDER BY hiredate) FROM emp",
    "SELECT NTILE(4) OVER (ORDER BY x), CUME_DIST() OVER (ORDER BY x) FROM t",
]

XML_JSON_BUILTINS = [
    "SELECT XMLELEMENT(\"e\", a) FROM t",
    "SELECT XMLAGG(XMLELEMENT(\"e\", a) ORDER BY a) FROM t",
    "SELECT XMLTABLE('/r' PASSING x COLUMNS a NUMBER PATH 'a') FROM t",
    "SELECT JSON_VALUE(doc, '$.a') FROM t",
    "SELECT JSON_QUERY(doc, '$.items') FROM t",
    "SELECT JSON_TABLE(doc, '$' COLUMNS (a NUMBER PATH '$.a')) FROM t",
]

QUERY_SHAPES_AND_LITERALS = [
    "SELECT * FROM t PIVOT (SUM(v) FOR k IN ('a', 'b'))",
    "SELECT * FROM t UNPIVOT (v FOR k IN (a, b))",
    "SELECT * FROM t SAMPLE(10)",
    "SELECT * FROM t, TABLE(t.items)",
    "SELECT N'unicode', q'[plain q-quote]' FROM dual",
    "SELECT * FROM t WHERE d > SYSDATE - INTERVAL '1' DAY",
    "SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END FROM t",
    "SELECT SYS_CONTEXT('USERENV', 'SESSION_USER') FROM dual",
    "SELECT t.\"Col\" FROM \"Tbl\" t",
]

ALLOWED_CASES = (
    BASIC
    + CTE_AND_ANALYTIC
    + TRAP_WORDS_IN_SAFE_POSITIONS
    + CONVERSION_AND_NULL_BUILTINS
    + STRING_NUMERIC_DATE_BUILTINS
    + AGGREGATE_AND_WINDOW
    + XML_JSON_BUILTINS
    + QUERY_SHAPES_AND_LITERALS
)
