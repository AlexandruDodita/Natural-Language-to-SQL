"""Shared style + data access for every figure in the thesis.

Numbers are read out of benchmark/results/*.json. Nothing here is
transcribed by hand, for the same reason benchmark.md isn't: a figure that
disagrees with the results file is worse than no figure.
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULTS = REPO / "benchmark" / "results"
OUT = HERE

# --- typography -----------------------------------------------------------
# Liberation Serif is metrically identical to Times New Roman and is a
# TrueType face, so matplotlib embeds it cleanly. TeX Gyre Termes (what the
# body text uses) is CFF/OpenType: matplotlib mis-declares it on embedding
# and poppler reports "mismatch between font type and embedded font file",
# so it is deliberately not used here. Same Times metrics either way.
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "Nimbus Roman",
                   "DejaVu Serif"],
    "font.monospace": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "custom",
    "mathtext.rm": "Liberation Serif",
    "mathtext.it": "Liberation Serif:italic",
    "mathtext.bf": "Liberation Serif:bold",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
})

# --- palette (arm-coded, colourblind-safe) --------------------------------
C = {
    "naive":   "#1f6fb4",   # blue   -- one shot, hosted
    "agentic": "#c1483a",   # red    -- tool-using
    "local":   "#2e8b57",   # green  -- on-device
    "ref":     "#8a8a8a",
    "accent":  "#d98c00",
    "ink":     "#222222",
    "box":     "#f4f4f4",
}


# Question-set fingerprints. A results file scored against a superseded
# wording carries a different one; the harness records it precisely so a
# stale run cannot be averaged in by accident. The figures enforce the same
# check, because a stale file is exactly the kind of error that produces a
# confident, wrong chart. (This caught local-qwen3.5-9b.json, a 26-question
# first-wave run sitting next to the current local-qwen35-9b.json.)
FINGERPRINT = {
    "car_rental":     "86e194123bb3",
    "adventureworks": "5398f281a907",
    "bird_dev":       "e700eb224701",
    "bird_dev_dict":  "e700eb224701",
}


def load(rel: str, *, strict: bool = True) -> dict | None:
    p = RESULTS / rel
    if not p.exists():
        raise FileNotFoundError(f"no results file: {p}")
    run = json.loads(p.read_text())
    if strict:
        want = FINGERPRINT.get(run.get("dataset", "car_rental"))
        got = run.get("questions_fingerprint")
        if want and got != want:
            raise ValueError(
                f"{rel}: stale question set (fingerprint {got!r}, "
                f"current {want!r}). Refusing to plot it.")
    return run


def acc(run: dict) -> float:
    return 100.0 * run["summary"]["execution_accuracy"]


def n_scored(run: dict) -> int:
    return run["summary"]["n_scored"]


def save(fig, name: str) -> None:
    for ext in ("pdf",):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote {name}.pdf")
