import os
import re

from dotenv import load_dotenv

# Anchored to this file's directory rather than the process cwd, since MCP
# clients (e.g. Claude Desktop spawning this over stdio) control the cwd.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_list(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip().upper() for item in value.split(",") if item.strip()]


# Oracle connection.
# ORACLE_LIB_DIR is optional: when set, python-oracledb runs in thick mode via
# Instant Client at that path; when unset it runs in thin mode, which needs no
# Instant Client at all and speaks to Oracle Database 12.1+ directly. Thin mode
# is what makes this server deployable in a slim container.
ORACLE_LIB_DIR = os.getenv("ORACLE_LIB_DIR") or None
ORACLE_USER = _get_required("ORACLE_USER")
ORACLE_PASSWORD = _get_required("ORACLE_PASSWORD")
ORACLE_HOST = _get_required("ORACLE_HOST")
ORACLE_PORT = _get_required("ORACLE_PORT")
ORACLE_SERVICE_NAME = _get_required("ORACLE_SERVICE_NAME")

# Schema whose tables the server exposes. When connecting as a dedicated
# read-only user (scripts/create_readonly_user.sql) this is the schema OWNER,
# not the connect user: metadata queries filter ALL_* views on it and every
# pooled session runs ALTER SESSION SET CURRENT_SCHEMA to it. Defaults to
# ORACLE_USER, which preserves the connect-as-owner behavior.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")
ORACLE_TARGET_SCHEMA = os.getenv("ORACLE_TARGET_SCHEMA", ORACLE_USER).strip().upper()
if not _IDENTIFIER_RE.match(ORACLE_TARGET_SCHEMA):
    # Spliced into ALTER SESSION SET CURRENT_SCHEMA (identifiers cannot be
    # bound), so it must be a plain Oracle identifier.
    raise RuntimeError(f"ORACLE_TARGET_SCHEMA is not a valid Oracle identifier: {ORACLE_TARGET_SCHEMA}")

# MCP server. The bearer token travels in cleartext over HTTP, so the default
# binding is loopback-only; bind a non-local address only behind TLS (e.g. a
# reverse proxy terminating HTTPS).
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "oracle")
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = _get_int("MCP_PORT", 8000)
MCP_AUTH_TOKEN = _get_required("MCP_AUTH_TOKEN")

# Query guards
TABLE_DENYLIST = set(_get_list("TABLE_DENYLIST"))
MAX_ROWS_HARD_CAP = _get_int("MAX_ROWS_HARD_CAP", 1000)
QUERY_TIMEOUT_SECONDS = _get_int("QUERY_TIMEOUT_SECONDS", 30)

# Response shaping: individual string cells longer than MAX_CELL_CHARS are
# truncated with a marker, and a tool response whose JSON payload would exceed
# MAX_RESPONSE_CHARS drops trailing rows (reported via `truncated`). Both
# protect the MCP client's context window, not the database.
MAX_CELL_CHARS = _get_int("MAX_CELL_CHARS", 2000)
MAX_RESPONSE_CHARS = _get_int("MAX_RESPONSE_CHARS", 200_000)

