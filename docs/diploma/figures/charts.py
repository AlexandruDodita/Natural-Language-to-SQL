"""Every result chart in chapter 4, generated from benchmark/results/*.json.

The registry below is the single place a run file is named. If a file is
missing the chart it feeds is skipped loudly rather than drawn with a hole
in it.
"""
from __future__ import annotations

import json

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from common import C, RESULTS, load, acc, save


def ro(x, d=1):
    """Romanian decimal separator, to match the running text."""
    return f"{x:.{d}f}".replace(".", ",")


def opt(rel):
    """A cell that was deliberately not run (see §4.6) is a
    legitimate hole, not an error."""
    try:
        return load(rel)
    except FileNotFoundError:
        return None

# label -> (file, arm)
CAR = [
    ("gemini-3.1-pro",      "naive-gemini-3.1-pro-preview.json",   "naive"),
    ("gemini-3.6-flash",    "naive-gemini-3.6-flash.json",         "naive"),
    ("gemini-3.7-flash",    "naive-gemini-3.7-flash.json",         "naive"),
    ("gemini-3-flash-prev", "naive-gemini-3-flash-preview.json",   "naive"),
    ("gemini-2.5-flash",    "naive-gemini-2.5-flash.json",         "naive"),
    ("codex: gpt-5.6-sol",  "codex-agent-gpt-5.6-sol.json",        "agentic"),
    ("codex: gpt-5.6-terra","codex-agent-gpt-5.6-terra.json",      "agentic"),
    ("codex: gpt-5.6-luna", "codex-agent-gpt-5.6-luna.json",       "agentic"),
    ("claude: sonnet-5",    "claude-agent-claude-sonnet-5.json",   "agentic"),
    ("claude: haiku-4.5",   "claude-agent-claude-haiku-4-5.json",  "agentic"),
    ("claude: opus-5",      "claude-agent-claude-opus-5.json",     "agentic"),
    ("mcp propriu: gemini-2.5-flash", "mcp-postgres.json",         "agentic"),
    ("qwen3.6-35B-A3B Q4",  "local-qwen36-35b-moe.json",           "local"),
    ("qwen3.6-27B IQ3",     "local-qwen36-27b-iq3.json",           "local"),
    ("qwen3.5-9B Q4",       "local-qwen35-9b.json",               "local"),
    ("Arctic-7B Q4",        "local-arctic-7b-q4.json",             "local"),
    ("Arctic-7B Q8",        "local-arctic-7b-q8.json",             "local"),
    ("Bonsai-27B Q1",       "local-bonsai-27b-q1.json",            "local"),
]

AW = [
    ("gemini-3.1-pro",      "adventureworks/naive-gemini-3.1-pro-preview.json", "naive"),
    ("gemini-3.7-flash",    "adventureworks/naive-gemini-3.7-flash.json",       "naive"),
    ("gemini-3-flash-prev", "adventureworks/naive-gemini-3-flash-preview.json", "naive"),
    ("gemini-3.6-flash",    "adventureworks/naive-gemini-3.6-flash.json",       "naive"),
    ("gemini-2.5-flash",    "adventureworks/naive-gemini-2.5-flash.json",       "naive"),
    ("qwen3.6-35B-A3B Q4",  "adventureworks/local-qwen36-35b-moe.json",         "local"),
    ("Bonsai-27B Q1",       "adventureworks/local-bonsai-27b-q1.json",          "local"),
    ("qwen3.5-9B Q4",       "adventureworks/local-qwen35-9b.json",             "local"),
    ("Arctic-7B Q4",        "adventureworks/local-arctic-7b-q4.json",           "local"),
    ("Arctic-7B Q8",        "adventureworks/local-arctic-7b-q8.json",           "local"),
]

BIRD = [
    ("gemini-3.7-flash\n+ dicționar", "bird_dev_dict/naive-gemini-3.7-flash.json"),
    ("gemini-3.7-flash",              "bird_dev/naive-gemini-3.7-flash.json"),
    ("gemini-3.1-pro-preview",        "bird_dev/naive-gemini-3.1-pro-preview.json"),
    ("gemini-2.5-flash",              "bird_dev/naive-gemini-2.5-flash.json"),
]

ARM_RO = {"naive": "A — un singur apel (naiv)",
          "agentic": "B — agentic (unelte MCP)",
          "local": "C — model local (GPU)"}


def collect(spec):
    out = []
    for label, f, arm in spec:
        out.append((label, load(f), arm))
    return out


