"""Emits the LaTeX table bodies for chapter 4 into docs/diploma/tables/.

Same rule as the figures: every cell is read out of benchmark/results/*.json.
The .tex file `\\input`s these, so a re-run of the benchmark propagates into
the thesis without anyone retyping a number.
"""
from __future__ import annotations

import pathlib
import statistics

import numpy as np

from common import RESULTS, load, acc
from charts import CAR, AW, BIRD, opt

OUT = pathlib.Path(__file__).resolve().parents[1] / "tables"
OUT.mkdir(exist_ok=True)

# GGUF file sizes, measured on disk (find ~/models -name '*.gguf' -printf %s).
# A quantisation is part of the measurement, so the exact file is named.
GGUF = {
    "Arctic-7B Q4":        (4.4, "rezident integral", 113, "4 min"),
    "Arctic-7B Q8":        (7.5, "rezident integral",  72, "5 min"),
    "qwen3.5-9B Q4":       (5.2, "rezident integral",  91, "15 min"),
    "Bonsai-27B Q1":       (3.5, "rezident integral",  53, "50 min"),
    "qwen3.6-35B-A3B Q4": (20.6, "experți în RAM",     50, "37 min"),
    "qwen3.6-27B IQ3":    (11.2, "straturi parțiale",   8, "247 min"),
}
VRAM = {"Arctic-7B Q4": 6055, "Arctic-7B Q8": 9067, "qwen3.5-9B Q4": 6702,
        "Bonsai-27B Q1": 6284, "qwen3.6-35B-A3B Q4": 9620,
        "qwen3.6-27B IQ3": 10438}


def w(name: str, body: str, spec: str = None, head: str = None,
      env: str = "tabular") -> None:
    """Write one table. When a column spec is given the whole tabular is
    emitted, because \\input inside an alignment breaks booktabs' \\noalign
    at the file boundary."""
    if spec is None:
        out = body.rstrip()
    else:
        arg = r"{\textwidth}" if env == "tabularx" else ""
        out = (f"\\begin{{{env}}}{arg}{{{spec}}}\n"
               f"\\toprule\n{head}\n\\midrule\n"
               f"{body.rstrip()}\n\\bottomrule\n\\end{{{env}}}")
    (OUT / name).write_text(out + "\n")
    print(f"  wrote tables/{name}")