# SQL-native, read-only built-in functions permitted inside run_query().
# A call to any name not in this set is rejected, and every schema/package-
# qualified call (pkg.func(...)) is rejected outright. This is the app-level
# barrier against a SELECT invoking PL/SQL -- e.g. a definer's-rights or
# autonomous-transaction function that performs writes. It is defense in depth
# on top of a DB user with no EXECUTE grants (scripts/create_readonly_user.sql),
# NOT a substitute for it.
#
# Every entry is a function/operator evaluated by the SQL engine itself, with no
# ability to modify data. PL/SQL packages (DBMS_*, UTL_*, ...) are deliberately
# absent and are additionally blocked as qualified calls. To widen this list,
# add only documented SQL built-ins -- never a user or package function.
ALLOWED_FUNCTIONS = frozenset(
    {
        # Aggregate / statistical
        "AVG", "COUNT", "MAX", "MIN", "SUM", "MEDIAN", "STDDEV", "STDDEV_POP",
        "STDDEV_SAMP", "VARIANCE", "VAR_POP", "VAR_SAMP", "CORR", "COVAR_POP",
        "COVAR_SAMP", "APPROX_COUNT_DISTINCT", "STATS_MODE", "GROUPING",
        "GROUPING_ID", "GROUP_ID", "LISTAGG", "PERCENTILE_CONT", "PERCENTILE_DISC",
        # Analytic / ranking (used with OVER)
        "RANK", "DENSE_RANK", "PERCENT_RANK", "CUME_DIST", "ROW_NUMBER", "NTILE",
        "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE", "RATIO_TO_REPORT",
        # GROUP BY extensions (tokenized as bare names)
        "ROLLUP", "CUBE",
        # Numeric
        "ABS", "ACOS", "ASIN", "ATAN", "ATAN2", "BITAND", "CEIL", "CEILING", "COS",
        "COSH", "EXP", "FLOOR", "LN", "LOG", "MOD", "NANVL", "POWER", "REMAINDER",
        "ROUND", "SIGN", "SIN", "SINH", "SQRT", "TAN", "TANH", "TRUNC", "WIDTH_BUCKET",
        # Character
        "CHR", "NCHR", "CONCAT", "INITCAP", "LOWER", "UPPER", "LPAD", "RPAD", "LTRIM",
        "RTRIM", "TRIM", "NLS_INITCAP", "NLS_LOWER", "NLS_UPPER", "NLSSORT", "REPLACE",
        "TRANSLATE", "SOUNDEX", "SUBSTR", "SUBSTRB", "REGEXP_REPLACE", "REGEXP_SUBSTR",
        "ASCII", "INSTR", "INSTRB", "LENGTH", "LENGTHB", "REGEXP_INSTR", "REGEXP_COUNT",
        "REGEXP_LIKE",
        # Datetime / interval
        "ADD_MONTHS", "CURRENT_DATE", "CURRENT_TIMESTAMP", "DBTIMEZONE", "EXTRACT",
        "FROM_TZ", "LAST_DAY", "LOCALTIMESTAMP", "MONTHS_BETWEEN", "NEXT_DAY",
        "NUMTODSINTERVAL", "NUMTOYMINTERVAL", "SESSIONTIMEZONE", "SYS_EXTRACT_UTC",
        "SYSDATE", "SYSTIMESTAMP", "TZ_OFFSET", "TO_DSINTERVAL", "TO_YMINTERVAL",
        # Conversion
        "ASCIISTR", "BIN_TO_NUM", "CAST", "CHARTOROWID", "COMPOSE", "CONVERT",
        "DECOMPOSE", "HEXTORAW", "RAWTOHEX", "RAWTONHEX", "ROWIDTOCHAR", "UNISTR",
        "VALIDATE_CONVERSION", "TO_CHAR", "TO_NCHAR", "TO_CLOB", "TO_DATE", "TO_NUMBER",
        "TO_TIMESTAMP", "TO_TIMESTAMP_TZ", "TO_BINARY_DOUBLE", "TO_BINARY_FLOAT",
        # Null handling / comparison / selection
        "COALESCE", "DECODE", "GREATEST", "LEAST", "LNNVL", "NULLIF", "NVL", "NVL2",
        # Hash / hierarchy / misc read-only
        "ORA_HASH", "STANDARD_HASH", "DUMP", "VSIZE", "SYS_GUID", "SYS_CONTEXT",
        "USERENV", "SYS_CONNECT_BY_PATH",
        # Collection / XML / JSON (SQL-native, read-only)
        "TABLE", "XMLELEMENT", "XMLFOREST", "XMLAGG", "XMLCONCAT", "XMLPARSE",
        "XMLQUERY", "XMLTABLE", "XMLCAST", "XMLEXISTS", "XMLSERIALIZE", "XMLATTRIBUTES",
        "XMLNAMESPACES", "JSON_VALUE", "JSON_QUERY", "JSON_OBJECT", "JSON_ARRAY",
        "JSON_ARRAYAGG", "JSON_OBJECTAGG", "JSON_TABLE", "JSON_EXISTS", "JSON_SERIALIZE",
        # Data-type names permitted as CAST / constructor targets
        "VARCHAR2", "NVARCHAR2", "VARCHAR", "CHAR", "NCHAR", "NUMBER", "NUMERIC",
        "DECIMAL", "DEC", "INTEGER", "INT", "SMALLINT", "FLOAT", "REAL", "BINARY_FLOAT",
        "BINARY_DOUBLE", "DATE", "TIMESTAMP", "INTERVAL", "RAW", "CLOB", "NCLOB", "BLOB",
        "ROWID",
        # SQL clause keywords that appear in call-like position (name followed by
        # `(`): interval-field precisions (INTERVAL DAY(2) TO SECOND(6)), the
        # row-sampling clause (t SAMPLE(10)), JSON_TABLE/XMLTABLE COLUMNS(...), and
        # the FIRST/LAST aggregate KEEP (...) clause. (MATCH_RECOGNIZE is not
        # supported -- its PATTERN(...) sub-clause makes it reject; add the
        # sub-keywords here if that feature is ever needed.)
        "YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND", "SAMPLE", "COLUMNS", "KEEP",
    }
)

# Audit log
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")
