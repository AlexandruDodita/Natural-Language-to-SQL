#!/usr/bin/env python3
"""Turn the BIRD-SQL dev release into a question set this harness can run.

    python benchmark_data/bird/prepare.py

Two upstream artefacts are combined, because BIRD ships them separately:

  dev_20251106.json    the 2026-11-06 question revision, from HuggingFace
                       (birdsql/bird_sql_dev_20251106). Questions and gold SQL
                       only -- no databases.
  dev_20240627/        the database bundle from bird-bench.oss-cn-beijing,
                       which is where the 11 SQLite files actually live. The
                       November revision changed question wording and gold SQL,
                       not the databases, so pairing the two is correct; this
                       script verifies it by checking that every db_id named in
                       the questions exists as a database, and by executing
                       every gold query against it.

What it writes:

  schemas/<db_id>.sql            the CREATE TABLE statements, one file per
                                 database, for the naive arm's prompt
  schemas_dict/<db_id>.sql       the same, plus BIRD's own column dictionary
  benchmark/questions_bird_dev.json   the question set in this harness's format

Every question BIRD ships is kept. Gold validation still runs, because two
things have to be known before a 1,534-question set is worth spending on: that
no gold returns zero rows -- `run.py` aborts loudly on those, since an empty
gold is trivially matchable and would mark every wrong answer correct -- and
which golds cannot be executed at all. The second kind is recorded on the
question as `gold_status` and reported here rather than dropped, so the set the
harness runs is the set BIRD published and the exceptions stay visible.
"""

from __future__ import annotations

import collections
import csv
import io
import json
import pathlib
import sqlite3
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
DB_ROOT = HERE / "dev_20240627" / "dev_databases"
QUESTIONS_IN = HERE / "dev_20251106.json"
SCHEMA_DIR = HERE / "schemas"
SCHEMA_DICT_DIR = HERE / "schemas_dict"
QUESTIONS_OUT = REPO / "benchmark" / "questions_bird_dev.json"

# Generous compared with the 15 s the arms get: this runs once, and a gold
# query that needs 20 s on the 600 MB football database is still a usable
# question. Anything past this is excluded rather than left to stall a run.
GOLD_TIMEOUT_S = 60.0


def db_path(db_id: str) -> pathlib.Path:
    return DB_ROOT / db_id / f"{db_id}.sqlite"


def connect(db_id: str) -> sqlite3.Connection:
    """Read-only connection. Model SQL must not be able to touch the fixture."""
    return sqlite3.connect(f"file:{db_path(db_id)}?mode=ro", uri=True)


def deadline_handler(conn: sqlite3.Connection, seconds: float):
    """Wall-clock timeout for SQLite, which has no statement_timeout.

    sqlite3 aborts the running statement when the progress handler returns
    non-zero, which is the only way to bound a query that would otherwise scan
    a 600 MB table for minutes. The instruction count is a compromise: small
    enough to notice the deadline promptly, large enough not to dominate the
    query's own cost.
    """
    end = time.perf_counter() + seconds
    conn.set_progress_handler(lambda: 1 if time.perf_counter() > end else 0, 10_000)


def column_notes(db_id: str, table: str) -> list[str]:
    """BIRD's own column dictionary for one table, as `col : meaning` lines.

    This is the information BIRD deliberately keeps out of the DDL, and it is
    the difference between a guessable schema and an unguessable one: the
    `financial` database has a column called `A3` whose CREATE TABLE line says
    only `A3 TEXT not null`, and whose dictionary entry says `region`. No model
    recovers that from the DDL, so a run without this file is measuring
    something other than SQL ability on those questions.

    Kept in a second schema directory rather than merged into the first,
    because the plain-DDL prompt is what makes the BIRD rows comparable with
    this project's other datasets. The two directories are the two experiments.
    """
    path = DB_ROOT / db_id / "database_description" / f"{table}.csv"
    if not path.exists():
        # Upstream file names do not always match the table exactly (case, or a
        # trailing space); fall back to a case-insensitive match before giving up.
        cand = {p.stem.strip().lower(): p for p in
                (DB_ROOT / db_id / "database_description").glob("*.csv")}
        path = cand.get(table.strip().lower())
        if path is None:
            return []
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return []

    notes = []
    for row in csv.DictReader(io.StringIO(text)):
        col = (row.get("original_column_name") or "").strip()
        if not col:
            continue
        # column_name is the human label, column_description the prose, and
        # value_description the encoding of the values -- which is where the
        # traps live ("M/F", or a units note). Duplicates are common (BIRD often
        # repeats the column name in the description), so they are folded out
        # rather than printed twice.
        parts, seen = [], set()
        for key in ("column_name", "column_description", "value_description"):
            v = " ".join((row.get(key) or "").split())
            if v and v.lower() != col.lower() and v.lower() not in seen:
                seen.add(v.lower())
                parts.append(v)
        if parts:
            notes.append(f"{col} : {'; '.join(parts)}")
    return notes