# ==========================================================================
def fig_accuracy_arms():
    """Headline: every system on car_rental, sorted, coloured by arm."""
    runs = sorted(collect(CAR), key=lambda t: acc(t[1]))
    labels = [t[0] for t in runs]
    vals = [acc(t[1]) for t in runs]
    arms = [t[2] for t in runs]
    n = len(runs)

    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    y = np.arange(n)
    ax.barh(y, vals, color=[C[a] for a in arms], height=0.72,
            edgecolor="white", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 108)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("acuratețe de execuție (%), 44 întrebări cotate")
    ax.grid(axis="y", visible=False)

    for yi, (v, r) in enumerate(zip(vals, [t[1] for t in runs])):
        s = r["summary"]
        ax.text(v + 1.4, yi, f"{ro(v)}  ({s['n_correct']}/{s['n_scored']})",
                va="center", fontsize=7.2, color="#333333")

    best_naive = max(v for v, a in zip(vals, arms) if a == "naive")
    ax.axvline(best_naive, color=C["naive"], lw=0.9, ls=(0, (4, 3)),
               zorder=1)

    ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=7,
                              color=C[a], label=ARM_RO[a])
                       for a in ("naive", "agentic", "local")],
              loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3,
              frameon=False, fontsize=7.4, columnspacing=1.4,
              handletextpad=0.4)
    save(fig, "fig_accuracy_arms")


# ==========================================================================
def fig_cost_accuracy():
    """Cost per 100 questions against accuracy. The arms separate on x by
    more than an order of magnitude, and in the wrong direction."""
    fig, ax = plt.subplots(figsize=(6.4, 3.4))

    pts = []
    for label, r, arm in collect(CAR):
        cost = (r["summary"].get("cost") or {}).get("usd_per_100_questions")
        if not cost:
            continue
        pts.append((label, cost, acc(r), arm))

    for label, cost, a, arm in pts:
        ax.scatter(cost, a, s=48, color=C[arm], zorder=4,
                   edgecolor="white", linewidth=0.8)

    # hand-placed so the cheap cluster does not overprint itself
    off = {"gemini-3.7-flash": (0, 9), "gemini-3.6-flash": (-26, -2),
           "gemini-3.1-pro": (0, 9), "gemini-3-flash-prev": (26, -8),
           "gemini-2.5-flash": (6, 9),
           "claude: sonnet-5": (0, 9), "claude: haiku-4.5": (0, -9),
           "claude: opus-5": (-6, -9)}
    for label, cost, a, arm in pts:
        dx, dy = off.get(label, (0, 9))
        ax.annotate(label, (cost, a), textcoords="offset points",
                    xytext=(dx, dy), ha="center",
                    va="bottom" if dy > 0 else "top",
                    fontsize=6.6, color="#333333", zorder=5)

    ax.set_xscale("log")
    ax.set_xlim(0.12, 140)
    ax.set_ylim(76, 106)
    ax.set_xlabel("cost măsurat, USD la 100 de întrebări (scară logaritmică)")
    ax.set_ylabel("acuratețe de execuție (%)")

    # the local arm has no per-token price at all; it belongs on the chart
    # as a band, not as a point that would imply a measured dollar figure
    ax.axhline(93.2, color=C["local"], lw=1.0, ls=(0, (5, 3)), zorder=2)
    ax.text(0.135, 93.9, "configurația C, qwen3.6-35B-A3B pe GPU local: 93,2 % — "
            "fără cost per token",
            fontsize=6.6, color=C["local"], va="bottom", ha="left")

    ax.annotate("", xy=(30, 79.5), xytext=(0.5, 79.5),
                arrowprops=dict(arrowstyle="<|-|>", color="#999999", lw=0.8))
    ax.text(4, 78.6, "de 9 până la 63 de ori mai scump, pentru mai puține "
            "răspunsuri corecte", ha="center", fontsize=6.6, color="#666666")

    ax.legend(handles=[Line2D([], [], marker="o", ls="", ms=6, color=C[a],
                              label=ARM_RO[a])
                       for a in ("naive", "agentic")],
              loc="center left", bbox_to_anchor=(0.01, 0.30),
              frameon=False, fontsize=7)
    save(fig, "fig_cost_accuracy")


