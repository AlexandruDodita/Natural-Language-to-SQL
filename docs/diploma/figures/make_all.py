"""Regenerates every figure and every table body used by lucrare.tex.

    python docs/diploma/figures/make_all.py

Run this after any benchmark re-run; the .tex file inputs the results, so
nothing has to be retyped.
"""
import diagrams
import charts
import tables

if __name__ == "__main__":
    print("diagrams:")
    diagrams.fig_harness()
    diagrams.fig_arm_rag()
    diagrams.fig_arm_mcp()
    print("charts:")
    charts.fig_accuracy_arms()
    charts.fig_saturation()
    charts.fig_bird()
    charts.fig_local()
    charts.fig_ambiguity()
    charts.fig_categories()
    charts.fig_cost_accuracy()
    print("tables:")
    tables.tab_naive()
    tables.tab_agentic()
    tables.tab_local_perf()
    tables.tab_local_acc()
    tables.tab_bird()
    tables.tab_bird_db()
    tables.tab_ambiguity()
    tables.tab_categories_summary()
    print("done.")
