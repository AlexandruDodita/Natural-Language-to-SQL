from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "presentation" / "Sistem_text_to_SQL_Dodita_Alexandru.pptx"
ASSETS = ROOT / "docs" / "presentation" / "assets"
SCREENSHOTS = ROOT / "docs" / "screenshots"

W, H = 13.333, 7.5
NAVY = "102A43"
NAVY_2 = "173F5F"
BLUE = "1F6FB4"
BLUE_LIGHT = "E8F2FA"
CORAL = "C1483A"
CORAL_LIGHT = "FAECE9"
GREEN = "2E8B57"
GREEN_LIGHT = "E8F5EE"
CREAM = "F7F5EF"
WHITE = "FFFFFF"
INK = "17212B"
MUTED = "647487"
LINE = "D6DEE6"
GOLD = "E1A83B"


def rgb(hex_color):
    return RGBColor.from_string(hex_color)


prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
blank = prs.slide_layouts[6]


def set_bg(slide, color=CREAM):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def add_text(slide, text, x, y, w, h, size=24, color=INK, bold=False,
             font="Aptos", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP,
             margin=0.03, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color)
    return box


def add_rich_text(slide, runs, x, y, w, h, size=24, color=INK,
                  align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.03)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    for text_value, opts in runs:
        run = p.add_run()
        run.text = text_value
        run.font.name = opts.get("font", "Aptos")
        run.font.size = Pt(opts.get("size", size))
        run.font.bold = opts.get("bold", False)
        run.font.italic = opts.get("italic", False)
        run.font.color.rgb = rgb(opts.get("color", color))
    return box


def shape(slide, kind, x, y, w, h, fill=WHITE, line=LINE, radius=True):
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    shp.line.color.rgb = rgb(line)
    shp.line.width = Pt(1)
    return shp


CORNER = 0.14   # inch — one corner radius for every rounded box in the deck


def rounded(slide, x, y, w, h, fill=WHITE, line=LINE, radius=CORNER):
    """A rounded rectangle whose corner radius is a fixed length.

    PowerPoint expresses the radius as a fraction of min(width, height), so
    with the default adjustment every box curves by a different amount and a
    tall narrow card ends up almost a lozenge. Pinning it to a length keeps
    the deck on one curve, and — the reason this exists — gives the accent
    bars and picture frames below a radius they can inset against.
    """
    shp = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, line)
    shp.adjustments[0] = min(radius / min(w, h), 0.5)
    return shp


def pill(slide, text, x, y, w, fill=BLUE_LIGHT, color=BLUE):
    s = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.34, fill, fill)
    s.adjustments[0] = 0.5
    add_text(slide, text.upper(), x, y + 0.01, w, 0.28, 10, color, True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def title(slide, text, kicker=None, dark=False):
    fg = WHITE if dark else NAVY
    if kicker:
        add_text(slide, kicker.upper(), 0.68, 0.38, 5.0, 0.24, 10,
                 GOLD if dark else BLUE, True)
    add_text(slide, text, 0.68, 0.70 if kicker else 0.48, 11.8, 0.95,
             30, fg, True)


def footer(slide, source=None, dark=False):
    # Numbered from the deck itself: hard-coded numbers silently desync the
    # moment a slide is inserted.
    number = len(prs.slides)
    color = "A8B6C4" if dark else MUTED
    if source:
        add_text(slide, source, 0.68, 7.13, 10.8, 0.18, 8.5, color)
    add_text(slide, f"{number:02d}", 12.25, 7.08, 0.4, 0.22, 9, color,
             True, align=PP_ALIGN.RIGHT)


def add_notes(slide, text):
    tf = slide.notes_slide.notes_text_frame
    tf.text = text.strip()


def add_picture_contain(slide, path, x, y, w, h, border=False):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    if border:
        rounded(slide, x, y, w, h, WHITE, LINE)
        # A "contain" fit touches the frame on one axis, and a square-cornered
        # PNG that touches a rounded frame overhangs it at all four corners.
        # Pad by the radius so the picture never reaches the arc.
        x, y = x + CORNER, y + CORNER
        w, h = w - 2 * CORNER, h - 2 * CORNER
    ratio = min(w / iw, h / ih)
    pw, ph = iw * ratio, ih * ratio
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    return slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))


def arrow(slide, x, y, w, color=BLUE):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(0.32))
    s.fill.solid(); s.fill.fore_color.rgb = rgb(color)
    s.line.fill.background()
    return s


