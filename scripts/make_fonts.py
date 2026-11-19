"""One-off: subset the Oria brand fonts into small woff2 files that can be embedded in SVG.
Run locally only (needs the installed variable fonts); the woff2 outputs are committed.
Usage: python scripts/make_fonts.py
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools import subset

SRC = Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
OUT = Path(__file__).parent / "fonts"
# printable ASCII + French accents + a few typographic marks
CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "éèêëàâäçùûüôöîïœÉÈÀÇ’‘“”—–·…"

JOBS = [
    ("Fraunces-Italic-VariableFont_SOFT,WONK,opsz,wght.ttf",
     {"wght": 380, "opsz": 72, "SOFT": 100, "WONK": 1}, "oria-display.woff2"),
    ("Fraunces-VariableFont_SOFT,WONK,opsz,wght.ttf",
     {"wght": 400, "opsz": 72, "SOFT": 100, "WONK": 0}, "oria-roman.woff2"),
    ("AlbertSans-VariableFont_wght.ttf", {"wght": 500}, "oria-ui.woff2"),
]

for src, axes, out in JOBS:
    font = instantiateVariableFont(TTFont(SRC / src), axes)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    sub = subset.Subsetter(opts)
    sub.populate(text=CHARS)
    sub.subset(font)
    font.flavor = "woff2"
    font.save(OUT / out)
    print(out, (OUT / out).stat().st_size, "bytes")
