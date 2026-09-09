"""The evaluation databases.

One question set, one database, several ways of answering it -- that is the
benchmark's design, and this module is what lets "one database" be a choice
rather than a constant. Everything that differs between evaluation databases
lives here, so `run.py` does not grow a branch per dataset and the arms stay
identical across them.

  car_rental      9 tables, ~70 columns, 8,026 rows. The whole schema fits in a
                  prompt with room to spare, so the naive arm -- which dumps it
                  all into one call -- is a strong baseline and retrieval has
                  little to prove.
  adventureworks  68 tables, 1,099 columns, 91 foreign keys, ~761k rows across
                  five schemas. The schema is ~9x larger, so choosing the right
                  handful of tables stops being free. This is the point of it.

Adding a dataset means adding an entry here and a questions file; no arm and no
scorer changes, which is what keeps the comparison honest.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import subprocess
import sys


@dataclasses.dataclass(frozen=True)
class Dataset:
    name: str
    db_name: str
    domain: str          # fills {domain} in the naive prompt
    questions_file: str
    schema_file: str     # relative to the repo root; the naive arm's prompt
    probe_sql: str       # returns a row once the database is seeded
    search_path: str | None = None
    note: str = ""
    # Which engine the fixture runs on, and therefore which dialect the arms are
    # asked for. PostgreSQL for everything this project ships; BIRD is SQLite
    # because that is the engine its 1,534 gold queries were written against,
    # and translating them would be substituting our SQL for the benchmark's.
    backend: str = "postgres"
    dialect: str = "PostgreSQL"

    def schema_text(self, repo: pathlib.Path) -> str:
        return (repo / self.schema_file).read_text()

    def schema_for(self, repo: pathlib.Path):
        """What the naive arm puts in its prompt.

        Returns a string when the dataset is one database, or a
        `question -> schema` callable when it is several. Single-database
        datasets keep returning the same string they always did, so their
        prompts are byte-identical to the ones already measured.
        """
        return self.schema_text(repo)

    def questions_path(self, benchmark_dir: pathlib.Path) -> pathlib.Path:
        return benchmark_dir / self.questions_file

    def seed(self, conn, repo: pathlib.Path) -> None:
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class CarRental(Dataset):
    def seed(self, conn, repo: pathlib.Path) -> None:
        conn.execute((repo / "test_app_db" / "init" / "01_schema.sql").read_text())
        conn.execute((repo / "benchmark_data" / "car_rental_seed_postgres.sql").read_text())
        print("seeded throwaway database from the frozen dataset")


@dataclasses.dataclass(frozen=True)
class AdventureWorks(Dataset):
    def seed(self, conn, repo: pathlib.Path) -> None:
        """Delegate to the setup script rather than duplicating the load here.

        The upstream CSVs are 102 MB and are fetched from a pinned commit, and
        the load needs psql for its `\\copy` lines, so it cannot run over this
        psycopg connection. setup.py owns the whole procedure, including the
        four documented patches; this just invokes it.
        """
        script = repo / "benchmark_data" / "adventureworks" / "setup.py"
        print(f"adventureworks not present; running {script.relative_to(repo)}")
        subprocess.run([sys.executable, str(script)], check=True)


@dataclasses.dataclass(frozen=True)
class BirdDev(Dataset):
    """BIRD-SQL dev: 1,534 questions over 11 SQLite databases.

    The first dataset here that is not one database. Two consequences, both
    handled by the base class's hooks rather than by branching in `run.py`:
    the schema in the naive arm's prompt is a property of the question, and the
    connection the scorer executes against is too.

    Nothing is seeded. The databases are the upstream artefact, downloaded and
    left read-only; `benchmark_data/bird/prepare.py` builds the schema files and
    the question set from them and is what has to be run first.
    """

    db_root: str = "benchmark_data/bird/dev_20240627/dev_databases"
    schema_dir: str = "benchmark_data/bird/schemas"

    def schema_text(self, repo: pathlib.Path) -> str:
        raise RuntimeError(
            "bird_dev has 11 schemas; use schema_for(repo) and pass it a question")

    def schema_for(self, repo: pathlib.Path):
        # Read once and cached: 11 files against 1,534 questions is 1,523
        # pointless reads otherwise, and the run is long enough already.
        cache: dict[str, str] = {}

        def schema(q: dict) -> str:
            db_id = q["db_id"]
            if db_id not in cache:
                cache[db_id] = (repo / self.schema_dir / f"{db_id}.sql").read_text()
            return cache[db_id]

        return schema

    def sqlite_path(self, repo: pathlib.Path, db_id: str) -> pathlib.Path:
        return repo / self.db_root / db_id / f"{db_id}.sqlite"

    def seed(self, conn, repo: pathlib.Path) -> None:
        raise RuntimeError("bird_dev is not seeded; run benchmark_data/bird/prepare.py")


REGISTRY: dict[str, Dataset] = {
    "car_rental": CarRental(
        name="car_rental",
        db_name="car_rental",
        # Reproduces the original prompt string exactly, so results recorded
        # before this module existed remain comparable.
        domain="a car rental company database",
        questions_file="questions.yaml",
        schema_file="test_app_db/init/01_schema.sql",
        probe_sql="SELECT 1 FROM information_schema.tables WHERE table_name='vehicles'",
    ),
    "adventureworks": AdventureWorks(
        name="adventureworks",
        db_name="adventureworks",
        domain="the AdventureWorks database of a bicycle manufacturer and retailer",
        questions_file="questions_adventureworks.yaml",
        schema_file="benchmark_data/adventureworks_schema.sql",
        probe_sql="SELECT 1 FROM information_schema.tables "
                  "WHERE table_schema='sales' AND table_name='salesorderheader'",
        # The 68 tables are spread over five schemas and no table name is
        # ambiguous between them (checked: zero collisions), so resolving
        # unqualified names costs nothing and removes a failure mode that has
        # nothing to do with translating the question: a query that is right in
        # every respect except for omitting `sales.` is not a text-to-SQL error
        # worth counting. Fully qualified names keep working unchanged.
        search_path="person,humanresources,production,purchasing,sales,public",
        note="68 tables / 1,099 columns / 91 FKs / ~761k rows",
    ),
    "bird_dev": BirdDev(
        name="bird_dev",
        db_name="bird_dev",
        domain="the database described below",
        questions_file="questions_bird_dev.json",
        # Unused: BirdDev overrides schema_text and schema_for. Recorded so the
        # field means something when someone greps for where a schema comes from.
        schema_file="benchmark_data/bird/schemas",
        probe_sql="",
        backend="sqlite",
        dialect="SQLite",
        note="1,534 questions over 11 SQLite databases; BIRD-SQL dev, "
             "question revision 2026-11-06",
    ),
    # Same questions, same databases, same arm -- the schema in the prompt is
    # the only thing that differs. BIRD withholds its column dictionary from the
    # DDL on purpose (`financial.A3` reads as `A3 TEXT not null` and means
    # "region"), so `bird_dev` measures this project's own prompt contract on a
    # harder database, and `bird_dev_dict` measures what that withheld
    # dictionary is worth. Neither is the "real" number; the pair is the result.
    "bird_dev_dict": BirdDev(
        name="bird_dev_dict",
        db_name="bird_dev",
        domain="the database described below",
        questions_file="questions_bird_dev.json",
        schema_file="benchmark_data/bird/schemas_dict",
        schema_dir="benchmark_data/bird/schemas_dict",
        probe_sql="",
        backend="sqlite",
        dialect="SQLite",
        note="bird_dev plus BIRD's per-column descriptions in the prompt",
    ),
}

DEFAULT = "car_rental"


def questions_fingerprint(questions: list[dict]) -> str:
    """Short digest of a question set's scoreable content.

    Recorded in every results file and checked when the results are rendered.
    Changing a question's wording invalidates any stored answer to it, and the
    failure is silent: the numbers still add up, they just describe a different
    experiment. A file whose fingerprint does not match the current question set
    is stale, and saying so in the table is cheaper than remembering it.

    Only id, question text and gold SQL are hashed -- a reworded note or a
    changed expected_chart does not invalidate a stored answer.
    """
    payload = json.dumps([[q["id"], q["question"], q.get("gold_sql")] for q in questions],
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
