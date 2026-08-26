"""Schema retrieval: the actual "R" of the RAG service.

Three signals are combined into a single ranking over tables:

1. **Dense similarity** between the question and a textual description of each
   table (name, comment, columns, types, foreign keys, CHECK domains).
   Embeddings are produced locally by a sentence-transformer; when the model is
   not installed a deterministic hashing embedder is used instead, so the
   service (and the test suite) never depends on a download or an API.
2. **Lexical overlap** between the question tokens and table/column names.
3. **Value matches** from a value index built over low-cardinality text columns,
   so that "Toyota" links to ``vehicles.make`` and "Miami" to ``locations.city``.

The result object keeps every intermediate score, which is what makes
schema-linking recall measurable in the evaluation chapter.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

from schema_store import SchemaCatalog, TableInfo

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are",
    "what", "which", "how", "many", "much", "show", "me", "list", "all", "by",
    "with", "from", "top", "most", "care", "sunt", "cei", "mai", "din", "la",
    "si", "cu", "pe", "ce", "cate", "cati",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


# ---------------------------------------------------------------------------
# Embedders
# ---------------------------------------------------------------------------
class HashingEmbedder:
    """Dependency-free deterministic embedder (hashed bag of tokens + 4-grams).

    Not as good as a neural encoder, but it is reproducible, needs no download
    and gives the ablation a meaningful "no dense model" baseline.
    """

    name = "hashing"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _features(self, text: str) -> Iterable[tuple[str, float]]:
        tokens = tokenize(text)
        for tok in tokens:
            yield tok, 1.0
            if len(tok) > 4:
                for i in range(len(tok) - 3):
                    yield tok[i : i + 4], 0.4

    def encode(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for feature, weight in self._features(text):
                h = int(hashlib.md5(feature.encode()).hexdigest()[:8], 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 31) & 1 == 0 else -1.0
                vec[idx] += sign * weight
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class SentenceTransformerEmbedder:
    """Local sentence-transformer (all-MiniLM-L6-v2 / bge-small-en-v1.5 / ...)."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy

        self.name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return [list(map(float, v)) for v in vectors]


def build_embedder(backend: str, model_name: str):
    """Return an embedder honouring EMBEDDING_BACKEND (auto|sentence-transformers|hashing)."""
    if backend == "hashing":
        return HashingEmbedder()
    try:
        return SentenceTransformerEmbedder(model_name)
    except Exception as exc:  # not installed, or model cannot be downloaded
        if backend == "sentence-transformers":
            raise
        logger.warning(
            "sentence-transformers unavailable (%s); using the hashing embedder", exc
        )
        return HashingEmbedder()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Value index
# ---------------------------------------------------------------------------
_TEXT_TYPES = ("character varying", "varchar", "text", "character", "char", "name")
_SKIP_COLUMN_HINTS = ("comment", "description", "address", "email", "phone", "notes")


@dataclass
class ValueIndex:
    """value (lowercased) -> list of "table.column" it appears in."""

    entries: dict[str, list[str]] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.entries)

    def add(self, value: str, table: str, column: str) -> None:
        key = value.strip().lower()
        if not key:
            return
        ref = f"{table}.{column}"
        self.entries.setdefault(key, [])
        if ref not in self.entries[key]:
            self.entries[key].append(ref)

    def lookup(self, question: str) -> list[dict]:
        q = " " + re.sub(r"[^a-z0-9]+", " ", (question or "").lower()) + " "
        hits: list[dict] = []
        for value, refs in self.entries.items():
            if len(value) < 3:
                continue
            needle = " " + re.sub(r"[^a-z0-9]+", " ", value) + " "
            if needle in q:
                for ref in refs:
                    table, column = ref.split(".", 1)
                    hits.append({"value": value, "table": table, "column": column})
        return hits

    def to_dict(self) -> dict:
        return {"entries": self.entries}

    @classmethod
    def from_dict(cls, data: dict) -> "ValueIndex":
        return cls(entries={k: list(v) for k, v in (data or {}).get("entries", {}).items()})


