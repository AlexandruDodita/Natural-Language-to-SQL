# Benchmark datasets

Two evaluation databases live here. `adventureworks/` holds the setup script
for the 68-table AdventureWorks OLTP database (fetched from a pinned upstream
commit rather than committed, since its CSVs are 102 MB) and
`adventureworks_schema.sql` is the generated schema-only DDL the naive arm puts
in its prompt. See `benchmark/README.md` for what each database is for.

The rest of this file documents the frozen car rental dataset.

# Frozen car rental dataset

`car_rental_seed_postgres.sql` and `test_app_db_oracle/init/02_seed_data.sql` hold the
same 8,026 rows as literal `INSERT` statements — 10 locations, 5 vehicle categories,
600 clients, 40 employees, 80 vehicles, 3,000 reservations, 2,691 payments, 400
maintenance records, 1,200 reviews.

## Why the data is frozen rather than generated

`test_app_db/init/02_seed_data.sql` generates its rows with `setseed(0.42)` and
`random()`. That is reproducible only on one PostgreSQL major version: **PostgreSQL 16
replaced the `random()` PRNG**, so the identical script produces different rows on PG 15
than on PG 16. Two consequences matter for the evaluation:

1. **Cross-engine comparison.** If Oracle were seeded by re-implementing the same
   generation with `DBMS_RANDOM`, the two databases would hold different data, and any
   accuracy difference between the Oracle and PostgreSQL arms would be confounded by the
   data rather than attributable to dialect or tooling.
2. **Reproducibility.** A grader rebuilding the volume on a different PostgreSQL image
   would get different rows and therefore different numbers than those reported.

Freezing removes both problems: every engine, every version, every rebuild loads
byte-identical rows.

## Provenance and verification

Generated once from the original generative seed on PostgreSQL 16.2, then verified by
loading the frozen dump into a fresh database and comparing a per-table SHA-256 of all
rows against the source database. All nine tables matched exactly, and the identity
sequences resync past the explicit ids (a subsequent insert into `locations` returns
id 11, not 1).

The Oracle dump additionally converts types at generation time: `DATE` →
`TO_DATE(...)`, `TIMESTAMP` → `TO_TIMESTAMP(..., 'YYYY-MM-DD HH24:MI:SS.FF6')`,
booleans → `1`/`0`, and `reviews.comment` → `reviews.comment_text` (see the header of
`test_app_db_oracle/init/01_schema.sql` for why that column is renamed). The longest
text value is 56 characters, comfortably inside Oracle's 4,000-character inline string
limit, so no `CLOB` chunking is needed. All 8,026 statements parse under sqlglot's
Oracle dialect.

## Adopting it on the PostgreSQL side

The Oracle side already loads its frozen dump automatically. The PostgreSQL side still
runs the original generative script. To switch it — recommended, so both arms and every
rebuild agree:

```bash
cp benchmark_data/car_rental_seed_postgres.sql test_app_db/init/02_seed_data.sql
docker compose down -v test_app_db && docker compose up -d test_app_db
```

The `-v` matters: init scripts only run on an empty volume, so an existing volume keeps
its old generated rows regardless of what the file says.

Keeping the generative script instead is a valid choice, but then the Oracle arm must be
re-dumped from whichever PostgreSQL image is actually in use, and the reported numbers
are tied to that image version.