def card(slide, x, y, w, h, headline, body, accent=BLUE, icon=None):
    rounded(slide, x, y, w, h, WHITE, LINE)
    # Inset by the corner radius at both ends. Run full height, the square bar
    # keeps its corners where the card has already curved away, and they show
    # as tabs sticking out past the outline.
    shape(slide, MSO_SHAPE.RECTANGLE, x, y + CORNER, 0.08, h - 2 * CORNER,
          accent, accent)
    if icon:
        circle = shape(slide, MSO_SHAPE.OVAL, x + 0.28, y + 0.28, 0.55, 0.55,
                       accent, accent)
        add_text(slide, icon, x + 0.28, y + 0.28, 0.55, 0.55, 18, WHITE, True,
                 align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        tx = x + 0.92
    else:
        tx = x + 0.35
    # Two lines of headroom, and a smaller size on icon cards: the icon eats
    # ~0.9" of the width and "Intermediar" broke mid-word at 18pt.
    add_text(slide, headline, tx, y + 0.22, w - (tx - x) - 0.16, 0.60,
             16.5 if icon else 18, NAVY, True)
    add_text(slide, body, x + 0.35, y + 0.88, w - 0.65, h - 1.05,
             12.5, MUTED)


# 1 — Title
s = prs.slides.add_slide(blank)
set_bg(s, NAVY)
shape(s, MSO_SHAPE.RECTANGLE, 8.3, 0, 5.03, 7.5, NAVY_2, NAVY_2)
for i, (x, y, r, c) in enumerate([
    (9.25, 1.15, .62, BLUE), (11.32, 1.02, .42, GREEN),
    (10.48, 2.55, .52, CORAL), (12.0, 3.05, .34, GOLD),
    (9.05, 4.23, .42, GREEN), (11.15, 5.0, .62, BLUE),
    (12.15, 6.0, .42, CORAL)]):
    shape(s, MSO_SHAPE.OVAL, x, y, r, r, c, c)
for x1, y1, x2, y2 in [(9.85,1.45,11.32,1.23),(9.7,1.67,10.48,2.55),
                       (11.0,2.8,12.0,3.2),(10.5,3.0,9.45,4.23),
                       (9.47,4.45,11.15,5.2),(11.75,5.55,12.15,6.18)]:
    ln = s.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = rgb("6D8AA3"); ln.line.width = Pt(1.5)
pill(s, "Proiect de diplomă", 0.72, 0.62, 1.65, "274A66", "A9D5F5")
add_text(s, "Sistem de interogare\na bazelor de date\nprin limbaj natural", 0.72, 1.42, 7.15, 2.75,
         36, WHITE, True)
add_text(s, "Proiectare și evaluare experimentală", 0.75, 4.45, 6.5, 0.42,
         19, "C8D7E4")
add_text(s, "Dodita Alexandru-Tomi", 0.75, 6.30, 3.8, 0.32, 15, WHITE, True)
add_text(s, "Coordonator: Prof. univ. dr. ing. Simona Caraiman", 0.75, 6.72, 6.5, 0.28,
         11.5, "A8B6C4")
add_notes(s, "Deschid prezentarea prin ideea centrală: proiectul urmărește să reducă distanța dintre o întrebare de business și datele necesare unei decizii. Nu este doar o demonstrație de generare SQL, ci și o evaluare controlată a modului în care această generare ar trebui realizată.")


# 2 — Starting point
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "De unde am pornit", "Context")
add_text(s, "Managementul are nevoie zilnic de răspunsuri din date.", 0.72, 1.45, 6.6, 0.72,
         26, NAVY, True)
pill(s, "Întrebare de business", 0.80, 2.52, 2.12)
rounded(s, 0.80, 3.05, 3.12, 1.16, WHITE, LINE)
add_text(s, "„Cum au evoluat veniturile\nîn ultimele șase luni?”", 1.05, 3.30, 2.62, 0.66,
         16, INK, True, italic=True, align=PP_ALIGN.CENTER)