def _is_indexable_column(col) -> bool:
    dtype = (col.data_type or "").lower()
    if not any(dtype.startswith(t) for t in _TEXT_TYPES):
        return False
    lowered = col.name.lower()
    return not any(hint in lowered for hint in _SKIP_COLUMN_HINTS)


async def build_value_index(
    runner,
    catalog: SchemaCatalog,
    max_distinct: int = 60,
    sample_rows: int = 5000,
    max_value_len: int = 64,
) -> ValueIndex:
    """Sample low-cardinality text columns. Never materialises a whole column."""
    index = ValueIndex()
    for table in catalog.tables:
        for col in table.columns:
            if not _is_indexable_column(col):
                continue
            sql = (
                f'SELECT DISTINCT s."{col.name}" FROM '
                f'(SELECT "{col.name}" FROM {table.qualified_name} '
                f'LIMIT {int(sample_rows)}) s '
                f'WHERE s."{col.name}" IS NOT NULL '
                f'AND length(s."{col.name}") <= {int(max_value_len)} '
                f"LIMIT {int(max_distinct) + 1}"
            )
            try:
                res = await runner.execute(sql)
            except Exception as exc:
                logger.debug("value index skipped %s.%s: %s", table.name, col.name, exc)
                continue
            if res.row_count > max_distinct:
                continue  # high cardinality -> not a useful linking signal
            for row in res.rows:
                if row and row[0] is not None:
                    index.add(str(row[0]), table.qualified_name, col.name)
    return index


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
@dataclass
class TableScore:
    table: str
    score: float
    dense: float
    lexical: float
    value: float

    def to_dict(self) -> dict:
        return {
            "table": self.table,
            "score": round(self.score, 4),
            "dense": round(self.dense, 4),
            "lexical": round(self.lexical, 4),
            "value": round(self.value, 4),
        }


@dataclass
class RetrievalResult:
    mode: str  # "full" | "topk" | "disabled" | "fallback"
    tables: list[str]
    ranking: list[TableScore] = field(default_factory=list)
    value_matches: list[dict] = field(default_factory=list)
    expanded: list[str] = field(default_factory=list)
    prompt_text: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "tables": self.tables,
            "expanded": self.expanded,
            "ranking": [r.to_dict() for r in self.ranking],
            "value_matches": self.value_matches,
            "latency_ms": round(self.latency_ms, 2),
        }


W_DENSE = 1.0
W_LEXICAL = 0.6
W_VALUE = 0.8


