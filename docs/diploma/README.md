# Lucrarea de diplomă

`lucrare.tex` — sursa. `lucrare.pdf` — rezultatul compilării.

## Compilare

```bash
lualatex lucrare.tex && lualatex lucrare.tex && lualatex lucrare.tex
```

Pe Overleaf nu trebuie schimbat nimic: fișierul `latexmkrc` din acest
director selectează automat LuaLaTeX.

**Este necesar LuaLaTeX (sau XeLaTeX), nu pdfLaTeX.** Sub codificarea T1 a
pdfLaTeX, literele `ș`, `ț` și `ă` nu există ca glife precompuse: sunt
construite din literă plus accent poziționat separat, iar unele
vizualizatoare PDF redau construcția cu spații și suprapuneri de caractere.
LuaLaTeX cu un font Unicode le tratează ca glife unice.

Întregul document — text, matematică, nume de fișiere și listinguri — este
cules cu **TeX Gyre Termes**, clona metric identică a fontului Times New
Roman distribuită cu TeX, corp de **12 pt**, spațiere 1, margini de 2 cm.
Figurile folosesc Liberation Serif, tot o clonă metrică Times: este un font
TrueType, pe care matplotlib îl înglobează corect, spre deosebire de
varianta OpenType.

## Regenerarea figurilor și a tabelelor

Toate cifrele din capitolul 4 sunt citite din `benchmark/results/*.json`;
niciuna nu este transcrisă manual. După orice rulare nouă a bancului de probă:

```bash
python docs/diploma/figures/make_all.py
```

- `figures/diagrams.py` — cele trei scheme bloc (banc de probă, braț RAG, braț MCP)
- `figures/charts.py`   — cele șapte grafice de rezultate
- `figures/tables.py`   — cele opt tabele din `tables/*.tex`, incluse cu `\input`
- `figures/common.py`   — stilul comun și verificarea amprentei setului de întrebări

`common.load()` refuză un fișier de rezultate a cărui amprentă nu corespunde
setului curent de întrebări, ca să nu ajungă o rulare învechită într-o figură.

## Fișiere

| fișier | rol |
| --- | --- |
| `lucrare.tex` | lucrarea (RO, 12pt, margini 2cm, bibliografie IEEE) |
| `figures/*.pdf` | figurile, vectoriale |
| `tables/*.tex` | corpurile de tabel generate |
| `diploma.tex` | **versiune veche, cu valori-șablon — nu se folosește** |