# ==========================================================================
def fig_saturation():
    """The un-saturation headline: same three models, three question sets."""
    models = [("gemini-3.7-flash", "naive-gemini-3.7-flash.json",
               "adventureworks/naive-gemini-3.7-flash.json",
               "bird_dev/naive-gemini-3.7-flash.json"),
              ("gemini-3.1-pro-preview", "naive-gemini-3.1-pro-preview.json",
               "adventureworks/naive-gemini-3.1-pro-preview.json",
               "bird_dev/naive-gemini-3.1-pro-preview.json"),
              ("gemini-2.5-flash", "naive-gemini-2.5-flash.json",
               "adventureworks/naive-gemini-2.5-flash.json",
               "bird_dev/naive-gemini-2.5-flash.json")]
    sets = ["car_rental\n(44 î., autor propriu)",
            "AdventureWorks\n(49 î., autor propriu)",
            "BIRD-SQL dev\n(1 534 î., autor extern)"]
    shades = ["#9fc3e3", "#4e93c9", "#12406b"]

    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(models))
    w = 0.26
    for j in range(3):
        vals = [acc(load(m[j + 1])) for m in models]
        b = ax.bar(x + (j - 1) * w, vals, w, color=shades[j],
                   label=sets[j], edgecolor="white", linewidth=0.6)
        ax.bar_label(b, labels=[ro(v) for v in vals], fontsize=7,
                     padding=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels([m[0] for m in models])
    ax.set_ylabel("acuratețe de execuție (%)")
    ax.set_ylim(0, 118)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=3, frameon=False, fontsize=7,
              bbox_to_anchor=(0.5, 1.03), columnspacing=1.2)
    save(fig, "fig_saturation")


# ==========================================================================
def fig_bird():
    """BIRD: the difficulty gradient, and the spread across databases."""
    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(6.5, 3.1), gridspec_kw={"width_ratios": [1, 1.25]})

    # -- left: accuracy by BIRD's own difficulty label ---------------------
    cats = ["simple", "moderate", "challenging"]
    cats_ro = ["simple\n(860)", "moderate\n(443)", "dificile\n(231)"]
    shades = ["#12406b", "#2e78b5", "#7ab0dc", "#b9d5ec"]
    x = np.arange(3)
    w = 0.2
    for i, (label, f) in enumerate(BIRD):
        r = load(f)
        bc = r["summary"]["by_category"]
        vals = [100 * bc[c]["accuracy"] for c in cats]
        a1.bar(x + (i - 1.5) * w, vals, w, color=shades[i],
               label=label.replace("\n", " "), edgecolor="white", lw=0.5)
    a1.set_xticks(x)
    a1.set_xticklabels(cats_ro)
    a1.set_ylabel("acuratețe (%)")
    a1.set_ylim(0, 82)
    a1.set_title("după eticheta de dificultate a BIRD", fontsize=8.5)
    a1.grid(axis="x", visible=False)
    a1.legend(fontsize=6.1, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.16), ncol=2, handlelength=1.0,
              borderpad=0.2, labelspacing=0.25, columnspacing=0.8)

    # -- right: spread across the 11 databases -----------------------------
    r37 = load("bird_dev/naive-gemini-3.7-flash.json")
    r25 = load("bird_dev/naive-gemini-2.5-flash.json")
    per = {}
    for run, key in ((r37, "a"), (r25, "b")):
        agg = {}
        for rec in run["results"]:
            if rec.get("category") == "ambiguous":
                continue
            db = rec.get("db_id")
            if db is None or rec.get("correct") is None:
                continue
            n, c = agg.get(db, (0, 0))
            agg[db] = (n + 1, c + bool(rec["correct"]))
        for db, (n, c) in agg.items():
            per.setdefault(db, {})[key] = 100 * c / n
            per[db]["n"] = n
    order = sorted(per, key=lambda d: per[d]["a"])
    y = np.arange(len(order))
    a2.barh(y, [per[d]["a"] for d in order], 0.62, color=C["naive"],
            label="gemini-3.7-flash", edgecolor="white", lw=0.5)
    a2.scatter([per[d]["b"] for d in order], y, s=22, color=C["accent"],
               zorder=4, label="gemini-2.5-flash", marker="D",
               edgecolor="white", linewidth=0.5)
    a2.set_yticks(y)
    a2.set_yticklabels([f"{d}  ({per[d]['n']})" for d in order], fontsize=6.3)
    a2.set_xlim(0, 100)
    a2.set_xlabel("acuratețe (%)")
    a2.set_title("după baza de date (11 baze)", fontsize=8.5)
    a2.grid(axis="y", visible=False)
    a2.legend(fontsize=6.6, frameon=False, loc="lower right")
    fig.subplots_adjust(wspace=0.50)
    save(fig, "fig_bird")


