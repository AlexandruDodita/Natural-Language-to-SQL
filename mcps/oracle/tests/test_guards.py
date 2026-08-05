import inspect
import sys

import pytest

import cases_allowed
import cases_rejected

import config
import guards


@pytest.fixture(autouse=True)
def _denylist():
    original = set(config.TABLE_DENYLIST)
    config.TABLE_DENYLIST.update(cases_rejected.DENYLISTED_TABLES)
    yield
    config.TABLE_DENYLIST.clear()
    config.TABLE_DENYLIST.update(original)


# --------------------------------------------------------------------------
# The catalogs: every rejected input raises, every allowed input passes.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql,expected_reason",
    cases_rejected.REJECTED_CASES,
    ids=[c[0][:60] for c in cases_rejected.REJECTED_CASES],
)
def test_rejected(sql, expected_reason):
    with pytest.raises(guards.QueryRejected) as exc_info:
        guards.validate_query(sql)
    assert expected_reason.lower() in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "sql", cases_allowed.ALLOWED_CASES, ids=[s[:60] for s in cases_allowed.ALLOWED_CASES]
)
def test_allowed(sql):
    result = guards.validate_query(sql)
    assert result == sql.strip()


def test_allowed_query_is_idempotent():
    sql = "SELECT a, COUNT(*) FROM t GROUP BY a"
    once = guards.validate_query(sql)
    assert guards.validate_query(once) == once


# --------------------------------------------------------------------------
# Catalog hygiene.
# --------------------------------------------------------------------------
def test_no_sql_string_is_both_allowed_and_rejected():
    rejected = {sql for sql, _ in cases_rejected.REJECTED_CASES}
    allowed = set(cases_allowed.ALLOWED_CASES)
    assert rejected.isdisjoint(allowed)


def test_allowed_cases_are_unique():
    assert len(cases_allowed.ALLOWED_CASES) == len(set(cases_allowed.ALLOWED_CASES))


# --------------------------------------------------------------------------
# Function allowlist internals.
# --------------------------------------------------------------------------
def test_allowed_functions_are_normalized_uppercase():
    for name in config.ALLOWED_FUNCTIONS:
        assert name == name.upper().strip()
        assert " " not in name
        assert '"' not in name


@pytest.mark.parametrize(
    "sql,name",
    [
        ("SELECT my_udf(1) FROM dual", "my_udf"),
        ("SELECT DoStuff(1) FROM dual", "DoStuff"),
        ('SELECT "quoted_udf"(1) FROM dual', '"quoted_udf"'),
    ],
)
def test_unallowlisted_call_names_the_function(sql, name):
    with pytest.raises(guards.QueryRejected) as exc_info:
        guards.validate_query(sql)
    assert "allowlist" in str(exc_info.value).lower()
    assert name in str(exc_info.value)


def test_qualified_call_rejected_even_if_leaf_is_a_builtin():
    # COUNT is allow-listed, but a package call pkg.count(...) must still fail.
    with pytest.raises(guards.QueryRejected) as exc_info:
        guards.validate_query("SELECT pkg.count(x) FROM t")
    assert "qualified" in str(exc_info.value).lower()


# --------------------------------------------------------------------------
# is_table_allowed / denylist normalization.
# --------------------------------------------------------------------------
def test_is_table_allowed_denylist_normalization():
    assert guards.is_table_allowed("some_table") is True
    assert guards.is_table_allowed("secret_table") is False
    assert guards.is_table_allowed("SECRET_TABLE") is False
    assert guards.is_table_allowed('"SECRET_TABLE"') is False
    assert guards.is_table_allowed("owner.secret_table") is False
    assert guards.is_table_allowed('"OWNER"."SECRET_TABLE"') is False
    assert guards.is_table_allowed("  secret_table  ") is False


# --------------------------------------------------------------------------
# clamp_row_limit (the SQL is never rewritten; the limit is applied at fetch
# time, so only the clamp itself needs testing).
# --------------------------------------------------------------------------
def test_clamp_row_limit_passes_through_in_range_values():
    assert guards.clamp_row_limit(1) == 1
    assert guards.clamp_row_limit(200) == 200
    assert guards.clamp_row_limit(config.MAX_ROWS_HARD_CAP) == config.MAX_ROWS_HARD_CAP


def test_clamp_row_limit_caps_at_hard_limit():
    assert guards.clamp_row_limit(config.MAX_ROWS_HARD_CAP + 1000) == config.MAX_ROWS_HARD_CAP


@pytest.mark.parametrize("bad_rows", [0, -1, -1000])
def test_clamp_row_limit_floors_at_one(bad_rows):
    assert guards.clamp_row_limit(bad_rows) == 1


# --------------------------------------------------------------------------
# guards must be a pure, DB-free module -- the tests never reach an endpoint.
# --------------------------------------------------------------------------
def test_guards_module_never_imports_oracledb():
    source = inspect.getsource(guards)
    assert "import oracledb" not in source
    assert "oracle_conn" not in source


def test_test_process_never_loaded_the_db_layer():
    # Validating queries must not drag in the driver or the connection module.
    assert "oracledb" not in sys.modules
    assert "oracle_conn" not in sys.modules
    assert "mcp_server" not in sys.modules
