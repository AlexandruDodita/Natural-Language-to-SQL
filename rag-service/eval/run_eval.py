#!/usr/bin/env python3
"""Retrieval ablation harness — produces the schema-linking results table.

Runs offline against the committed catalog fixture (no database, no API key):

    python eval/run_eval.py
    python eval/run_eval.py --embedder sentence-transformers/all-MiniLM-L6-v2
    python eval/run_eval.py --format latex
    python eval/run_eval.py --telemetry data/telemetry.jsonl   # aggregate a run

Metrics per configuration:
  recall      micro-averaged recall of gold tables (hits / gold tables)
  coverage    share of questions whose gold tables are *all* retrieved
  tables      average number of tables injected into the prompt
  latency     average retrieval time per question
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval import HashingEmbedder, SchemaIndex, ValueIndex, build_embedder  # noqa: E402
from schema_store import SchemaCatalog  # noqa: E402
from telemetry import Telemetry  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def load_index(embedder_name: str, use_values: bool) -> SchemaIndex:
    catalog = SchemaCatalog.from_dict(
        json.loads((FIXTURES / "car_rental_catalog.json").read_text())
    )
    values = (
        ValueIndex.from_dict(json.loads((FIXTURES / "car_rental_value_index.json").read_text()))
        if use_values
        else ValueIndex()
    )
    embedder = (
        HashingEmbedder() if embedder_name == "hashing" else build_embedder("auto", embedder_name)
    )
    index = SchemaIndex(catalog, embedder, value_index=values)
    index.build_embeddings()
    return index


def evaluate(index: SchemaIndex, gold: list[dict], top_k: int, expand_fk: bool) -> dict:
    total = hits = covered = tables = 0
    started = time.perf_counter()
    misses = []
    for item in gold:
        result = index.retrieve(
            item["question"], top_k=top_k, fallback_max_tables=0, expand_fk=expand_fk
        )
        wanted, got = set(item["tables"]), set(result.tables)
        total += len(wanted)
        hits += len(wanted & got)
        tables += len(got)
        if wanted <= got:
            covered += 1
        else:
            misses.append((item["id"], sorted(wanted - got)))
    elapsed = (time.perf_counter() - started) * 1000.0 / max(1, len(gold))
    return {
        "top_k": top_k,
        "fk_expansion": expand_fk,
        "recall": hits / total,
        "coverage": covered / len(gold),
        "avg_tables": tables / len(gold),
        "latency_ms": elapsed,
        "misses": misses,
    }


def print_table(rows: list[dict], fmt: str) -> None:
    header = ["top_k", "fk_exp", "recall", "coverage", "tables", "ms"]
    if fmt == "latex":
        print("\\begin{tabular}{llrrrr}")
        print("\\toprule")
        print(" & ".join(header) + " \\\\")
        print("\\midrule")
        for r in rows:
            print(
                f"{r['top_k']} & {'da' if r['fk_expansion'] else 'nu'} & "
                f"{r['recall']:.3f} & {r['coverage']:.3f} & "
                f"{r['avg_tables']:.1f} & {r['latency_ms']:.1f} \\\\"
            )
        print("\\bottomrule")
        print("\\end{tabular}")
        return

    print(f"{'k':>3} {'fk':>5} {'recall':>7} {'cover':>7} {'tables':>7} {'ms':>6}")
    for r in rows:
        print(
            f"{r['top_k']:>3} {str(r['fk_expansion']):>5} {r['recall']:>7.3f} "
            f"{r['coverage']:>7.3f} {r['avg_tables']:>7.1f} {r['latency_ms']:>6.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default="hashing",
                        help="'hashing' or a sentence-transformer model name")
    parser.add_argument("--top-k", nargs="*", type=int, default=[2, 3, 4, 5])
    parser.add_argument("--no-values", action="store_true", help="disable the value index")
    parser.add_argument("--format", choices=["text", "latex", "json"], default="text")
    parser.add_argument("--telemetry", help="aggregate a telemetry JSONL file instead")
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args()

    if args.telemetry:
        print(json.dumps(Telemetry(args.telemetry).summary(), indent=2))
        return 0

    gold = json.loads((FIXTURES / "schema_linking_gold.json").read_text())["questions"]
    index = load_index(args.embedder, not args.no_values)

    rows = [
        evaluate(index, gold, k, fk)
        for k in args.top_k
        for fk in (False, True)
    ]

    if args.format == "json":
        print(json.dumps(rows, indent=2))
    else:
        print(
            f"embedder={getattr(index.embedder, 'name', '?')} "
            f"values={'off' if args.no_values else 'on'} "
            f"questions={len(gold)} tables={len(index.catalog.tables)}"
        )
        print_table(rows, args.format)

    if args.show_misses:
        for row in rows:
            if row["misses"]:
                print(f"\nk={row['top_k']} fk={row['fk_expansion']} misses:")
                for qid, tables in row["misses"]:
                    print(f"  {qid}: {', '.join(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
