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

    def schema_text(self, repo: pathlib.Path) -> str:
        return (repo / self.schema_file).read_text()

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
