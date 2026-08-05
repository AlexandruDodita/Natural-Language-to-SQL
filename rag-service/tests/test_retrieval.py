"""Retrieval ranking tests.

Runs against the committed catalog fixture with the deterministic hashing
embedder, so the numbers are reproducible on any machine (no model download, no
database). The sentence-transformer path is exercised only when the package and
the model are actually available.
"""

from __future__ import annotations

import json

import pytest

from retrieval import (
    HashingEmbedder,
    SchemaIndex,
    ValueIndex,
    build_embedder,
    cosine,
    tokenize,
)


def recall(index: SchemaIndex, gold: list[dict], top_k: int, expand_fk: bool) -> tuple[float, int]:
    """(micro recall over gold tables, number of fully covered questions)"""
    total = hits = covered = 0
    for item in gold:
        result = index.retrieve(
            item["question"], top_k=top_k, fallback_max_tables=0, expand_fk=expand_fk
        )
        wanted, got = set(item["tables"]), set(result.tables)
        total += len(wanted)
        hits += len(wanted & got)
        covered += int(wanted <= got)
    return hits / total, covered


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the average salary of employees?", "employees"),
        ("How many vehicles are available?", "vehicles"),
        ("Which payment method is used most often?", "payments"),
        ("Show the ratings customers left", "reviews"),
        ("Total maintenance cost per car", "maintenance_records"),
        ("List the branch offices", "locations"),
    ],
)
def test_expected_table_ranks_first(index, question, expected):
    ranking, _ = index.rank(question)
    assert ranking[0].table == expected, [r.to_dict() for r in ranking[:3]]


def test_value_index_links_a_literal_to_its_column(index):
    result = index.retrieve("How many Toyota cars do we have?", top_k=2, fallback_max_tables=0)
    assert "vehicles" in result.tables
    matches = {(m["table"], m["column"]) for m in result.value_matches}
    assert ("vehicles", "make") in matches


def test_value_index_links_a_city_to_locations(index):
    result = index.retrieve("Which cars are in Miami?", top_k=2, fallback_max_tables=0)
    matches = {(m["table"], m["column"]) for m in result.value_matches}
    assert ("locations", "city") in matches
    assert "locations" in result.tables


def test_value_matches_are_reported_in_the_prompt(index):
    result = index.retrieve("How many Toyota cars do we have?", top_k=2, fallback_max_tables=0)
    assert "toyota" in result.prompt_text.lower()


def test_value_index_improves_recall(catalog, value_index, gold_questions):
    with_values = SchemaIndex(catalog, HashingEmbedder(), value_index=value_index)
    with_values.build_embeddings()
    without = SchemaIndex(catalog, HashingEmbedder(), value_index=ValueIndex())
    without.build_embeddings()

    r_with, _ = recall(with_values, gold_questions, top_k=2, expand_fk=False)
    r_without, _ = recall(without, gold_questions, top_k=2, expand_fk=False)
    assert r_with >= r_without


# ---------------------------------------------------------------------------
# Recall over the gold set (the thesis's schema-linking metric)
# ---------------------------------------------------------------------------
def test_recall_at_k(index, gold_questions):
    r2, _ = recall(index, gold_questions, top_k=2, expand_fk=False)
    r3, _ = recall(index, gold_questions, top_k=3, expand_fk=False)
    r5, _ = recall(index, gold_questions, top_k=5, expand_fk=False)
    assert r2 >= 0.80
    assert r3 >= r2
    assert r5 >= 0.85


def test_fk_expansion_helps_recall(index, gold_questions):
    plain, plain_covered = recall(index, gold_questions, top_k=3, expand_fk=False)
    expanded, expanded_covered = recall(index, gold_questions, top_k=3, expand_fk=True)
    assert expanded > plain
    assert expanded_covered >= plain_covered
    assert expanded >= 0.90


def test_fk_expansion_only_adds_join_bridges(index):
    """Expansion must stay bounded — it is not "add every neighbour"."""
    result = index.retrieve(
        "Which clients spent the most money?", top_k=2, fallback_max_tables=0,
        expand_fk=True,
    )
    assert len(result.expanded) <= 3
    assert len(result.tables) <= 5


# ---------------------------------------------------------------------------
# Modes / knobs
# ---------------------------------------------------------------------------
def test_small_schema_falls_back_to_the_whole_schema(index, catalog):
    result = index.retrieve("anything at all", top_k=2, fallback_max_tables=50)
    assert result.mode == "full"
    assert set(result.tables) == set(catalog.table_names)