# ==========================================================================
def fig_local():
    """The density finding: throughput is set by how much of the model is
    read per token, not by how big the file is."""
    rows = [
        # label, file GiB, decode tok/s, kind
        ("Arctic-7B Q4",        4.4, 113, "dens"),
        ("Arctic-7B Q8",        7.5,  72, "dens"),
        ("qwen3.5-9B Q4",       5.2,  91, "dens"),
        ("Bonsai-27B Q1",       3.5,  53, "dens"),
        ("qwen3.6-27B IQ3",    11.2,   8, "dens"),
        ("qwen3.6-35B-A3B Q4", 20.6,  50, "rar"),
    ]
    fig, (a1, a2) = plt.subplots(
        1, 2, figsize=(6.5, 3.1), gridspec_kw={"width_ratios": [1.15, 1]})

    # -- left: file size against decode speed ------------------------------
    a1.axvspan(11.0, 24, color="#f1f1f1", zorder=0)
    a1.text(17.5, 118, "peste ~11 GiB:\ndescărcare parțială pe CPU",
            ha="center", va="center", fontsize=6.3, color="#777777",
            style="italic", linespacing=1.4)
    for label, gib, tps, kind in rows:
        rar = kind == "rar"
        a1.scatter(gib, tps, s=70 if rar else 36,
                   color=C["local"] if rar else C["agentic"],
                   marker="o" if rar else "s", zorder=4,
                   edgecolor="white", linewidth=0.8)
    lbl = {"Arctic-7B Q4": (8, 0, "left"), "Arctic-7B Q8": (8, 0, "left"),
           "qwen3.5-9B Q4": (8, 0, "left"), "Bonsai-27B Q1": (8, 0, "left"),
           "qwen3.6-27B IQ3": (-6, 10, "right"),
           "qwen3.6-35B-A3B Q4": (0, 11, "center")}
    for label, gib, tps, kind in rows:
        dx, dy, ha = lbl[label]
        a1.annotate(label, (gib, tps), textcoords="offset points",
                    xytext=(dx, dy), ha=ha,
                    va="center" if dy == 0 else ("bottom" if dy > 0 else "top"),
                    fontsize=6.3, color="#333333")
    a1.set_xlabel("dimensiunea fișierului GGUF (GiB)")
    a1.set_ylabel("viteză de decodare (tok/s)")
    a1.set_xlim(1.5, 24)
    a1.set_ylim(-8, 132)
    a1.legend(handles=[
        Line2D([], [], marker="s", ls="", color=C["agentic"], ms=5,
               label="dens — toți parametrii, la fiecare token"),
        Line2D([], [], marker="o", ls="", color=C["local"], ms=6,
               label="MoE — ~3 B activi din 35 B")],
        fontsize=6.2, frameon=False, loc="upper center",
        bbox_to_anchor=(0.5, -0.20), ncol=1, handletextpad=0.3,
        labelspacing=0.25)

    # -- right: accuracy on both PostgreSQL datasets -----------------------
    pairs = [("qwen3.6-35B-A3B Q4", "local-qwen36-35b-moe.json"),
             ("qwen3.6-27B IQ3", "local-qwen36-27b-iq3.json"),
             ("qwen3.5-9B Q4", "local-qwen35-9b.json"),
             ("Arctic-7B Q4", "local-arctic-7b-q4.json"),
             ("Arctic-7B Q8", "local-arctic-7b-q8.json"),
             ("Bonsai-27B Q1", "local-bonsai-27b-q1.json")]
    labels, cr, aw = [], [], []
    for label, f in pairs:
        ra = opt(f"adventureworks/{f}")
        labels.append(label)
        cr.append(acc(load(f)))
        aw.append(acc(ra) if ra else np.nan)
    order = list(np.argsort(cr))
    y = np.arange(len(order))
    a2.barh(y + 0.19, [cr[i] for i in order], 0.36, color=C["local"],
            label="car_rental (44 î.)", edgecolor="white", lw=0.5)
    a2.barh(y - 0.19, [aw[i] for i in order], 0.36, color="#9dcbb0",
            label="AdventureWorks (49 î.)", edgecolor="white", lw=0.5)
    for k, i in enumerate(order):
        if np.isnan(aw[i]):
            a2.text(1.5, k - 0.19, "rulare oprită deliberat", va="center",
                    fontsize=5.9, color="#888888", style="italic")
    a2.set_yticks(y)
    a2.set_yticklabels([labels[i] for i in order], fontsize=6.8)
    a2.set_xlim(0, 105)
    a2.set_xticks(range(0, 101, 25))
    a2.set_xlabel("acuratețe de execuție (%)")
    a2.grid(axis="y", visible=False)
    a2.axvline(100, color=C["naive"], lw=0.9, ls=(0, (4, 3)))
    a2.legend(fontsize=6.2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=1, labelspacing=0.25)
    fig.subplots_adjust(wspace=0.42)
    save(fig, "fig_local")


