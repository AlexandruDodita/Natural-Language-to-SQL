"""Service state: everything built once at startup.

Startup sequence:
  1. connect to the target database and introspect the catalog (cached on disk,
     so a database outage degrades to the last known schema instead of a crash);
  2. load or build the embedding index and the value index (keyed on the catalog
     fingerprint, so boots after the first one are fast);
  3. load the authorization policy;
  4. build the LLM client.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import schema_store
from db import QueryResult, SessionContext, build_runners
from llm import build_client
from policy import DEFAULT_POLICY, PolicyEngine, UserContext
from retrieval import RetrievalResult, SchemaIndex, build_embedder, build_value_index
from schema_store import SchemaCatalog

logger = logging.getLogger(__name__)


class ServiceState:
    def __init__(self, settings):
        self.settings = settings
        self.catalog: Optional[SchemaCatalog] = None
        self.index: Optional[SchemaIndex] = None
        self.policy: Optional[PolicyEngine] = None
        self.llm = None
        self.runner = None
        self.direct_runner = None
        self.schema_text_fallback = schema_store.LEGACY_SCHEMA_TEXT
        self.status: dict = {}

    # -- paths ------------------------------------------------------------
    @property
    def catalog_path(self) -> str:
        return os.path.join(self.settings.index_dir, "catalog.json")

    @property
    def index_path(self) -> str:
        return os.path.join(self.settings.index_dir, "index.json")

    # -- startup ----------------------------------------------------------
    async def initialize(self) -> None:
        settings = self.settings
        self.runner, self.direct_runner = build_runners(settings)
        self.llm = build_client(settings)

        await self._load_catalog()
        self._load_policy()
        await self._load_index()

        self.status = {
            "executor": getattr(self.runner, "name", "unknown"),
            "introspection": "live" if self.direct_runner else "unavailable",
            "tables": len(self.catalog.tables) if self.catalog else 0,
            "fingerprint": self.catalog.fingerprint if self.catalog else None,
            "embedder": getattr(self.index.embedder, "name", None) if self.index else None,
            "value_index_size": self.index.value_index.size if self.index else 0,
            "policy_roles": sorted(self.policy.roles) if self.policy else [],
            "model": getattr(self.llm, "name", "unknown"),
        }
        logger.info("service state ready: %s", self.status)

    async def _load_catalog(self) -> None:
        schemas = [s.strip() for s in self.settings.introspect_schemas.split(",") if s.strip()]
        if self.direct_runner is not None:
            try:
                self.catalog = await schema_store.introspect(self.direct_runner, schemas)
                self.catalog.save(self.catalog_path)
                self.schema_text_fallback = self.catalog.render()
                logger.info(
                    "introspected %d tables from %s",
                    len(self.catalog.tables),
                    self.catalog.database,
                )
                return
            except Exception as exc:
                logger.error("introspection failed: %s", exc)

        cached = SchemaCatalog.load(self.catalog_path)
        if cached is not None:
            self.catalog = cached
            self.schema_text_fallback = cached.render()
            logger.warning("using the cached schema catalog (%d tables)", len(cached.tables))
        else:
            logger.warning("no catalog available; falling back to the bundled schema text")

    def _load_policy(self) -> None:
        if not self.settings.policy_enabled:
            self.policy = None
            return
        try:
            self.policy = PolicyEngine.from_file(
                self.settings.policy_file,
                catalog=self.catalog,
                dialect=self.settings.sql_dialect,
            )
        except Exception as exc:
            logger.error(
                "could not load the policy file %s (%s); falling back to a "
                "single unrestricted role",
                self.settings.policy_file,
                exc,
            )
            self.policy = PolicyEngine(
                DEFAULT_POLICY, catalog=self.catalog, dialect=self.settings.sql_dialect
            )

    async def _load_index(self) -> None:
        if not self.settings.retrieval_enabled or self.catalog is None:
            self.index = None
            return

        embedder = build_embedder(
            self.settings.embedding_backend, self.settings.embedding_model
        )
        index = SchemaIndex.load(self.index_path, self.catalog, embedder)
        if index is None:
            index = SchemaIndex(self.catalog, embedder)
            index.build_embeddings()
            if self.settings.value_index_enabled and self.direct_runner is not None:
                try:
                    index.value_index = await build_value_index(
                        self.direct_runner,
                        self.catalog,
                        max_distinct=self.settings.value_index_max_distinct,
                        sample_rows=self.settings.value_index_sample_rows,
                        max_value_len=self.settings.value_index_max_value_len,
                    )
                except Exception as exc:
                    logger.warning("value index build failed: %s", exc)
            try:
                index.save(self.index_path)
            except OSError as exc:
                logger.warning("could not persist the index: %s", exc)
        self.index = index

    async def rebuild_index(self) -> dict:
        """Re-introspect and rebuild both indexes (POST /admin/reindex)."""
        try:
            os.remove(self.index_path)
        except OSError:
            pass
        await self._load_catalog()
        self._load_policy()
        await self._load_index()
        self.status["tables"] = len(self.catalog.tables) if self.catalog else 0
        self.status["fingerprint"] = self.catalog.fingerprint if self.catalog else None
        self.status["value_index_size"] = self.index.value_index.size if self.index else 0
        return self.status

    # -- runtime ----------------------------------------------------------
    @property
    def can_explain(self) -> bool:
        return self.direct_runner is not None

    def retrieve(self, question: str, top_k: Optional[int] = None) -> Optional[RetrievalResult]:
        if self.index is None:
            return None
        return self.index.retrieve(
            question,
            top_k=top_k or self.settings.retrieval_top_k,
            fallback_max_tables=self.settings.retrieval_fallback_max_tables,
            min_score=self.settings.retrieval_min_score,
            expand_fk=self.settings.retrieval_expand_fk,
        )

    async def execute(self, sql: str, session: SessionContext) -> QueryResult:
        if getattr(self.runner, "supports_session_context", False):
            return await self.runner.execute(sql, session=session)
        return await self.runner.execute(sql)

    def user_context(self, payload: Optional[dict]) -> UserContext:
        """Build the user context from the request, falling back to server defaults."""
        settings = self.settings
        payload = payload or {}
        return UserContext(
            user_id=payload.get("user_id") or settings.default_user_id,
            role=payload.get("role") or settings.default_user_role,
            location_id=(
                payload.get("location_id")
                if payload.get("location_id") is not None
                else settings.default_user_location_id
            ),
            attributes=payload.get("attributes") or {},
        )