def write_schemas() -> dict[str, int]:
    """One .sql per database, straight from sqlite_master.

    Raw DDL, deliberately: `car_rental` and `adventureworks` give the naive arm
    the schema and nothing else, and BIRD ships a column-description CSV per
    database that would hand this arm information the other two datasets never
    had. Using it would make the BIRD rows measure a different prompt.
    """
    SCHEMA_DIR.mkdir(exist_ok=True)
    SCHEMA_DICT_DIR.mkdir(exist_ok=True)
    sizes = {}
    for d in sorted(DB_ROOT.iterdir()):
        if not d.is_dir():
            continue
        conn = connect(d.name)
        rows = list(conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"))
        conn.close()
        text = ";\n\n".join(sql.strip() for _, sql in rows) + ";\n"
        (SCHEMA_DIR / f"{d.name}.sql").write_text(text)
        sizes[d.name] = len(text)

        blocks = []
        for name, sql in rows:
            blocks.append(sql.strip() + ";")
            notes = column_notes(d.name, name)
            if notes:
                blocks.append(f"-- {name} column meanings:\n" +
                              "\n".join(f"--   {n}" for n in notes))
        (SCHEMA_DICT_DIR / f"{d.name}.sql").write_text("\n\n".join(blocks) + "\n")
    return sizes


def main() -> int:
    if not QUESTIONS_IN.exists():
        sys.exit(f"missing {QUESTIONS_IN}; download it from "
                 "https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106")
    if not DB_ROOT.is_dir():
        sys.exit(f"missing {DB_ROOT}; unpack dev.zip from "
                 "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip here")

    raw = json.loads(QUESTIONS_IN.read_text())
    print(f"{len(raw)} questions, {len({r['db_id'] for r in raw})} databases")

    missing = sorted({r["db_id"] for r in raw} - {p.name for p in DB_ROOT.iterdir() if p.is_dir()})
    if missing:
        sys.exit(f"question set names databases that are not in the bundle: {missing}")

    sizes = write_schemas()
    print(f"wrote {len(sizes)} schema files to {SCHEMA_DIR.relative_to(REPO)} "
          f"and {SCHEMA_DICT_DIR.relative_to(REPO)}")

    conns: dict[str, sqlite3.Connection] = {}
    out: list[dict] = []
    status = collections.Counter()
    problems: list[dict] = []
    empty_gold: list[str] = []
    slow: list[tuple[float, str]] = []
    t_start = time.perf_counter()

    for i, r in enumerate(raw, 1):
        db_id = r["db_id"]
        if db_id not in conns:
            conns[db_id] = connect(db_id)
        conn = conns[db_id]
        qid = f"b{r['question_id']:04d}"

        t0 = time.perf_counter()
        try:
            deadline_handler(conn, GOLD_TIMEOUT_S)
            rows = conn.execute(r["SQL"]).fetchall()
            reason = None if rows else "gold returns zero rows"
        except Exception as e:
            rows, reason = None, f"{type(e).__name__}: {str(e).splitlines()[0][:120]}"
        finally:
            conn.set_progress_handler(None, 0)
        dt = time.perf_counter() - t0
        if dt > 5:
            slow.append((round(dt, 1), qid))

        if reason == "gold returns zero rows":
            empty_gold.append(qid)
        if reason:
            status[reason.split(":")[0]] += 1
            problems.append({"id": qid, "db_id": db_id, "reason": reason})
        else:
            status["ok"] += 1

        out.append({
            "id": qid,
            "question": r["question"],
            # BIRD's own difficulty label fills the harness's category slot, so
            # summarise()'s by_category breakdown becomes the simple/moderate/
            # challenging split BIRD reports against.
            "category": r["difficulty"],
            "lang": "en",
            "gold_sql": r["SQL"],
            # BIRD scores with an unordered comparison, so every question is
            # unordered here too. Deviating would make these rows incomparable
            # with every published BIRD number.
            "ordered": False,
            "db_id": db_id,
            # The external-knowledge hint. Part of BIRD's task definition -- the
            # questions are not answerable without it -- so it belongs in the
            # prompt, and it is carried on the question rather than baked into
            # the schema because it differs per question.
            "evidence": r.get("evidence") or "",
            # What executing this gold did at prepare time. "ok" for all but a
            # handful; anything else means the question cannot be scored, and
            # every arm records a gold_error against it identically -- so it
            # depresses all rows by the same amount and does not distort a
            # comparison between them.
            "gold_status": reason or "ok",
            "gold_rows": len(rows) if rows is not None else None,
        })
        if i % 200 == 0:
            print(f"  validated {i}/{len(raw)}", flush=True)

    for c in conns.values():
        c.close()
    elapsed = time.perf_counter() - t_start

    QUESTIONS_OUT.write_text(json.dumps({"questions": out}, indent=1, ensure_ascii=False))
    (HERE / "gold_problems.json").write_text(json.dumps(problems, indent=1))

    print(f"\ngold validation took {elapsed/60:.1f} min "
          f"({elapsed/len(raw)*1000:.0f} ms/question)")
    print(f"questions written {len(out)}  (every question BIRD ships)")
    for reason, n in status.most_common():
        print(f"  {n:5d}  {reason}")
    print(f"\nby difficulty: {dict(collections.Counter(q['category'] for q in out))}")
    print(f"by database  : {dict(collections.Counter(q['db_id'] for q in out))}")
    if slow:
        slow.sort(reverse=True)
        print(f"\nslowest golds: {slow[:5]}")
    if empty_gold:
        print(f"\nWARNING: {len(empty_gold)} gold queries return zero rows: "
              f"{empty_gold[:10]}. run.py aborts on these -- an empty gold "
              f"matches any query returning nothing, including a wrong one.")
    print(f"\nwrote {QUESTIONS_OUT.relative_to(REPO)}")
    print(f"wrote {(HERE / 'gold_problems.json').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
