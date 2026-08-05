"""Central configuration for the RAG service.

Everything that the evaluation chapter needs to ablate (top-k, retry budget,
fallback threshold, embedding backend) is an environment variable with a
documented default so an experiment run is a matter of changing the
environment, never the code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env_str(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env_str(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    return _env_str(name, "true" if default else "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _env_opt_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@dataclass
class Settings:
    # --- LLM -------------------------------------------------------------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- SQL execution ---------------------------------------------------
    sql_backend_url: str = "http://test_app_backend:8080"
    target_database_url: str = ""
    # http  -> execute through the Rust backend (default, keeps the old path)
    # direct-> execute through psycopg (enables SET ROLE + RLS enforcement)
    executor: str = "http"
    sql_dialect: str = "postgres"
    max_rows: int = 200
    statement_timeout_ms: int = 5000

    # --- Schema retrieval ------------------------------------------------
    retrieval_enabled: bool = True
    retrieval_top_k: int = 6
    # if the database has <= this many tables the whole schema is injected
    # (the "fallback" arm of the ablation)
    retrieval_fallback_max_tables: int = 8
    retrieval_min_score: float = 0.0
    retrieval_expand_fk: bool = True
    embedding_backend: str = "auto"  # auto | sentence-transformers | hashing
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    index_dir: str = "/app/data/index"
    introspect_schemas: str = "public"

    # --- Value index -----------------------------------------------------
    value_index_enabled: bool = True
    value_index_max_distinct: int = 60
    value_index_sample_rows: int = 5000
    value_index_max_value_len: int = 64

    # --- Self-repair loop ------------------------------------------------
    max_repair_attempts: int = 2
    dry_run_enabled: bool = True
    clarification_enabled: bool = True

    # --- Authorization ---------------------------------------------------
    policy_enabled: bool = True
    policy_file: str = "/app/policy.yaml"
    default_user_id: str = "demo"
    default_user_role: str = "manager"
    default_user_location_id: int | None = None

    # --- Telemetry -------------------------------------------------------
    telemetry_enabled: bool = True
    telemetry_path: str = "/app/data/telemetry.jsonl"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gemini_api_key=_env_str("GEMINI_API_KEY", ""),
            gemini_model=_env_str("GEMINI_MODEL", "gemini-2.5-flash"),
            sql_backend_url=_env_str("SQL_BACKEND_URL", "http://test_app_backend:8080"),
            target_database_url=_env_str("TARGET_DATABASE_URL", ""),
            executor=_env_str("SQL_EXECUTOR", "http").lower(),
            sql_dialect=_env_str("SQL_DIALECT", "postgres"),
            max_rows=_env_int("SQL_MAX_ROWS", 200),
            statement_timeout_ms=_env_int("SQL_STATEMENT_TIMEOUT_MS", 5000),
            retrieval_enabled=_env_bool("RETRIEVAL_ENABLED", True),
            retrieval_top_k=_env_int("RETRIEVAL_TOP_K", 6),
            retrieval_fallback_max_tables=_env_int("RETRIEVAL_FALLBACK_MAX_TABLES", 8),
            retrieval_min_score=_env_float("RETRIEVAL_MIN_SCORE", 0.0),
            retrieval_expand_fk=_env_bool("RETRIEVAL_EXPAND_FK", True),
            embedding_backend=_env_str("EMBEDDING_BACKEND", "auto").lower(),
            embedding_model=_env_str(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            index_dir=_env_str("INDEX_DIR", "/app/data/index"),
            introspect_schemas=_env_str("INTROSPECT_SCHEMAS", "public"),
            value_index_enabled=_env_bool("VALUE_INDEX_ENABLED", True),
            value_index_max_distinct=_env_int("VALUE_INDEX_MAX_DISTINCT", 60),
            value_index_sample_rows=_env_int("VALUE_INDEX_SAMPLE_ROWS", 5000),
            value_index_max_value_len=_env_int("VALUE_INDEX_MAX_VALUE_LEN", 64),
            max_repair_attempts=_env_int("MAX_REPAIR_ATTEMPTS", 2),
            dry_run_enabled=_env_bool("DRY_RUN_ENABLED", True),
            clarification_enabled=_env_bool("CLARIFICATION_ENABLED", True),
            policy_enabled=_env_bool("POLICY_ENABLED", True),
            policy_file=_env_str("POLICY_FILE", "/app/policy.yaml"),
            default_user_id=_env_str("DEFAULT_USER_ID", "demo"),
            default_user_role=_env_str("DEFAULT_USER_ROLE", "manager"),
            default_user_location_id=_env_opt_int("DEFAULT_USER_LOCATION_ID"),
            telemetry_enabled=_env_bool("TELEMETRY_ENABLED", True),
            telemetry_path=_env_str("TELEMETRY_PATH", "/app/data/telemetry.jsonl"),
        )

    def ablation_knobs(self) -> dict:
        """The subset of settings the evaluation chapter varies."""
        return {
            "retrieval_enabled": self.retrieval_enabled,
            "retrieval_top_k": self.retrieval_top_k,
            "retrieval_fallback_max_tables": self.retrieval_fallback_max_tables,
            "retrieval_expand_fk": self.retrieval_expand_fk,
            "value_index_enabled": self.value_index_enabled,
            "embedding_backend": self.embedding_backend,
            "embedding_model": self.embedding_model,
            "max_repair_attempts": self.max_repair_attempts,
            "dry_run_enabled": self.dry_run_enabled,
            "clarification_enabled": self.clarification_enabled,
            "policy_enabled": self.policy_enabled,
            "max_rows": self.max_rows,
            "sql_dialect": self.sql_dialect,
            "model": self.gemini_model,
        }

    def public_dict(self) -> dict:
        data = asdict(self)
        data.pop("gemini_api_key", None)
        data["gemini_api_key_configured"] = bool(self.gemini_api_key)
        return data


settings = Settings.from_env()
