import re

import sqlparse
from sqlparse.tokens import Comment, Error, Keyword, Literal, Name, Punctuation

import config

MAX_QUERY_LENGTH = 20_000

# ttype for any of these is "in" sqlparse.tokens.Keyword (DML/DDL/DCL/CTE all
# nest under Keyword), so a single membership check covers every subtype.
BANNED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "LOCK",
    "CALL",
    "EXECUTE",
    "AUDIT",
    "COMMENT",
    "INTO",
    "FUNCTION",
    "PROCEDURE",
}

# Identifier-level (Name token) prefixes for packages that can perform
# writes or side effects even from inside a read-only SELECT. Matched against
# the query text with string-literal contents blanked out (see
# _text_without_string_literals), so 'DBMS_STATS' as a *value* is fine while
# DBMS_STATS as an *identifier* is rejected.
_DANGEROUS_PACKAGE_RE = re.compile(
    r"\b(DBMS_\w*|UTL_\w*|CTXSYS\.\w*|ORDSYS\.\w*|XDB\.\w*|SYS\.\w*)",
    re.IGNORECASE,
)

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# SQL comments have no legitimate purpose in a query submitted programmatically
# by an LLM, and malformed/unterminated comments (e.g. a trailing `/*` with no
# closing `*/`) tokenize inconsistently -- sometimes as a real Comment token,
# sometimes falling through to plain keywords/operators depending on content.
# Rejecting on raw substrings, before any parsing happens, sidesteps that
# tokenizer ambiguity entirely rather than trying to special-case it.
_COMMENT_MARKERS = ("--", "/*", "*/")

# Double-quoted identifiers tokenize as this, not as Name; a function call can be
# written "my_func"(...), so call detection must cover both.
_QUOTED_NAME = sqlparse.tokens.Literal.String.Symbol

# Keywords that mark the end of a leading WITH clause (start of the main query).
_CTE_TERMINATORS = {"SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"}


class QueryRejected(Exception):
    pass


def _normalize_identifier(name: str) -> str:
    name = name.strip()
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    if name.startswith('"') and name.endswith('"') and len(name) >= 2:
        name = name[1:-1]
    return name.upper()


def is_table_allowed(table_name: str) -> bool:
    return _normalize_identifier(table_name) not in config.TABLE_DENYLIST


def _iter_identifier_tokens(statement):
    for tok in statement.flatten():
        if tok.ttype in sqlparse.tokens.Name or tok.ttype is sqlparse.tokens.Literal.String.Symbol:
            yield tok


def _is_name_like(tok) -> bool:
    return tok.ttype in Name or tok.ttype is _QUOTED_NAME


def _significant_tokens(tokens):
    return [tok for tok in tokens if not tok.is_whitespace and tok.ttype not in Comment]


def _is_string_literal(tok) -> bool:
    # Single-quoted (and q-quoted / N-prefixed) literals only. Double-quoted
    # identifiers (Literal.String.Symbol) are names, not values, and stay
    # subject to every identifier-level check.
    return tok.ttype in Literal.String and tok.ttype is not _QUOTED_NAME


def _text_without_string_literals(tokens) -> str:
    """The query text with each string literal replaced by a single space.

    Whitespace and punctuation are preserved verbatim, so multi-token
    references such as SYS.DBMS_LOB remain adjacent for the package regex,
    while values like 'DBMS_STATS' can no longer false-positive it.
    """
    return "".join(" " if _is_string_literal(tok) else tok.value for tok in tokens)


def _cte_name_positions(sig) -> set:
    """Indices in `sig` of identifiers that are CTE names in a leading WITH clause.

    `WITH x (a, b) AS (...)` makes `x (` look exactly like a function call in a
    flat token scan, but it is a query-name definition, not an invocation. We
    skip these exact positions only -- never by name -- so a real call such as
    `x(1)` elsewhere in the query body is still validated.
    """
    if not sig or sig[0].ttype not in Keyword or sig[0].value.upper() != "WITH":
        return set()

    positions = set()
    depth = 0
    expect_name = True  # the next depth-0 identifier is a CTE definition name
    for i in range(1, len(sig)):
        tok = sig[i]
        if tok.ttype is Punctuation and tok.value == "(":
            depth += 1
        elif tok.ttype is Punctuation and tok.value == ")":
            depth -= 1
        elif depth == 0:
            if tok.ttype is Punctuation and tok.value == ",":
                expect_name = True
            elif tok.ttype in Keyword and tok.value.upper() in _CTE_TERMINATORS:
                break  # main query has begun; WITH clause is finished
            elif expect_name and _is_name_like(tok):
                positions.add(i)
                expect_name = False
    return positions