arrow(s, 4.20, 3.46, 1.02, MUTED)
card(s, 5.45, 2.60, 2.65, 2.06, "Intermediar tehnic", "Analistul traduce întrebarea în SQL, verifică rezultatul și pregătește raportul.", CORAL, "SQL")
arrow(s, 8.36, 3.46, 1.02, MUTED)
card(s, 9.62, 2.60, 2.68, 2.06, "Răspuns", "Corect, dar dependent de disponibilitatea unei alte persoane.", GREEN, "✓")
rounded(s, 3.15, 5.37, 7.04, 0.88, CORAL_LIGHT, CORAL_LIGHT)
add_rich_text(s, [("Blocajul: ", {"bold": True, "color": CORAL}),
                  ("managerul nu cunoaște SQL și nu poate aștepta pentru fiecare întrebare de rutină.", {"color": INK})],
              3.40, 5.60, 6.55, 0.38, 17)
footer(s)
add_notes(s, "Punctul de plecare este unul organizațional. Managerii și personalul de decizie au întrebări recurente despre vânzări, costuri, clienți sau operațiuni, însă datele sunt accesibile prin SQL. Pentru fiecare răspuns trebuie solicitat ajutorul unui analist, ceea ce introduce un timp de așteptare și întrerupe activitatea ambelor persoane.")


# 3 — Purpose
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Scopul proiectului", "Obiectiv")
add_text(s, "Un traseu direct de la întrebare la decizie", 0.72, 1.40, 8.6, 0.55, 25, NAVY, True)
steps = [
    ("1", "Întreabă", "Utilizatorul formulează problema în limbaj natural.", BLUE),
    ("2", "Înțelege", "Sistemul identifică schema, generează și validează SQL-ul.", CORAL),
    ("3", "Decide", "Rezultatul este explicat și transformat în tabel sau grafic.", GREEN),
]
for i, (n, h1, body, c) in enumerate(steps):
    x = 0.78 + i * 4.18
    card(s, x, 2.32, 3.68, 2.25, h1, body, c, n)
    if i < 2: arrow(s, x + 3.76, 3.28, 0.34, c)
rounded(s, 1.48, 5.22, 10.36, 0.95, NAVY, NAVY)
add_text(s, "Răspunsuri de zi cu zi, fără bariera SQL — cu control, trasabilitate și acces numai în citire.",
         1.80, 5.49, 9.72, 0.40, 18, WHITE, True, align=PP_ALIGN.CENTER)
footer(s)
add_notes(s, "Scopul este democratizarea accesului la date pentru întrebările de zi cu zi, nu eliminarea rolului analistului. Sistemul preia întrebarea, găsește informațiile relevante, generează o interogare sigură și livrează un rezultat ușor de interpretat. Analistul rămâne necesar pentru analize complexe, modelare și guvernanță.")


# 4 — Product
s = prs.slides.add_slide(blank); set_bg(s, NAVY)
title(s, "Din întrebare, direct la răspuns", "Aplicația", dark=True)
# Captured from the running application, not from the mockup: the frame is
# 1600x1024, the same 1.5625 aspect as the box below, so nothing is cropped.
add_picture_contain(s, SCREENSHOTS / "05-workbench-raspuns-si-sql.png",
                    0.72, 1.48, 8.05, 5.15, border=True)
rounded(s, 9.12, 1.48, 3.44, 5.15, "173F5F", "35556F")
for i, (h1, body, c) in enumerate([
    ("Răspuns conversațional", "Explicația este formulată pentru utilizator, nu pentru baza de date.", BLUE),
    ("Rezultat verificabil", "Tabelul și graficul provin din interogarea executată.", GREEN),
    ("Raport reutilizabil", "Datele pot fi exportate pentru analiză și prezentare.", GOLD),
]):
    # Two lines of headroom for the headline: "Răspuns conversațional" wraps at
    # this width and used to run straight into the body text underneath.
    y = 1.90 + i * 1.55
    shape(s, MSO_SHAPE.OVAL, 9.52, y + 0.04, 0.22, 0.22, c, c)
    add_text(s, h1, 9.88, y - 0.06, 2.46, 0.46, 13.5, WHITE, True)
    add_text(s, body, 9.88, y + 0.48, 2.44, 0.74, 11.5, "B8CAD8")
footer(s, dark=True)
add_notes(s, "Aceasta este interfața sistemului. Utilizatorul discută cu aplicația, iar rezultatul poate fi deschis ca artefact: grafic, tabel și raport. În spate, răspunsul este legat de SQL-ul executat, astfel încât să poată fi verificat și refolosit.")