def test_top_k_mode_when_the_schema_is_large(index):
    result = index.retrieve("average salary", top_k=2, fallback_max_tables=0, expand_fk=False)
    assert result.mode == "topk"
    assert len(result.tables) == 2


def test_top_k_limits_the_prompt_size(index):
    small = index.retrieve("average salary", top_k=2, fallback_max_tables=0, expand_fk=False)
    full = index.retrieve("average salary", top_k=2, fallback_max_tables=50)
    assert len(small.prompt_text) < len(full.prompt_text)


def test_ranking_is_always_reported_even_in_full_mode(index, catalog):
    """Schema-linking recall must stay measurable regardless of the mode."""
    result = index.retrieve("average salary", top_k=2, fallback_max_tables=50)
    assert len(result.ranking) == len(catalog.tables)
    assert result.to_dict()["ranking"][0]["table"] == "employees"


def test_min_score_filters_weak_matches(index):
    result = index.retrieve(
        "zzzz", top_k=5, fallback_max_tables=0, min_score=10.0, expand_fk=False
    )
    # nothing clears the threshold -> the best table is still returned
    assert len(result.tables) == 1


# ---------------------------------------------------------------------------
# Embedder behaviour
# ---------------------------------------------------------------------------
def test_hashing_embedder_is_deterministic_and_normalised():
    a = HashingEmbedder().encode(["how many vehicles are available"])[0]
    b = HashingEmbedder().encode(["how many vehicles are available"])[0]
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_hashing_embedder_separates_unrelated_texts():
    emb = HashingEmbedder()
    vehicles, salary, vehicles2 = emb.encode(
        ["vehicles fleet make model", "employee salary payroll", "fleet of vehicles"]
    )
    assert cosine(vehicles, vehicles2) > cosine(vehicles, salary)


def test_tokenizer_drops_stopwords():
    assert "the" not in tokenize("What are the vehicles")
    assert "vehicles" in tokenize("What are the vehicles")


def test_build_embedder_falls_back_to_hashing_for_a_missing_model():
    embedder = build_embedder("auto", "definitely/not-a-real-model-name")
    assert embedder.name == "hashing"


def test_build_embedder_honours_the_hashing_backend():
    assert build_embedder("hashing", "sentence-transformers/all-MiniLM-L6-v2").name == "hashing"


@pytest.mark.slow
def test_sentence_transformer_backend_if_available(catalog, value_index, gold_questions):
    st = pytest.importorskip("sentence_transformers")
    from retrieval import SentenceTransformerEmbedder

    try:
        embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as exc:  # no network / no cached model
        pytest.skip(f"model unavailable: {exc}")

    idx = SchemaIndex(catalog, embedder, value_index=value_index)
    idx.build_embeddings()
    score, _ = recall(idx, gold_questions, top_k=3, expand_fk=True)
    assert score >= 0.90


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_index_roundtrips_through_disk(tmp_path, catalog, value_index):
    idx = SchemaIndex(catalog, HashingEmbedder(), value_index=value_index)
    idx.build_embeddings()
    path = tmp_path / "index.json"
    idx.save(str(path))

    loaded = SchemaIndex.load(str(path), catalog, HashingEmbedder())
    assert loaded is not None
    assert loaded.embeddings == idx.embeddings
    assert loaded.value_index.size == value_index.size
    assert loaded.retrieve("average salary", top_k=2, fallback_max_tables=0).tables == \
        idx.retrieve("average salary", top_k=2, fallback_max_tables=0).tables


def test_index_is_rebuilt_when_the_schema_changes(tmp_path, catalog):
    idx = SchemaIndex(catalog, HashingEmbedder())
    idx.build_embeddings()
    path = tmp_path / "index.json"
    idx.save(str(path))

    changed = json.loads(json.dumps(catalog.to_dict()))
    changed["fingerprint"] = "deadbeef"
    from schema_store import SchemaCatalog

    assert SchemaIndex.load(str(path), SchemaCatalog.from_dict(changed), HashingEmbedder()) is None


def test_index_is_rebuilt_when_the_embedder_changes(tmp_path, catalog):
    idx = SchemaIndex(catalog, HashingEmbedder())
    idx.build_embeddings()
    path = tmp_path / "index.json"
    idx.save(str(path))

    class OtherEmbedder(HashingEmbedder):
        name = "other-model"

    assert SchemaIndex.load(str(path), catalog, OtherEmbedder()) is None
