"""Shared fixtures.

Everything except the ``live_*`` fixtures runs without a database: the schema
catalog is a committed JSON fixture produced by the real introspection code, so
the retrieval and policy tests are reproducible on any machine.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))

from policy import PolicyEngine  # noqa: E402
from retrieval import HashingEmbedder, SchemaIndex, ValueIndex  # noqa: E402
from schema_store import SchemaCatalog  # noqa: E402


@pytest.fixture(scope="session")
def catalog() -> SchemaCatalog:
    data = json.loads((FIXTURES / "car_rental_catalog.json").read_text())
    return SchemaCatalog.from_dict(data)


@pytest.fixture(scope="session")
def value_index() -> ValueIndex:
    data = json.loads((FIXTURES / "car_rental_value_index.json").read_text())
    return ValueIndex.from_dict(data)


@pytest.fixture(scope="session")
def index(catalog, value_index) -> SchemaIndex:
    idx = SchemaIndex(catalog, HashingEmbedder(), value_index=value_index)
    idx.build_embeddings()
    return idx


@pytest.fixture(scope="session")
def policy_engine(catalog) -> PolicyEngine:
    return PolicyEngine.from_file(str(ROOT / "policy.yaml"), catalog=catalog)


@pytest.fixture(scope="session")
def gold_questions() -> list[dict]:
    return json.loads((FIXTURES / "schema_linking_gold.json").read_text())["questions"]


@pytest.fixture(scope="session")
def live_dsn() -> str:
    """DSN of a live car_rental database, or skip.

    Set TEST_DATABASE_URL, e.g. with docker compose up:
        TEST_DATABASE_URL=postgresql://readonly_user:readonly_pass@localhost:5434/car_rental
    """
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set (no live database available)")
    return dsn