class SchemaIndex:
    """Embedding index over table descriptions + value index, persisted to disk."""

    def __init__(
        self,
        catalog: SchemaCatalog,
        embedder,
        embeddings: Optional[dict[str, list[float]]] = None,
        value_index: Optional[ValueIndex] = None,
    ):
        self.catalog = catalog
        self.embedder = embedder
        self.embeddings: dict[str, list[float]] = embeddings or {}
        self.value_index = value_index or ValueIndex()

    # -- build / persist --------------------------------------------------
    def build_embeddings(self) -> None:
        tables = self.catalog.tables
        texts = [t.description() for t in tables]
        vectors = self.embedder.encode(texts) if texts else []
        self.embeddings = {
            t.qualified_name: v for t, v in zip(tables, vectors)
        }

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {
            "fingerprint": self.catalog.fingerprint,
            "embedder": getattr(self.embedder, "name", "unknown"),
            "embeddings": self.embeddings,
            "value_index": self.value_index.to_dict(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, path: str, catalog: SchemaCatalog, embedder) -> Optional["SchemaIndex"]:
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("fingerprint") != catalog.fingerprint:
            logger.info("schema fingerprint changed -> rebuilding index")
            return None
        if payload.get("embedder") != getattr(embedder, "name", "unknown"):
            logger.info("embedder changed -> rebuilding index")
            return None
        return cls(
            catalog,
            embedder,
            embeddings=payload.get("embeddings", {}),
            value_index=ValueIndex.from_dict(payload.get("value_index", {})),
        )

    # -- scoring ----------------------------------------------------------
    def _lexical_score(self, question_tokens: set[str], table: TableInfo) -> float:
        if not question_tokens:
            return 0.0
        name_tokens = set(tokenize(table.name))
        column_tokens: set[str] = set()
        for col in table.columns:
            column_tokens.update(tokenize(col.name))
        name_hit = len(question_tokens & name_tokens)
        # singular/plural tolerance ("client" vs "clients")
        for qt in question_tokens:
            for nt in name_tokens:
                if qt != nt and (qt.rstrip("s") == nt.rstrip("s")):
                    name_hit += 1
        col_hit = len(question_tokens & column_tokens)
        return min(1.0, 0.6 * min(name_hit, 2) + 0.2 * min(col_hit, 3))

    def rank(self, question: str) -> tuple[list[TableScore], list[dict]]:
        q_tokens = set(tokenize(question))
        value_matches = self.value_index.lookup(question)
        value_tables: dict[str, int] = {}
        for match in value_matches:
            value_tables[match["table"]] = value_tables.get(match["table"], 0) + 1

        q_vec = self.embedder.encode([question])[0] if self.embeddings else []

        scores: list[TableScore] = []
        for table in self.catalog.tables:
            emb = self.embeddings.get(table.qualified_name)
            dense = cosine(q_vec, emb) if emb and q_vec else 0.0
            dense = max(0.0, dense)
            lexical = self._lexical_score(q_tokens, table)
            value = min(1.0, 0.7 * value_tables.get(table.qualified_name, 0))
            total = W_DENSE * dense + W_LEXICAL * lexical + W_VALUE * value
            scores.append(
                TableScore(
                    table=table.qualified_name,
                    score=total,
                    dense=dense,
                    lexical=lexical,
                    value=value,
                )
            )
        scores.sort(key=lambda s: (-s.score, s.table))
        return scores, value_matches

    # -- retrieval --------------------------------------------------------
    def retrieve(
        self,
        question: str,
        top_k: int = 6,
        fallback_max_tables: int = 8,
        min_score: float = 0.0,
        expand_fk: bool = True,
        max_expansions: int = 3,
    ) -> RetrievalResult:
        start = time.perf_counter()
        ranking, value_matches = self.rank(question)

        if len(self.catalog.tables) <= fallback_max_tables:
            selected = [t.qualified_name for t in self.catalog.tables]
            result = RetrievalResult(
                mode="full",
                tables=selected,
                ranking=ranking,
                value_matches=value_matches,
            )
        else:
            selected = [s.table for s in ranking[:top_k] if s.score >= min_score]
            if not selected and ranking:
                selected = [ranking[0].table]
            expanded: list[str] = []
            if expand_fk:
                expanded = self._fk_expansion(selected, max_expansions)
            result = RetrievalResult(
                mode="topk",
                tables=selected + expanded,
                ranking=ranking,
                value_matches=value_matches,
                expanded=expanded,
            )

        result.prompt_text = self.render_prompt(result)
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return result

    def _fk_expansion(self, selected: list[str], max_expansions: int) -> list[str]:
        """Add join-bridge tables so the model can actually connect the selection."""
        chosen = set(selected)
        counts: dict[str, int] = {}
        for name in selected:
            for neighbour in self.catalog.neighbours(name):
                if neighbour in chosen:
                    continue
                counts[neighbour] = counts.get(neighbour, 0) + 1
        # a table linking two or more selected tables is a genuine join bridge
        bridges = sorted(
            (t for t, c in counts.items() if c >= 2),
            key=lambda t: (-counts[t], t),
        )
        return bridges[:max_expansions]

    def render_prompt(self, result: RetrievalResult) -> str:
        text = self.catalog.render(result.tables)
        if result.value_matches:
            lines = [
                f"- \"{m['value']}\" appears in {m['table']}.{m['column']}"
                for m in result.value_matches[:12]
            ]
            text += "\n\nLiteral values found in the question:\n" + "\n".join(lines)
        return text