# 5 — Solution pipeline
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Cum funcționează soluția", "Arhitectură")
add_picture_contain(s, ASSETS / "fig_arm_rag.png", 0.70, 1.48, 8.25, 4.85, border=True)
rounded(s, 9.28, 1.48, 3.30, 4.85, NAVY, NAVY)
add_text(s, "Principii de proiectare", 9.66, 1.84, 2.56, 0.42, 18, WHITE, True)
for i, (n, text_value, c) in enumerate([
    ("01", "Context relevant, nu întreaga bază", BLUE),
    ("02", "Validare pe arborele sintactic", CORAL),
    ("03", "Rol PostgreSQL numai pentru citire", GREEN),
    ("04", "Limită de timp și de rânduri", GOLD),
]):
    y = 2.63 + i * 0.77
    add_text(s, n, 9.65, y, 0.42, 0.28, 10, c, True)
    add_text(s, text_value, 10.16, y - 0.03, 1.98, 0.50, 12.5, WHITE, True)
footer(s, "Configurația RAG implementată în proiect")
add_notes(s, "Conducta proprie selectează tabelele relevante prin căutare lexicală, embeddings și potrivirea valorilor din întrebare. Modelul generează SQL, iar validatorul blochează operațiile de modificare sau accesul nepermis. Execuția are loc cu un utilizator read-only și limite explicite.")


# --- act break: from the system to the measurements -----------------------
s = prs.slides.add_slide(blank); set_bg(s, NAVY)
title(s, "Sistemul funcționează.\nEste însă arhitectura potrivită?", "Partea a doua", dark=True)
add_text(s, "Arhitectura prezentată până aici constituie o alegere de proiectare, nu un "
            "rezultat măsurat. Fiecare decizie este verificată experimental în continuare.",
         0.72, 2.36, 5.30, 1.50, 17, "B8CAD8")
for i, (n, q, c) in enumerate([
    ("01", "Cum ar trebui generat SQL-ul?", BLUE),
    ("02", "Cât costă fiecare variantă?", CORAL),
    ("03", "Pe ce date se poate măsura credibil?", GREEN),
    ("04", "Cum se tratează întrebările ambigue?", GOLD),
]):
    y = 1.80 + i * 1.24
    rounded(s, 6.75, y, 5.86, 1.02, "173F5F", "35556F")
    add_text(s, n, 7.10, y, 0.55, 1.02, 15, c, True, valign=MSO_ANCHOR.MIDDLE)
    add_text(s, q, 7.72, y, 4.62, 1.02, 16, WHITE, True, valign=MSO_ANCHOR.MIDDLE)
footer(s, dark=True)
add_notes(s, "Până în acest punct am descris o arhitectură care funcționează. Nu am arătat însă că este arhitectura potrivită. Partea a doua a lucrării tratează fiecare decizie ca pe o ipoteză de verificat: modul de generare a SQL-ului, costul fiecărei variante, datele pe care măsurarea rămâne credibilă și comportamentul în fața întrebărilor ambigue.")


