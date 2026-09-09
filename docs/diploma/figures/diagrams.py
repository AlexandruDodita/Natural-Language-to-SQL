"""The three block diagrams: the measurement harness, the RAG arm, the MCP arm.

Drawn with matplotlib patches rather than TikZ so the whole figure set is
produced by one command and stays in step with the code it describes.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from common import C, save


def rect(ax, x, y, w, h, *, fc="#ffffff", ec=C["ink"], lw=1.0, ls="-", z=2):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.010",
        facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=z,
        mutation_aspect=ax.figure.get_figwidth() / ax.figure.get_figheight()))


def box(ax, x, y, w, h, title=None, body=None, *, fc="#ffffff",
        ec=C["ink"], lw=1.0, tfs=8.2, bfs=7.3, tmono=False, z=2):
    """One block: bold title line, optional smaller body underneath."""
    rect(ax, x, y, w, h, fc=fc, ec=ec, lw=lw, z=z)
    cx = x + w / 2
    if title and body:
        # Convert point sizes to axes fractions so the title never lands on
        # the first body line, whatever the figure height is.
        figh = ax.figure.get_figheight() * 72.0
        nb = body.count("\n") + 1
        th = tfs * 1.55 / figh
        lh = bfs * 1.45 / figh
        bh = nb * lh
        gap = 0.35 * lh
        top = y + h / 2 + (th + gap + bh) / 2
        ax.text(cx, top - th / 2, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", zorder=z + 1,
                **({"fontfamily": "monospace"} if tmono else {}))
        ax.text(cx, top - th - gap - bh / 2, body, ha="center", va="center",
                fontsize=bfs, zorder=z + 1, linespacing=1.45, color="#333333")
    else:
        t = title or body
        ax.text(cx, y + h / 2, t, ha="center", va="center",
                fontsize=tfs if title else bfs,
                fontweight="bold" if title else "normal", zorder=z + 1,
                linespacing=1.45,
                **({"fontfamily": "monospace"} if tmono else {}))


def arrow(ax, p0, p1, *, ec=C["ink"], lw=1.0, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=9, color=ec, linewidth=lw,
        linestyle=ls, zorder=5, connectionstyle=f"arc3,rad={rad}",
        shrinkA=1.0, shrinkB=1.0))


def note(ax, x, y, text, *, fs=7.0, color=C["ink"], ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color,
            zorder=6, linespacing=1.4,
            bbox=dict(fc="white", ec="none", pad=1.0))


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.grid(False)
    return fig, ax


# ==========================================================================
# 1. The measurement harness
# ==========================================================================
def fig_harness():
    fig, ax = canvas(6.5, 4.6)

    box(ax, 0.015, 0.815, 0.225, 0.135, "Set de întrebări",
        "questions.yaml / .json\namprentă SHA-256",
        fc="#eef4fa", ec=C["naive"], tfs=8.0, bfs=6.9)
    box(ax, 0.015, 0.645, 0.225, 0.105, "Schema bazei", "DDL, text simplu",
        fc="#eef4fa", ec=C["naive"], tfs=8.0, bfs=6.9)

    box(ax, 0.315, 0.645, 0.245, 0.305, "run.py",
        "bucla de evaluare\n\n• verifică amprenta\n• punct de salvare / 50 q\n"
        "• un apel per întrebare",
        fc="#fbfbfb", lw=1.4, tfs=9.5, bfs=7.0, tmono=True)

    ax.text(0.815, 0.975, "REGISTRUL DE CONFIGURAȚII", ha="center", va="center",
            fontsize=7.2, fontweight="bold", color="#555555")
    rect(ax, 0.635, 0.640, 0.360, 0.310, fc="#fcfcfc", ec="#cccccc",
         lw=0.8, ls=(0, (3, 2)), z=1)
    box(ax, 0.652, 0.845, 0.326, 0.085, None,
        "A.  naive — schemă integrală, un apel",
        fc="#eef4fa", ec=C["naive"], bfs=7.4)
    box(ax, 0.652, 0.745, 0.326, 0.085, None,
        "B.  agentic — explorare prin unelte",
        fc="#fbeeec", ec=C["agentic"], bfs=7.4)
    box(ax, 0.652, 0.655, 0.326, 0.085, None,
        "C.  local — identic cu A, model local",
        fc="#eaf5ee", ec=C["local"], bfs=7.4)

    arrow(ax, (0.240, 0.880), (0.315, 0.840))
    arrow(ax, (0.240, 0.697), (0.315, 0.730))
    arrow(ax, (0.560, 0.820), (0.635, 0.820))
    note(ax, 0.597, 0.848, "întrebare", fs=6.6)
    arrow(ax, (0.815, 0.640), (0.815, 0.520))
    note(ax, 0.838, 0.580, "SQL prezis", fs=6.9, ha="left")

    rect(ax, 0.315, 0.335, 0.680, 0.185, fc="#fbfbfb", lw=1.4)
    ax.text(0.655, 0.487, "Executorul — singurul loc în care se execută SQL",
            ha="center", va="center", fontsize=8.4, fontweight="bold",
            zorder=3)
    box(ax, 0.335, 0.355, 0.310, 0.100, "PostgresFixture",
        "read-only · timeout 15 s", tfs=7.6, bfs=6.9, tmono=True,
        fc="#f7f7f7")
    box(ax, 0.665, 0.355, 0.310, 0.100, "SqliteFixture",
        "11 fișiere · progress handler", tfs=7.6, bfs=6.9, tmono=True,
        fc="#f7f7f7")

    box(ax, 0.015, 0.370, 0.225, 0.105, "SQL de referință", "(gold)",
        fc="#f2f2f2", ec=C["ref"], tfs=8.0, bfs=6.9)
    arrow(ax, (0.240, 0.423), (0.315, 0.423))

    box(ax, 0.245, 0.110, 0.435, 0.160, "score.py",
        "acuratețe de execuție: compară\nSETURILE DE REZULTATE, nu textul SQL\n"
        "multiset · numele coloanelor ignorate",
        fc="#fff8e8", ec=C["accent"], lw=1.3, tfs=9.0, bfs=7.0, tmono=True)
    arrow(ax, (0.463, 0.335), (0.463, 0.270))
    note(ax, 0.560, 0.303, "ambele seturi de rânduri", fs=6.6)

    box(ax, 0.720, 0.110, 0.275, 0.160, "results/*.json",
        "per întrebare: SQL,\nlatență, tokeni, cost",
        fc="#f2f2f2", ec=C["ref"], tfs=8.0, bfs=6.9, tmono=True)
    arrow(ax, (0.680, 0.190), (0.720, 0.190))

    ax.text(0.5, 0.035,
            "Singura variabilă care diferă între configurațiile A și C este modelul "
            "care răspunde:\nprompt, contract de ieșire și mediu de execuție sunt "
            "identice.",
            ha="center", va="center", fontsize=7.2, style="italic",
            color="#555555", linespacing=1.45)
    save(fig, "fig_harness")


# ==========================================================================
# 2. The RAG arm (the project's own pipeline)
# ==========================================================================
def fig_arm_rag():
    fig, ax = canvas(6.5, 3.35)

    y, h, w = 0.615, 0.205, 0.180
    xs = [0.012, 0.207, 0.402, 0.597, 0.792]

    box(ax, xs[0], y, w, h, "Întrebare", "limbaj natural\n(ro / en)",
        fc="#f2f2f2", ec=C["ref"], tfs=8.2, bfs=7.0)
    box(ax, xs[1], y, w, h, "Recuperare",
        "SchemaIndex\nValueIndex\nexpansiune FK",
        fc="#eef4fa", ec=C["naive"], tfs=8.2, bfs=7.0)
    box(ax, xs[2], y, w, h, "Prompt", "doar tabelele\nselectate",
        fc="#eef4fa", ec=C["naive"], tfs=8.2, bfs=7.0)
    box(ax, xs[3], y, w, h, "LLM", "generare SQL",
        fc="#eef4fa", ec=C["naive"], tfs=8.2, bfs=7.0)
    box(ax, xs[4], y, w, h, "Validator",
        "AST: doar SELECT\nfuncții interzise\nschema pg_ blocată",
        fc="#fff8e8", ec=C["accent"], tfs=8.2, bfs=7.0)

    for i in range(4):
        arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))

    arrow(ax, (xs[4] + w * 0.35, y), (xs[3] + w * 0.65, y), rad=-0.6,
          ec=C["agentic"], ls=(0, (3, 2)))
    note(ax, 0.792, 0.500, "respins → reîncercare", fs=6.9, color=C["agentic"])

    box(ax, 0.560, 0.245, 0.412, 0.150, "Execuție",
        "utilizator PostgreSQL exclusiv read-only\n"
        "timeout de instrucțiune · plafon de rânduri",
        fc="#eaf5ee", ec=C["local"], tfs=8.2, bfs=7.0)
    arrow(ax, (0.882, 0.540), (0.882, 0.395))

    box(ax, 0.075, 0.245, 0.412, 0.150, "Răspuns",
        "SSE progresiv · panou artifact\nraport Excel, grafic ales de model",
        fc="#f2f2f2", ec=C["ref"], tfs=8.2, bfs=7.0)
    arrow(ax, (0.560, 0.320), (0.487, 0.320))

    ax.text(0.5, 0.085,
            "Configurație măsurată separat de A–C. Rândul său nu apare în capitolul 4; "
            "motivul este dat în secțiunea 4.9.",
            ha="center", va="center", fontsize=7.2, style="italic",
            color="#555555")
    save(fig, "fig_arm_rag")


# ==========================================================================
# 3. The MCP / agentic arm
# ==========================================================================
def fig_arm_mcp():
    fig, ax = canvas(6.5, 3.55)

    box(ax, 0.010, 0.640, 0.180, 0.175, "Întrebare",
        "fără schemă\nîn prompt", fc="#f2f2f2", ec=C["ref"],
        tfs=8.2, bfs=7.2)

    box(ax, 0.238, 0.505, 0.272, 0.375, "Model + harness",
        "claude -p  ·  codex exec\nconfigurația MCP proprie\n\n"
        "buclă autonomă: modelul\ndecide ce unealtă cheamă\n"
        "și când se oprește",
        fc="#fbeeec", ec=C["agentic"], lw=1.4, tfs=8.4, bfs=7.0)

    box(ax, 0.700, 0.505, 0.290, 0.375, "Server MCP", "PostgreSQL"
        "\ntransport stdio\n\nlist_tables()\ndescribe_table(t)\n"
        "get_schema()\nrun_query(sql)",
        fc="#ffffff", ec=C["agentic"], lw=1.2, tfs=8.4, bfs=7.0)

    arrow(ax, (0.190, 0.727), (0.238, 0.727))

    # The two legs of the agent loop, labelled inside the gap between the
    # boxes so nothing is written over a border.
    arrow(ax, (0.510, 0.800), (0.700, 0.800), ec=C["agentic"])
    ax.text(0.605, 0.838, "apel de unealtă", ha="center", va="center",
            fontsize=6.9, color=C["agentic"], zorder=6)
    arrow(ax, (0.700, 0.590), (0.510, 0.590), ec=C["agentic"])
    ax.text(0.605, 0.552, "rânduri / metadate", ha="center", va="center",
            fontsize=6.9, color=C["agentic"], zorder=6)
    ax.text(0.605, 0.695, "de la 2,0 până la\n4,9 ture în medie",
            ha="center", va="center", fontsize=6.9, style="italic",
            color="#666666", linespacing=1.4, zorder=6)

    box(ax, 0.700, 0.300, 0.290, 0.125, "PostgreSQL",
        "rol read-only · plafon de rânduri", fc="#eaf5ee", ec=C["local"],
        tfs=8.2, bfs=6.9)
    arrow(ax, (0.845, 0.505), (0.845, 0.425), style="<|-|>", ec=C["local"])

    box(ax, 0.238, 0.300, 0.272, 0.125, "SQL final",
        "extras din ultimul bloc marcat", fc="#f2f2f2", ec=C["ref"],
        tfs=8.2, bfs=6.9)
    arrow(ax, (0.374, 0.505), (0.374, 0.425))

    ax.text(0.5, 0.135,
            "Costul configurației este dominat de contextul retrimis la fiecare "
            "tură:\n65 000 – 162 000 tokeni de prompt în medie, față de "
            "1 511 pentru configurația A.",
            ha="center", va="center", fontsize=7.4, linespacing=1.5,
            bbox=dict(fc="#fff8e8", ec=C["accent"], lw=0.9,
                      boxstyle="round,pad=0.5"))
    save(fig, "fig_arm_mcp")


if __name__ == "__main__":
    print("diagrams:")
    fig_harness()
    fig_arm_rag()
    fig_arm_mcp()