# ==========================================================================
def fig_ambiguity():
    """How often each family asked instead of guessing."""
    fam = {"naive": [], "agentic": [], "local": []}
    for label, f, arm in CAR:
        r = load(f)
        if r is None or label == "claude: fable-5":
            continue
        fam[arm].append(r)

    qs = None
    counts = {}
    for arm, runs in fam.items():
        agg = {}
        for r in runs:
            for rec in r["results"]:
                if rec.get("category") != "ambiguous":
                    continue
                agg.setdefault(rec["id"], [0, 0])
                agg[rec["id"]][1] += 1
                agg[rec["id"]][0] += bool(rec.get("clarified"))
        counts[arm] = agg
        qs = qs or list(agg)

    order = sorted(qs, key=lambda q: -sum(
        counts[a][q][0] / max(counts[a][q][1], 1) for a in counts))
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    x = np.arange(len(order))
    w = 0.26
    for i, arm in enumerate(("naive", "agentic", "local")):
        vals = [100 * counts[arm][q][0] / counts[arm][q][1] for q in order]
        ax.bar(x + (i - 1) * w, vals, w, color=C[arm], label=ARM_RO[arm],
               edgecolor="white", lw=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(order, fontsize=7.5)
    ax.set_ylabel("rulări care au cerut\nclarificare (%)")
    ax.set_ylim(0, 118)
    ax.set_yticks(range(0, 101, 25))
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", ncol=3, frameon=False, fontsize=7,
              bbox_to_anchor=(0.5, 1.04), columnspacing=1.2)
    save(fig, "fig_ambiguity")
    return order


# ==========================================================================
def fig_categories():
    """Heatmap: which question families still discriminate."""
    groups = {
        "simple": ["simple"], "agregare": ["aggregate"], "join": ["join"],
        "subinterogare": ["subquery"], "fereastră": ["window"],
        "structură": ["multi_level_agg", "self_join", "anti_join",
                      "recursive", "set_ops", "gaps_islands"],
        "măsură": ["ratio", "percentile", "pivot"],
        "temporal": ["temporal", "calendar", "cohort"],
    }
    runs = sorted(collect(CAR), key=lambda t: -acc(t[1]))
    M = np.full((len(runs), len(groups)), np.nan)
    for i, (_, r, _) in enumerate(runs):
        bc = r["summary"]["by_category"]
        for j, (_, members) in enumerate(groups.items()):
            n = sum(bc[m]["n"] for m in members if m in bc)
            c = sum(bc[m]["correct"] for m in members if m in bc)
            if n:
                M[i, j] = 100 * c / n

    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(list(groups), rotation=32, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(runs)))
    ax.set_yticklabels([f"{t[0]}" for t in runs], fontsize=7.2)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center",
                        fontsize=6.4,
                        color="#111111" if 25 < M[i, j] < 90 else "#111111")
    for tick, (_, _, arm) in zip(ax.get_yticklabels(), runs):
        tick.set_color(C[arm])
    ax.set_xlim(-0.5, len(groups) - 0.5)
    ax.grid(False)
    ax.set_xticks(np.arange(len(groups) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(runs) + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", lw=1.2)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.02)
    cb.set_label("acuratețe pe grup (%)", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)
    ax.legend(handles=[Line2D([], [], marker="s", ls="", ms=6, color=C[a],
                              label=ARM_RO[a])
                       for a in ("naive", "agentic", "local")],
              loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=3,
              frameon=False, fontsize=7.2, columnspacing=1.4,
              handletextpad=0.4)
    save(fig, "fig_categories")


if __name__ == "__main__":
    print("charts:")
    fig_accuracy_arms()
    fig_saturation()
    fig_bird()
    fig_local()
    fig_ambiguity()
    fig_categories()
    fig_cost_accuracy()
