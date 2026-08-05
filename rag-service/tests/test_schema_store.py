"""Catalog construction, rendering and caching.

``build_catalog`` is pure: it takes the rows the introspection queries return
and produces the schema model, so it is tested without a database. The live
introspection itself is covered by ``test_live_db.py``.
"""

from __future__ import annotations

import pytest

from schema_store import (
    LEGACY_SCHEMA_TEXT,
    SchemaCatalog,
    _shorten_check,
    build_catalog,
)

TABLE_ROWS = [
    ("public", "locations", "r", "Branch offices", 5),
    ("public", "employees", "r", "Staff assigned to a branch", 40),
]

COLUMN_ROWS = [
    ("public", "locations", "id", "integer", True, "nextval('locations_id_seq')", None),
    ("public", "locations", "city", "character varying(100)", True, None, "Branch city"),
    ("public", "employees", "id", "integer", True, None, None),
    ("public", "employees", "location_id", "integer", True, None, None),
    ("public", "employees", "role", "character varying(30)", True, None, None),
    ("public", "employees", "salary", "numeric(10,2)", True, None, None),
    ("public", "employees", "email", "character varying(150)", False, None, None),
]

CONSTRAINT_ROWS = [
    ("public", "locations", "p", "PRIMARY KEY (id)", ["id"], None, None, []),
    ("public", "employees", "p", "PRIMARY KEY (id)", ["id"], None, None, []),
    (
        "public",
        "employees",
        "f",
        "FOREIGN KEY (location_id) REFERENCES locations(id)",
        ["location_id"],
        "public",
        "locations",
        ["id"],
    ),
    (
        "public",
        "employees",
        "c",
        "CHECK (((role)::text = ANY ((ARRAY['manager'::character varying, "
        "'agent'::character varying])::text[])))",
        ["role"],
        None,
        None,
        [],
    ),
    ("public", "employees", "u", "UNIQUE (email)", ["email"], None, None, []),
]


@pytest.fixture()
def built() -> SchemaCatalog:
    return build_catalog("car_rental", TABLE_ROWS, COLUMN_ROWS, CONSTRAINT_ROWS)


def test_tables_and_columns_are_wired(built):
    assert [t.name for t in built.tables] == ["employees", "locations"]
    employees = built.table("employees")
    assert [c.name for c in employees.columns] == [
        "id",
        "location_id",
        "role",
        "salary",
        "email",
    ]


def test_primary_keys_are_marked(built):
    assert built.table("employees").column("id").is_primary_key


def test_foreign_keys_are_captured_on_both_levels(built):
    employees = built.table("employees")
    assert employees.foreign_keys[0].ref_table == "locations"
    assert employees.column("location_id").references == "locations.id"


def test_unique_and_nullability(built):
    employees = built.table("employees")
    assert employees.column("email").is_unique
    assert employees.column("email").nullable is True
    assert employees.column("salary").nullable is False


def test_check_constraints_are_simplified(built):
    check = built.table("employees").column("role").check
    assert check == "CHECK(role IN ('manager', 'agent'))"


def test_comments_are_kept(built):
    assert built.table("locations").comment == "Branch offices"
    assert built.table("locations").column("city").comment == "Branch city"


def test_render_produces_prompt_text(built):
    text = built.render(["employees"])
    assert "employees(" in text
    assert "salary numeric(10,2)" in text
    assert "FK->locations.id" in text
    assert "locations(" not in text.split("employees(")[1]


def test_render_all_tables_by_default(built):
    text = built.render()
    assert "employees(" in text and "locations(" in text


def test_description_feeds_retrieval(built):
    description = built.table("employees").description()
    assert "employees" in description
    assert "salary" in description
    assert "joins locations" in description


def test_neighbours_are_bidirectional(built):
    assert built.neighbours("employees") == ["locations"]
    assert built.neighbours("locations") == ["employees"]


def test_fingerprint_changes_with_the_schema(built):
    other = build_catalog("car_rental", TABLE_ROWS, COLUMN_ROWS[:-1], CONSTRAINT_ROWS)
    assert built.fingerprint
    assert built.fingerprint != other.fingerprint


def test_fingerprint_is_stable(built):
    again = build_catalog("car_rental", TABLE_ROWS, COLUMN_ROWS, CONSTRAINT_ROWS)
    assert built.fingerprint == again.fingerprint


def test_catalog_roundtrips_through_disk(tmp_path, built):
    path = tmp_path / "catalog.json"
    built.save(str(path))
    loaded = SchemaCatalog.load(str(path))
    assert loaded is not None
    assert loaded.fingerprint == built.fingerprint
    assert loaded.render() == built.render()


def test_load_missing_catalog_returns_none(tmp_path):
    assert SchemaCatalog.load(str(tmp_path / "nope.json")) is None


def test_unknown_table_lookup_returns_none(built):
    assert built.table("does_not_exist") is None


@pytest.mark.parametrize(
    "definition,expected",
    [
        ("CHECK ((rating >= 1) AND (rating <= 5))", "CHECK((rating >= 1) AND (rating <= 5))"),
        (
            "CHECK (((status)::text = ANY ((ARRAY['a'::character varying])::text[])))",
            "CHECK(status IN ('a'))",
        ),
        ("CHECK ((return_date >= pickup_date))", "CHECK(return_date >= pickup_date)"),
    ],
)
def test_check_simplification(definition, expected):
    assert _shorten_check(definition) == expected


def test_legacy_fallback_is_available():
    assert "car_rental" in LEGACY_SCHEMA_TEXT
    assert "reservations" in LEGACY_SCHEMA_TEXT


def test_fixture_matches_the_real_database(catalog):
    """The committed fixture came from a live introspection; keep it honest."""
    assert catalog.database == "car_rental"
    assert len(catalog.tables) == 9
    vehicles = catalog.table("vehicles")
    assert vehicles.column("make").data_type.startswith("character varying")
    assert vehicles.column("status").check.startswith("CHECK(status IN (")
    assert {fk.ref_table for fk in vehicles.foreign_keys} == {
        "vehicle_categories",
        "locations",
    }