# 6 — Three arms
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Trei moduri de a genera SQL", "Întrebarea de cercetare")
add_text(s, "Ajută autonomia agentului sau doar adaugă complexitate?", 0.72, 1.38, 9.7, 0.52, 23, NAVY, True)
configs = [
    ("A", "Apel unic", "Schema completă în prompt\nUn singur răspuns", BLUE, "Reper cloud"),
    ("B", "Agent MCP", "Fără schemă inițială\nExplorare prin unelte", CORAL, "Configurația studiată"),
    ("C", "Model local", "Același prompt ca A\nRulare pe GPU personal", GREEN, "Reper local"),
]
for i, (letter, h1, body, c, tag) in enumerate(configs):
    x = 0.78 + i * 4.18
    rounded(s, x, 2.20, 3.66, 3.42, WHITE, LINE)
    shape(s, MSO_SHAPE.OVAL, x + 0.30, 2.49, 0.70, 0.70, c, c)
    add_text(s, letter, x + 0.30, 2.49, 0.70, 0.70, 22, WHITE, True,
             align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    pill(s, tag, x + 1.15, 2.60, 1.92, {BLUE:BLUE_LIGHT,CORAL:CORAL_LIGHT,GREEN:GREEN_LIGHT}[c], c)
    add_text(s, h1, x + 0.34, 3.48, 2.95, 0.42, 20, NAVY, True)
    add_text(s, body, x + 0.34, 4.10, 2.95, 0.78, 14, MUTED)
    add_text(s, "→ SQL", x + 0.34, 5.10, 2.95, 0.30, 13, c, True)
add_text(s, "Între configurațiile comparate se modifică o singură variabilă.",
         2.28, 6.25, 8.76, 0.38, 17, NAVY, True, align=PP_ALIGN.CENTER)
footer(s)
add_notes(s, "Am comparat trei configurații. A primește schema completă și răspunde o singură dată. B nu primește schema, ci explorează baza prin unelte MCP. C este identică procedural cu A, dar rulează un model local. Această separare face rezultatele interpretabile.")


# 7 — Evaluation
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Corectitudinea se măsoară prin execuție", "Metodă")
add_picture_contain(s, ASSETS / "fig_harness.png", 0.70, 1.40, 7.60, 4.95, border=True)
stats = [("18", "sisteme"), ("3", "baze de date"), ("93", "întrebări proprii"), ("1.534", "întrebări BIRD-SQL")]
for i, (num, label) in enumerate(stats):
    x = 8.66 + (i % 2) * 1.92
    y = 1.56 + (i // 2) * 1.63
    rounded(s, x, y, 1.65, 1.30, WHITE, LINE)
    add_text(s, num, x, y + 0.19, 1.65, 0.50, 25, NAVY, True, align=PP_ALIGN.CENTER)
    add_text(s, label, x + 0.12, y + 0.78, 1.41, 0.29, 10.5, MUTED, True, align=PP_ALIGN.CENTER)
rounded(s, 8.66, 5.10, 3.57, 1.12, BLUE_LIGHT, BLUE_LIGHT)
add_text(s, "Nu comparăm textul SQL.\nComparăm rezultatele obținute.", 8.93, 5.36, 3.03, 0.60,
         15, BLUE, True, align=PP_ALIGN.CENTER)
footer(s, "Baze: car_rental, AdventureWorks și BIRD-SQL dev")
add_notes(s, "Două interogări diferite textual pot fi ambele corecte. De aceea, interogarea prezisă și cea de referință sunt executate, apoi sunt comparate seturile de rezultate. Cadrul păstrează separat erorile modelului și erorile de referință și verifică amprenta setului de întrebări.")


# --- the three evaluation sets -------------------------------------------
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Trei seturi, două tipuri de dificultate", "Datele de evaluare")
add_text(s, "Aceeași configurație A, același prompt. Se schimbă doar baza de date.",
         0.72, 1.46, 9.60, 0.30, 14, MUTED, True)

sets = [
    ("car_rental", "elaborată de autor", "9 tabele · 8.026 rânduri",
     "51 de întrebări · autor propriu",
     "What is the longest run of consecutive calendar days on which at least "
     "one reservation was picked up at the Downtown Hub branch?",
     None, "100 %", BLUE, BLUE_LIGHT),
    ("adventureworks", "OLTP public, Microsoft", "68 tabele · ≈761.000 rânduri",
     "56 de întrebări · autor propriu",
     "For each product category, what is the value-weighted average discount "
     "rate on its sales order lines — the sum of unitpricediscount × unitprice "
     "× quantity, divided by the sum of unitprice × quantity?",
     None, "100 %", CORAL, CORAL_LIGHT),
    ("BIRD-SQL dev", "11 baze, autor extern", "75 tabele · 3.932.735 rânduri",
     "1.534 de întrebări · autor extern",
     "List out the account numbers of female clients who are oldest and has "
     "lowest average salary, calculate the gap between this lowest average "
     "salary with the highest average salary?",
     "A11 refers to average salary; if person A's birthdate > B's birthdate, "
     "person B is order than person A.",
     "63,6 %", GREEN, GREEN_LIGHT),
]
for i, (name, prov, size, qs, example, evidence, acc, c, tint) in enumerate(sets):
    x = 0.72 + i * 4.06
    rounded(s, x, 1.86, 3.86, 3.94, WHITE, LINE)
    shape(s, MSO_SHAPE.RECTANGLE, x, 1.86 + CORNER, 0.08, 3.94 - 2 * CORNER, c, c)
    add_text(s, name, x + 0.32, 2.04, 3.30, 0.30, 15, NAVY, True, font="Consolas")
    add_text(s, prov, x + 0.32, 2.38, 3.30, 0.24, 10.5, c, True)
    add_text(s, size, x + 0.32, 2.70, 3.36, 0.24, 11, INK)
    add_text(s, qs, x + 0.32, 2.96, 3.36, 0.24, 11, INK)
    add_text(s, "ÎNTREBARE DIFICILĂ DIN SET", x + 0.32, 3.32, 3.30, 0.20, 8.5, MUTED, True)
    rounded(s, x + 0.30, 3.56, 3.40, 1.60, tint, tint)
    add_text(s, "„" + example + "”", x + 0.44, 3.66, 3.12,
             0.86 if evidence else 1.40, 9.5, INK, italic=True)
    if evidence:
        add_text(s, "+ dicționar extern: " + evidence, x + 0.44, 4.52, 3.12, 0.60,
                 8.5, c, True)
    add_text(s, acc, x + 0.32, 5.20, 3.30, 0.48, 24, c, True)
    add_text(s, "acuratețe de execuție", x + 0.32, 5.58, 3.30, 0.20, 9, MUTED)

rounded(s, 0.72, 5.96, 11.94, 1.00, NAVY, NAVY)
add_rich_text(s, [
    ("În primele două seturi dificultatea este ", {"bold": True, "color": WHITE, "size": 14}),
    ("sintactică", {"bold": True, "color": GOLD, "size": 14}),
    ("; în al treilea este ", {"bold": True, "color": WHITE, "size": 14}),
    ("semantică", {"bold": True, "color": GOLD, "size": 14}),
    (".", {"bold": True, "color": WHITE, "size": 14}),
], 1.04, 6.06, 11.30, 0.32)
add_rich_text(s, [
    ("Coloana ", {"color": "9FB4C6", "size": 11}),
    ("A11", {"color": GOLD, "size": 11, "font": "Consolas"}),
    (" nu poate fi dedusă din schemă, iar valoarea „north Bohemia” nu corespunde formei "
     "„North Bohemia”. Volumul nu explică diferența de scor: dispersia este de 61 de puncte "
     "între cele 11 baze BIRD, față de 8 puncte între modele.",
     {"color": "9FB4C6", "size": 11}),
], 1.04, 6.42, 11.30, 0.48)
footer(s, "car_rental și AdventureWorks: gemini-3.7-flash. BIRD-SQL dev: aceeași rulare, DDL brut")
add_notes(s, "Cele trei seturi nu sunt comparabile ca dificultate, iar diferența nu vine din volum. Primele două conțin întrebări pe care le-am formulat eu, peste scheme pe care le cunoșteam bine: dificultatea este sintactică, adică SQL complex, serii de zile consecutive sau medii ponderate. Pe acestea modelele bune ajung la sută la sută. BIRD schimbă natura dificultății: întrebarea este formulată de altcineva, uneori agramatical, coloanele au nume opace precum A11, iar semantica lor este livrată într-un dicționar ținut separat de schemă. Eșecurile nu sunt de construcție a interogării, ci de ancorare în date. Numărul mare de întrebări nu coboară scorul, ci restabilește puterea de discriminare: pe patruzeci și patru de întrebări, trei modele erau egale la sută la sută.")


# 8 — Main result
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Mai multă autonomie nu a însemnat mai multă acuratețe", "Rezultatul principal")
add_picture_contain(s, ASSETS / "fig_accuracy_arms.png", 0.58, 1.66, 8.45, 5.20)
rounded(s, 9.28, 1.66, 3.33, 4.90, NAVY, NAVY)
for i, (num, label, c) in enumerate([
    ("100%", "cel mai bun apel unic", BLUE),
    ("95,5%", "cel mai bun agent", CORAL),
    ("93,2%", "cel mai bun model local", GREEN),
]):
    y = 2.02 + i * 1.25
    add_text(s, num, 9.64, y, 2.55, 0.55, 26, c, True)
    add_text(s, label, 9.66, y + 0.55, 2.44, 0.25, 11.5, "C8D7E4")
add_text(s, "Toate primele patru poziții folosesc cea mai simplă configurație.",
         9.64, 5.78, 2.48, 0.54, 13, WHITE, True)
footer(s, "Acuratețe de execuție pe car_rental, 44 de întrebări punctate")
add_notes(s, "Rezultatul central este contraintuitiv. Trei modele cu apel unic ating 100%. Cel mai bun agent obține 95,5%, iar cel mai bun model local 93,2%. Accesul la unelte este fezabil, dar nu a depășit reperul simplu cu schema în prompt.")


# 9 — Cost
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Explorarea agentică are un cost structural", "Cost vs. acuratețe")
add_picture_contain(s, ASSETS / "fig_cost_accuracy.png", 0.62, 1.40, 8.80, 5.45)
rounded(s, 9.64, 1.53, 2.86, 2.12, CORAL_LIGHT, CORAL_LIGHT)
add_text(s, "9–63×", 9.64, 1.93, 2.86, 0.63, 31, CORAL, True, align=PP_ALIGN.CENTER)
add_text(s, "mai scump / 100 întrebări", 9.90, 2.70, 2.34, 0.36, 12, CORAL, True, align=PP_ALIGN.CENTER)
card(s, 9.64, 4.05, 2.86, 1.94, "De ce?", "La fiecare pas, agentul retrimite contextul acumulat și promptul propriu.", NAVY)
footer(s, "Costuri măsurate; axa costului este logaritmică")
add_notes(s, "Diferența de cost este mai mare decât diferența de acuratețe. Configurațiile agentice măsurate sunt între 9 și 63 de ori mai scumpe pentru o sută de întrebări. Cauza este bucla agentului: fiecare apel retrimite contextul acumulat.")


# 10 — Local
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Un model local poate fi competitiv", "Infrastructură locală")
add_picture_contain(s, ASSETS / "fig_local.png", 0.62, 1.40, 8.75, 5.45)
rounded(s, 9.62, 1.48, 2.90, 4.90, GREEN_LIGHT, GREEN_LIGHT)
add_text(s, "35B MoE", 9.92, 1.92, 2.28, 0.50, 25, GREEN, True, align=PP_ALIGN.CENTER)
add_text(s, "93,2%", 9.92, 2.56, 2.28, 0.50, 25, NAVY, True, align=PP_ALIGN.CENTER)
add_text(s, "RTX 5070 · 12 GiB", 9.92, 3.24, 2.28, 0.32, 12.5, MUTED, True, align=PP_ALIGN.CENTER)
for i, txt in enumerate(["Datele rămân local", "Fără tarif per token", "Model rar: viteză mai bună"]):
    add_text(s, "✓", 9.98, 4.05 + i * 0.55, 0.25, 0.25, 13, GREEN, True)
    add_text(s, txt, 10.32, 4.02 + i * 0.55, 1.70, 0.34, 11.5, INK, True)
footer(s, "Modele locale servite prin llama.cpp")
add_notes(s, "Modelul local Qwen 35B MoE obține 93,2%, egal cu cel mai bun agent Claude din măsurători. Rulează pe o placă de consum cu 12 GiB. Experimentele arată și că densitatea este mai importantă decât dimensiunea fișierului: un model rar poate fi mai mare pe disc, dar mai rapid la inferență.")


# 11 — Ambiguity
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Adevărata limită: întrebările ambigue", "Comportament")
rounded(s, 0.72, 1.46, 4.02, 4.95, NAVY, NAVY)
pill(s, "Exemplu", 1.12, 1.88, 1.00, "274A66", "A9D5F5")
add_text(s, "„Care sunt cei mai buni clienți?”", 1.12, 2.55, 3.18, 0.95,
         24, WHITE, True)
add_text(s, "după venit?\ndupă numărul de rezervări?\ndupă valoarea medie?", 1.12, 3.80, 3.05, 1.28,
         15, "C8D7E4")
add_text(s, "Un răspuns sigur începe cu o întrebare.", 1.12, 5.55, 3.05, 0.48,
         13.5, GOLD, True)
add_picture_contain(s, ASSETS / "fig_ambiguity.png", 5.05, 1.54, 7.55, 4.60, border=True)
rounded(s, 5.40, 6.10, 6.86, 0.68, CORAL_LIGHT, CORAL_LIGHT)
# Anchored MIDDLE across the full height: the sentence wraps to two lines and
# the second one used to sit below the strip.
add_text(s, "Apelurile unice au preferat să ghicească; agenții au cerut mai des clarificări.",
         5.62, 6.10, 6.42, 0.68, 13, CORAL, True, align=PP_ALIGN.CENTER,
         valign=MSO_ANCHOR.MIDDLE)
footer(s)
add_notes(s, "Pe întrebările SQL bine precizate, modelele de vârf sunt aproape de plafon. Diferența apare când întrebarea pare validă, dar are mai multe interpretări. Toate modelele cu apel unic au ales o interpretare fără să întrebe. Agenții, având un proces deliberativ, au solicitat clarificări mai des.")


# 12 — External validation
s = prs.slides.add_slide(blank); set_bg(s)
title(s, "Validare externă: BIRD-SQL", "Generalizare")
add_text(s, "1.534 de întrebări · 11 baze de date · set elaborat independent", 0.72, 1.34, 8.5, 0.34,
         15, MUTED, True)
add_picture_contain(s, ASSETS / "fig_saturation.png", 0.68, 1.78, 7.72, 4.78, border=True)
rounded(s, 8.72, 1.78, 3.85, 4.78, WHITE, LINE)
add_text(s, "Ce confirmă?", 9.10, 2.16, 3.08, 0.42, 19, NAVY, True)
for i, (h1, body, c) in enumerate([
    ("Seturile proprii se saturează", "Modelele recente ajung la 100%.", BLUE),
    ("BIRD rămâne discriminatoriu", "Scorurile scad la 55,7–63,6%.", CORAL),
    ("Ordinea modelelor se poate schimba", "Capacitatea declarată nu garantează primul loc.", GREEN),
]):
    y = 2.88 + i * 1.02
    shape(s, MSO_SHAPE.OVAL, 9.10, y, 0.20, 0.20, c, c)
    add_text(s, h1, 9.46, y - 0.06, 2.58, 0.27, 12.5, NAVY, True)
    add_text(s, body, 9.46, y + 0.28, 2.58, 0.46, 10.5, MUTED)
footer(s, "BIRD-SQL dev, evaluare pe întregul set")
add_notes(s, "Pentru a evita concluziile dependente de întrebările formulate în proiect, am evaluat modelele și pe întregul BIRD-SQL dev. Aici scorurile scad puternic și setul rămâne discriminatoriu. Validarea externă confirmă că un rezultat perfect pe o bază curată nu înseamnă că problema text-to-SQL este rezolvată în general.")


# 13 — Conclusions
s = prs.slides.add_slide(blank); set_bg(s, NAVY)
title(s, "Concluzii", "Ce rămâne de reținut", dark=True)
conclusions = [
    ("01", "Acces direct la date", "Limbajul natural poate elimina bariera SQL pentru întrebările manageriale de rutină.", BLUE),
    ("02", "Simplu poate fi mai bun", "Apelul unic a fost mai exact, mai rapid și mai ieftin decât explorarea agentică.", CORAL),
    ("03", "Rularea locală este viabilă", "Un model MoE pe hardware de consum a ajuns la 93,2% acuratețe.", GREEN),
    ("04", "Clarificarea este următoarea frontieră", "Sistemul trebuie să știe când nu există încă o întrebare suficient de precisă.", GOLD),
]
for i, (n, h1, body, c) in enumerate(conclusions):
    x = 0.78 + (i % 2) * 6.20
    y = 1.55 + (i // 2) * 2.15
    rounded(s, x, y, 5.72, 1.72, "173F5F", "35556F")
    add_text(s, n, x + 0.35, y + 0.30, 0.55, 0.42, 16, c, True)
    add_text(s, h1, x + 1.02, y + 0.24, 4.24, 0.52, 17, WHITE, True)
    add_text(s, body, x + 1.02, y + 0.86, 4.24, 0.62, 11.8, "C8D7E4")
rounded(s, 2.07, 6.15, 9.20, 0.66, WHITE, WHITE)
add_text(s, "Un sistem bun nu doar generează SQL — știe și când trebuie să întrebe.",
         2.35, 6.32, 8.64, 0.30, 17, NAVY, True, align=PP_ALIGN.CENTER)
footer(s, dark=True)
add_notes(s, "În concluzie, proiectul demonstrează atât utilitatea practică a unei interfețe în limbaj natural, cât și necesitatea unei evaluări riguroase. Configurația agentică este fezabilă, însă nu este automat superioară. Modelele locale sunt deja competitive. Direcția cea mai valoroasă este interacțiunea: sistemul trebuie să poată clarifica intenția înainte de a produce un răspuns convingător, dar greșit.")


# Core metadata
prs.core_properties.title = "Sistem de interogare a bazelor de date prin limbaj natural"
prs.core_properties.subject = "Prezentare proiect de diplomă"
prs.core_properties.author = "Dodita Alexandru-Tomi"
prs.core_properties.comments = "Generată pe baza lucrării și a rezultatelor experimentale din proiect."

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(OUT)