def n_(x, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "---"
    s = f"{x:,.{d}f}".replace(",", "\\,").replace(".", ",")
    return s


def pc(x, d=1):
    return "---" if x is None else f"{x:.{d}f}".replace(".", ",")


def esc(s: str) -> str:
    return s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


def cat_acc(run, members):
    bc = run["summary"]["by_category"]
    n = sum(bc[m]["n"] for m in members if m in bc)
    c = sum(bc[m]["correct"] for m in members if m in bc)
    return 100 * c / n if n else None


# ======================================================================
def tab_naive():
    """Arm A: the one-shot hosted baseline, both PostgreSQL databases."""
    rows = []
    for label, f, arm in CAR:
        if arm != "naive":
            continue
        r = load(f)
        ra = opt(f"adventureworks/{f}")
        s = r["summary"]
        u, c = s["usage"], s["cost"]
        rows.append((acc(r), (
            f"\\code{{{esc(label)}}} & "
            f"{pc(acc(r))}\\,\\% & "
            f"{pc(acc(ra)) if ra else '---'}\\,\\% & "
            f"{n_(s['latency_ms_median'] / 1000, 1)}\\,s & "
            f"{n_(u['prompt_tokens_mean'], 0)} & "
            f"{n_(u['output_tokens_mean'], 0)} & "
            f"\\${pc(c['usd_per_100_questions'], 2)} \\\\")))
    w("tab_naive.tex", "\n".join(b for _, b in sorted(rows, reverse=True)),
      spec="@{}lrrrrrr@{}",
      head=r" & \multicolumn{2}{c}{\hd{Acuratețe}} & "
           r"\multicolumn{4}{c}{\hd{Măsurat pe car\_rental}} \\"
           "\n" r"\cmidrule(lr){2-3}\cmidrule(l){4-7}" "\n"
           r"\hd{Model} & \hd{car\_rental} & \hd{AdventureWorks} & "
           r"\hd{Latență med.} & \hd{Tok.\ prompt} & \hd{Tok.\ ieșire} & "
           r"\hd{\$/100 î.} \\")


# ======================================================================
def tab_agentic():
    """Arm B: agentic, car_rental only."""
    rows = []
    for label, f, arm in CAR:
        if arm != "agentic":
            continue
        r = load(f)
        s = r["summary"]
        # scored questions only, matching every other population in ch.4
        turns = [(rec.get("extra") or {}).get("turns")
                 or (rec.get("extra") or {}).get("tool_calls")
                 for rec in r["results"] if rec.get("scored")]
        turns = [t for t in turns if t is not None]
        u = s.get("usage") or {}
        c = s.get("cost") or {}
        cost = c.get("usd_per_100_questions_measured")
        # two different reasons for a missing cost: the arm recorded no token
        # usage at all, or the vendor publishes no price for that model
        if cost:
            cost_cell = "\\$" + pc(cost, 2)
        elif not u:
            cost_cell = "nemăsurat"
        else:
            cost_cell = "nepublicat"
        rows.append((acc(r), (
            f"\\code{{{esc(label)}}} & "
            f"{s['n_correct']}/{s['n_scored']} & "
            f"\\textbf{{{pc(acc(r))}\\,\\%}} & "
            f"{n_(statistics.mean(turns), 1) if turns else '---'} & "
            f"{n_(s['latency_ms_median'] / 1000, 1)}\\,s & "
            f"{n_(u.get('prompt_tokens_mean'), 0) if u else 'nemăsurat'} & "
            f"{cost_cell} \\\\")))
    body = "\n".join(b for _, b in sorted(rows, reverse=True))
    ref = load("naive-gemini-3.7-flash.json")
    body += ("\n\\midrule\n"
             "\\emph{referință:} configurația A, cea mai bună & "
             f"{ref['summary']['n_correct']}/{ref['summary']['n_scored']} & "
             f"\\textbf{{{pc(acc(ref))}\\,\\%}} & 0 & "
             f"{n_(ref['summary']['latency_ms_median'] / 1000, 1)}\\,s & "
             f"{n_(ref['summary']['usage']['prompt_tokens_mean'], 0)} & "
             f"\\${pc(ref['summary']['cost']['usd_per_100_questions'], 2)} \\\\")
    w("tab_agentic.tex", body, spec="@{}lrrrrrr@{}",
      head=r"\hd{Sistem} & \hd{Corecte} & \hd{Acuratețe} & "
           r"\hd{Iterații med.} & \hd{Latență med.} & \hd{Tok.\ prompt} & "
           r"\hd{\$/100 î.} \\")


# ======================================================================
def tab_local_perf():
    """Arm C: how each model fits on the card, and what that costs."""
    order = sorted(GGUF, key=lambda k: -GGUF[k][2])
    files = {"Arctic-7B Q4": "local-arctic-7b-q4.json",
             "Arctic-7B Q8": "local-arctic-7b-q8.json",
             "qwen3.5-9B Q4": "local-qwen35-9b.json",
             "Bonsai-27B Q1": "local-bonsai-27b-q1.json",
             "qwen3.6-35B-A3B Q4": "local-qwen36-35b-moe.json",
             "qwen3.6-27B IQ3": "local-qwen36-27b-iq3.json"}
    out = []
    for k in order:
        gib, fit, tps, wall = GGUF[k]
        r = opt(files[k]) if k in files else None
        lat = (f"{n_(r['summary']['latency_ms_median'] / 1000, 1)}\\,s"
               if r else "---")
        em = (lambda x: f"\\textbf{{{x}}}") if k == "qwen3.6-35B-A3B Q4" \
            else (lambda x: str(x))
        vram = f"{VRAM[k]:,}".replace(",", "\\,")
        out.append(f"{em(esc(k))} & {n_(gib)} & {vram} & {fit} & "
                   f"{em(tps)} & {lat} & {wall} \\\\")
    w("tab_local_perf.tex", "\n".join(out), spec="@{}lrrlrrr@{}",
      head=r"\hd{Model} & \hd{GGUF (GiB)} & \hd{VRAM (MiB)} & "
           r"\hd{Cum încape} & \hd{tok/s} & \hd{Latență med.} & "
           r"\hd{Durată, 44 î.} \\")


def tab_local_acc():
    """Arm C accuracy on both databases, with the failure split."""
    files = [("qwen3.6-35B-A3B Q4", "local-qwen36-35b-moe.json"),
             ("qwen3.6-27B IQ3", "local-qwen36-27b-iq3.json"),
             ("qwen3.5-9B Q4", "local-qwen35-9b.json"),
             ("Bonsai-27B Q1", "local-bonsai-27b-q1.json"),
             ("Arctic-7B Q4", "local-arctic-7b-q4.json"),
             ("Arctic-7B Q8", "local-arctic-7b-q8.json")]
    rows = []
    for label, f in files:
        r = load(f)
        ra = opt(f"adventureworks/{f}")
        s = r["summary"]
        # scored population only, as the caption states
        trunc = sum(1 for rec in r["results"] if rec.get("scored")
                    and (rec.get("extra") or {}).get("truncated"))
        rows.append((acc(r), (
            f"\\code{{{esc(label)}}} & "
            f"\\textbf{{{pc(acc(r))}\\,\\%}} ({s['n_correct']}/{s['n_scored']}) & "
            f"{pc(acc(ra)) + '\\,\\% (' + str(ra['summary']['n_correct']) + '/' + str(ra['summary']['n_scored']) + ')' if ra else 'nerulat'} & "
            f"{s['invalid_sql']} & {s['no_sql_produced']} & {trunc} \\\\")))
    w("tab_local_acc.tex",
      "\n".join(b for _, b in sorted(rows, reverse=True)),
      spec="@{}lllrrr@{}",
      head=r" & \multicolumn{2}{c}{\hd{Acuratețe}} & "
           r"\multicolumn{3}{c}{\hd{Eșecuri pe car\_rental}} \\"
           "\n" r"\cmidrule(lr){2-3}\cmidrule(l){4-6}" "\n"
           r"\hd{Model} & \hd{car\_rental} & \hd{AdventureWorks} & "
           r"\hd{SQL inv.} & \hd{fără SQL} & \hd{trunchiat} \\")


# ======================================================================
def tab_bird():
    """BIRD-SQL dev, four runs, 1534 questions each."""
    cats = ["simple", "moderate", "challenging"]
    out = []
    for label, f in BIRD:
        r = load(f)
        s = r["summary"]
        bc = s["by_category"]
        c = s.get("cost") or {}
        lbl = label.replace("\n", " ")
        out.append(
            f"\\code{{{esc(lbl)}}} & "
            f"\\textbf{{{pc(acc(r))}\\,\\%}} & {s['n_correct']}/{s['n_scored']} & "
            + " & ".join(pc(100 * bc[c_]["accuracy"]) + "\\,\\%" for c_ in cats)
            + f" & {s['invalid_sql']} & {s['no_sql_produced']} & "
            f"{n_(s['latency_ms_median'] / 1000, 1)}\\,s & "
            f"\\${pc(c.get('usd_per_100_questions', 0) * 15.34, 2)} \\\\")
    w("tab_bird.tex", "\n".join(out), spec="@{}lrrrrrrrrr@{}",
      head=r"\hd{Rulare} & \hd{Acurat.} & \hd{Corecte} & \hd{simple} & "
           r"\hd{moderate} & \hd{dificile} & \hd{inv.} & \hd{f.\,SQL} & "
           r"\hd{Lat.} & \hd{Cost} \\" "\n"
           r" & & & \hd{(860)} & \hd{(443)} & \hd{(231)} & & & & \\")


def tab_bird_db():
    """Per-database spread inside BIRD."""
    runs = [("3.7-flash", "bird_dev/naive-gemini-3.7-flash.json"),
            ("3.1-pro", "bird_dev/naive-gemini-3.1-pro-preview.json"),
            ("2.5-flash", "bird_dev/naive-gemini-2.5-flash.json")]
    per = {}
    for key, f in runs:
        for rec in load(f)["results"]:
            db = rec.get("db_id")
            if db is None or rec.get("correct") is None:
                continue
            d = per.setdefault(db, {})
            n, c = d.get(key, (0, 0))
            d[key] = (n + 1, c + bool(rec["correct"]))
    order = sorted(per, key=lambda d: -per[d]["3.7-flash"][1] / per[d]["3.7-flash"][0])
    out = []
    for db in order:
        cells = []
        for key, _ in runs:
            n, c = per[db][key]
            cells.append(pc(100 * c / n) + "\\,\\%")
        n = per[db]["3.7-flash"][0]
        out.append(f"\\code{{{esc(db)}}} & {n} & " + " & ".join(cells) + " \\\\")
    w("tab_bird_db.tex", "\n".join(out), spec="@{}lrrrr@{}",
      head=r"\hd{Baza de date} & \hd{Î.} & \hd{3.7-flash} & "
           r"\hd{3.1-pro} & \hd{2.5-flash} \\")


# ======================================================================
def tab_ambiguity():
    """Per-question ask rates, car_rental, by arm family."""
    fam = {"naive": [], "agentic": [], "local": []}
    for label, f, arm in CAR:
        fam[arm].append(load(f))
    texts, agg = {}, {}
    for arm, runs in fam.items():
        for r in runs:
            for rec in r["results"]:
                if rec.get("category") != "ambiguous":
                    continue
                texts[rec["id"]] = rec["question"]
                d = agg.setdefault(rec["id"], {})
                n, c = d.get(arm, (0, 0))
                d[arm] = (n + 1, c + bool(rec.get("clarified")))
    order = sorted(agg, key=lambda q: -sum(
        agg[q][a][1] / agg[q][a][0] for a in agg[q]))
    out = []
    for q in order:
        cells = []
        for arm in ("naive", "agentic", "local"):
            n, c = agg[q][arm]
            cell = f"{c}/{n}"
            if c == 0:
                cell = f"\\textbf{{{cell}}}"
            cells.append(cell)
        t = texts[q]
        t = (t[:52] + "\\dots") if len(t) > 55 else t
        out.append(f"\\code{{{q}}} & \\emph{{„{esc(t)}”}} & "
                   + " & ".join(cells) + " \\\\")
    w("tab_ambiguity.tex", "\n".join(out), env="tabularx",
      spec="@{}llrrr@{}",
      head=r"\hd{Î.} & \hd{Textul întrebării} & \hd{Config. A} & "
           r"\hd{Config. B} & \hd{Config. C} \\")


# ======================================================================
def tab_categories_summary():
    """The two groups that still discriminate, per arm family."""
    groups = {
        "simple": ["simple"], "agregare": ["aggregate"], "join": ["join"],
        "subinterog.": ["subquery"], "fereastră": ["window"],
        "structură": ["multi_level_agg", "self_join", "anti_join",
                      "recursive", "set_ops", "gaps_islands"],
        "măsură": ["ratio", "percentile", "pivot"],
        "temporal": ["temporal", "calendar", "cohort"],
    }
    fam = {"naive": [], "agentic": [], "local": []}
    for label, f, arm in CAR:
        fam[arm].append(load(f))
    names = {"naive": "A --- un singur apel", "agentic": "B --- agentic",
             "local": "C --- local"}
    out = []
    for arm in ("naive", "agentic", "local"):
        cells = []
        for _, members in groups.items():
            n = c = 0
            for r in fam[arm]:
                bc = r["summary"]["by_category"]
                n += sum(bc[m]["n"] for m in members if m in bc)
                c += sum(bc[m]["correct"] for m in members if m in bc)
            cells.append(pc(100 * c / n) if n else "---")
        out.append(f"{names[arm]} & " + " & ".join(cells) + " \\\\")
    w("tab_categories.tex", "\n".join(out), spec="@{}lrrrrrrrr@{}",
      head=r"\hd{Familie} & \hd{simple} & \hd{agreg.} & \hd{join} & "
           r"\hd{subint.} & \hd{fereastră} & \hd{structură} & "
           r"\hd{măsură} & \hd{temporal} \\")


if __name__ == "__main__":
    print("tables:")
    tab_naive()
    tab_agentic()
    tab_local_perf()
    tab_local_acc()
    tab_bird()
    tab_bird_db()
    tab_ambiguity()
    tab_categories_summary()