def _check_function_calls(tokens) -> None:
    """Reject any call that is not to a SQL-native, read-only built-in.

    An identifier in call position (immediately followed by `(`) must be an
    unqualified name in config.ALLOWED_FUNCTIONS. Schema/package-qualified calls
    (pkg.func(...)) are rejected outright. This is the app-level block against a
    SELECT invoking PL/SQL -- e.g. a definer's-rights or autonomous-transaction
    function that performs writes from inside a read-only SELECT.
    """
    sig = _significant_tokens(tokens)
    cte_positions = _cte_name_positions(sig)
    for i, tok in enumerate(sig):
        nxt = sig[i + 1] if i + 1 < len(sig) else None
        if nxt is None or nxt.ttype is not Punctuation or nxt.value != "(":
            continue
        if not _is_name_like(tok) or i in cte_positions:
            continue
        prev = sig[i - 1] if i > 0 else None
        if prev is not None and prev.ttype is Punctuation and prev.value == ".":
            raise QueryRejected(f"Qualified package or type-method calls are not allowed: {tok.value}.")
        if _normalize_identifier(tok.value) not in config.ALLOWED_FUNCTIONS:
            raise QueryRejected(f"Function is not on the read-only allowlist: {tok.value}.")


def validate_query(sql: str) -> str:
    """Validate that sql is a single, safe, read-only SELECT statement.

    Returns the (stripped) validated SQL on success, or raises
    QueryRejected with a human-readable reason.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise QueryRejected("Query must be a non-empty string.")

    if len(sql) > MAX_QUERY_LENGTH:
        raise QueryRejected(f"Query exceeds the maximum length of {MAX_QUERY_LENGTH} characters.")

    if _CONTROL_CHAR_RE.search(sql):
        raise QueryRejected("Query contains disallowed control characters.")

    for marker in _COMMENT_MARKERS:
        if marker in sql:
            raise QueryRejected("Comments are not allowed in the query.")

    statements = sqlparse.parse(sql)
    if len(statements) == 0:
        raise QueryRejected("Query must be a non-empty string.")
    if len(statements) > 1:
        raise QueryRejected("Only a single SQL statement is allowed.")

    statement = statements[0]
    tokens = list(statement.flatten())

    if any(tok.ttype is Error for tok in tokens):
        raise QueryRejected("Query contains an unterminated string literal or invalid token.")

    if any(tok.ttype is Punctuation and tok.value == ";" for tok in tokens):
        raise QueryRejected("Semicolons are not allowed in the query.")

    # A database link (table@link) executes with the link's stored credentials
    # and can reach schemas this server's grants never allowed. `@` has no
    # legitimate use in a SELECT outside string literals (XQuery/JSON `@attr`
    # paths live inside literals), so reject it at the token level.
    if any("@" in tok.value for tok in tokens if not _is_string_literal(tok)):
        raise QueryRejected("Database links (@) are not allowed in the query.")

    statement_type = statement.get_type()
    if statement_type != "SELECT":
        raise QueryRejected(f"Only SELECT statements are allowed (got statement type: {statement_type}).")

    for tok in tokens:
        if tok.ttype in Keyword and tok.value.upper() in BANNED_KEYWORDS:
            raise QueryRejected(f"Query contains a disallowed keyword: {tok.value.upper()}.")

    match = _DANGEROUS_PACKAGE_RE.search(_text_without_string_literals(tokens))
    if match:
        raise QueryRejected(f"Query references a disallowed package or schema: {match.group(0)}.")

    _check_function_calls(tokens)

    for tok in _iter_identifier_tokens(statement):
        identifier = _normalize_identifier(tok.value)
        if identifier in config.TABLE_DENYLIST:
            raise QueryRejected(f"Query references a table that is not accessible: {identifier}.")

    return sql.strip()


def clamp_row_limit(max_rows: int) -> int:
    """Clamp a caller-requested row limit to [1, MAX_ROWS_HARD_CAP].

    The limit is enforced at fetch time (cursor.fetchmany), never by rewriting
    the SQL: a ROWNUM/FETCH FIRST wrapper breaks valid queries whose SELECT
    list has duplicate column names (ORA-00918), which LLM-written joins hit
    constantly.
    """
    return max(1, min(max_rows, config.MAX_ROWS_HARD_CAP))
