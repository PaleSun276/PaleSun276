"""Render the animated SVG cards + README.md / README.fr.md from profile.json.

python scripts/render_readme_cards.py            # real data (needs GH_TOKEN, or data/contributions.json)
python scripts/render_readme_cards.py --demo --out preview   # fake data, nothing in the repo is touched
STATIC=1 python ...                              # freeze animations (for screenshots)
"""
import argparse, base64, datetime, json, math, os, random, sys, re, urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("en", "fr")
R = 20  # one corner radius for every card

# Oria "Aube doree" palette (design-system/oria-tokens.css) + logo greens. No gradients.
GOLD, GREEN, CREAM = "#D19D33", "#282E1E", "#F9F7EF"
INK, SOFT, VIOLET, PALE = "#3B3A24", "#D9D0EE", "#6A4C93", "#F5E9B8"
RAMP = ["#3A4430", "#947632", "#A87F2B", GOLD, PALE]  # level 1 lightened for 3:1 contrast on GREEN

MONTHS = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
          "fr": "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.".split()}
T = {
    "en": {"project": "Project", "year": "contributions in the last year", "less": "less", "more": "more",
           "contrib": "Contributions", "src": "Source: GitHub", "upd": "updated {d}"},
    "fr": {"project": "Projet", "year": "contributions sur l'année", "less": "moins", "more": "plus",
           "contrib": "Contributions", "src": "Source : GitHub", "upd": "mis à jour le {d}"},
}

FONTS = {"display": ("OriaDisplay", "oria-display.woff2", "italic"),
         "roman": ("OriaRoman", "oria-roman.woff2", "normal"),
         "ui": ("OriaUI", "oria-ui.woff2", "normal")}


def font_css(*names):
    out = ""
    for n in names:
        fam, f, style = FONTS[n]
        b = base64.b64encode((ROOT / "scripts/fonts" / f).read_bytes()).decode()
        out += f"@font-face{{font-family:'{fam}';font-style:{style};src:url(data:font/woff2;base64,{b})}}"
    return out


CSS = """
.n{font-family:'OriaDisplay',Georgia,serif;font-style:italic}
.r{font-family:'OriaRoman',Georgia,serif}
.u{font-family:'OriaUI',system-ui,sans-serif}
@keyframes rise{from{opacity:0;transform:translateY(10px)}}
@keyframes pop{from{opacity:0;transform:scale(.4)}}
@keyframes float{50%{transform:translateY(-6px)}}
@keyframes pulse{50%{opacity:.5}}
@keyframes sheen{from{transform:translateX(-340px)}to{transform:translateX(900px)}}
@keyframes nudge{50%{transform:translate(3px,-3px)}}
.rise{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}
.float{animation:float 5s ease-in-out infinite}
.hex{animation:pulse 4s ease-in-out infinite}
.sheen{animation:sheen 5.5s ease-in-out 1.6s infinite}
.nudge{animation:nudge 2.4s ease-in-out infinite}
.cell{animation:pop .5s ease-out both;transform-box:fill-box;transform-origin:center}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
""" + ("*{animation:none!important}" if os.environ.get("STATIC") else "")


def svg(w, h, body, title, fonts):
    """Card of w x h, wrapped in a transparent margin so the gap between cards is the same everywhere."""
    p = round(w * 0.009)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w + 2 * p} {h + 2 * p}" role="img">'
            f'<title>{escape(title)}</title><style>{font_css(*fonts)}{CSS}</style>'
            f'<g transform="translate({p} {p})">{body}</g></svg>')


def symbol_paths():
    s = (ROOT / "scripts/assets/oria-symbole-inverse.svg").read_text(encoding="utf-8")
    return re.findall(r'<path fill="([^"]+)"[^>]* d="([^"]+)"', s)


def logo(x, y, size, cls=""):
    paths = "".join(f'<path fill="{f}" fill-rule="evenodd" d="{d}"/>' for f, d in symbol_paths())
    return f'<g class="{cls}"><g transform="translate({x} {y}) scale({size / 256:.4f})">{paths}</g></g>'


def hexagon(cx, cy, r):
    pts = [(cx + r * math.cos(math.radians(60 * i + 30)), cy + r * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    return "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts) + "Z"


def honeycomb(w, h, r=26):
    """Faint honeycomb over the right 45% of the card, fading toward the text; a few cells pulse."""
    dx, dy = r * math.sqrt(3), r * 1.5
    out, n = [], 0
    for row in range(int(h / dy) + 2):
        for col in range(int(w / dx) + 2):
            cx, cy = col * dx + (dx / 2 if row % 2 else 0), row * dy
            if cx < w * 0.55:
                continue
            n += 1
            op = 0.05 + 0.22 * (cx - w * 0.55) / (w * 0.45)
            anim = f' class="hex" style="animation-delay:{(n * 0.37) % 4:.2f}s"' if n % 7 == 0 else ""
            out.append(f'<path d="{hexagon(cx, cy, r - 2)}" fill="none" stroke="{GOLD}" stroke-opacity="{op:.2f}"{anim}/>')
    return "".join(out)


# fine-stroke icons on a 24-unit grid, one family, same stroke width
ICONS = {
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    "diamond": '<path d="M12 3l9 9-9 9-9-9z"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M4 7l8 6 8-6"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/>',
}


def icon(name, x, y, size, color):
    return (f'<g transform="translate({x} {y}) scale({size / 24:.3f})" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["link"])}</g>')


def hero(cfg, lang):
    w, h = 960, 200
    name, tag = escape(cfg["name"]), escape(cfg["tagline"][lang])
    body = f"""
<defs><clipPath id="card"><rect width="{w}" height="{h}" rx="{R}"/></clipPath>
 <clipPath id="nm"><text x="204" y="112" class="n" font-size="72">{name}</text></clipPath></defs>
<g clip-path="url(#card)">
 <rect width="{w}" height="{h}" fill="{GREEN}"/>
 {honeycomb(w, h)}
 {logo(44, 38, 124, "float")}
 <text x="206" y="112" class="n rise" font-size="72" fill="{CREAM}" style="animation-delay:.2s">{name}</text>
 <g clip-path="url(#nm)"><rect class="sheen" x="0" y="40" width="80" height="90" fill="{PALE}" opacity=".85" transform="skewX(-20)"/></g>
 <rect x="208" y="130" width="56" height="3" rx="1.5" fill="{GOLD}" class="rise" style="animation-delay:.5s"/>
 <text x="206" y="172" class="u rise" font-size="28" fill="{SOFT}" style="animation-delay:.65s">{tag}</text>
</g>"""
    return svg(w, h, body, f"{cfg['name']} - {cfg['tagline'][lang]}", ("display", "ui"))


def row_card(kind, label, value, ic, right_pill=None):
    """Full-width card sized to its text. kind: 'project' (cream) or 'link' (violet)."""
    w, h = 640, 96
    bg, bd, lb, vl, icc = ((CREAM, f'stroke="{GOLD}" stroke-opacity=".6" stroke-width="2"', VIOLET, INK, VIOLET)
                           if kind == "project" else (VIOLET, 'stroke="none"', PALE, CREAM, PALE))
    if right_pill:
        pw = len(right_pill) * 9.8 + 40
        right = (f'<rect x="{w - 28 - pw:.0f}" y="31" width="{pw:.0f}" height="34" rx="17" fill="{SOFT}"/>'
                 f'<text x="{w - 28 - pw / 2:.0f}" y="48" text-anchor="middle" dominant-baseline="central" class="u" font-size="16" fill="#3A2D52">{escape(right_pill)}</text>')
    else:
        right = (f'<g class="nudge" transform="translate({w - 62} {34})"><path d="M0 26 L26 0 M7 0 H26 V19" fill="none" stroke="{GOLD}" '
                 f'stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></g>')
    body = f"""
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{R}" fill="{bg}" {bd}/>
{icon(ic, 28, 29, 38, icc)}
<text x="84" y="38" class="u rise" font-size="15" letter-spacing="3" fill="{lb}">{escape(label.upper())}</text>
<text x="84" y="73" class="r rise" font-size="32" fill="{vl}" style="animation-delay:.12s">{escape(value)}</text>
{right}"""
    return svg(w, h, body, f"{label}: {value}", ("roman", "ui"))


def fetch_contributions(login, token):
    q = ("query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{totalContributions "
         "weeks{contributionDays{contributionCount}}}}}}")
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": q, "variables": {"l": login}}).encode(),
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    cal = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]  # KeyError/TypeError => loud failure
    return {"total": cal["totalContributions"],
            "weeks": [[d["contributionCount"] for d in wk["contributionDays"]] for wk in cal["weeks"]]}


def demo_contributions():
    rnd = random.Random(7)
    weeks = [[max(0, int(rnd.gauss(2, 3))) if rnd.random() > .35 else 0 for _ in range(7)] for _ in range(53)]
    return {"total": sum(map(sum, weeks)), "weeks": weeks}


def today(lang):
    d = datetime.datetime.now(datetime.timezone.utc)
    return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}"


def activity(data, lang):
    w, h, cell, gap = 960, 250, 13, 3.5
    t = T[lang]
    weeks = data["weeks"][-53:]
    step = cell + gap
    gw = len(weeks) * step - gap
    x0 = (w - gw) / 2  # grid centred: same margin left and right, header and footer align on it
    top = max((c for wk in weeks for c in wk), default=0) or 1
    def lvl(c): return 0 if c == 0 else 1 + min(3, int(4 * c / (top + 1)))
    cells = "".join(f'<rect class="cell" x="{x0 + i * step:.1f}" y="{86 + j * step:.1f}" width="{cell}" height="{cell}" rx="4" '
                    f'fill="{RAMP[lvl(c)]}" style="animation-delay:{0.3 + i * 0.025:.2f}s"/>'
                    for i, wk in enumerate(weeks) for j, c in enumerate(wk))
    lx = w - x0 - 5 * 17 - 44  # leave room for the word after the squares
    legend = "".join(f'<rect x="{lx + k * 17:.1f}" y="216" width="13" height="13" rx="4" fill="{RAMP[k]}"/>' for k in range(5))
    body = f"""
<rect width="{w}" height="{h}" rx="{R}" fill="{GREEN}"/>
<text x="{x0:.1f}" y="52" class="r rise" font-size="34" fill="{CREAM}">{t["contrib"]}</text>
<text x="{w - x0:.1f}" y="52" text-anchor="end" class="u rise" font-size="22" fill="{GOLD}" style="animation-delay:.2s">{data["total"]} {escape(t["year"])}</text>
{cells}
<text x="{x0:.1f}" y="227" class="u" font-size="15" fill="{SOFT}">{escape(t["src"])} · {escape(t["upd"].format(d=today(lang)))}</text>
<text x="{lx - 8:.1f}" y="227" text-anchor="end" class="u" font-size="15" fill="{SOFT}">{t["less"]}</text>{legend}
<text x="{lx + 5 * 17 + 3:.1f}" y="227" class="u" font-size="15" fill="{SOFT}">{t["more"]}</text>"""
    return svg(w, h, body, f"{data['total']} {t['year']}", ("roman", "ui"))


def readme(cfg, lang, data):
    nav = ('<b>English</b> · <a href="README.fr.md">Français</a>' if lang == "en"
           else '<a href="README.md">English</a> · <b>Français</b>')
    t = T[lang]
    img = lambda src, alt: f'<img src="cards/{src}" width="100%" alt="{escape(alt)}">'
    rows = [img(f"hero-{lang}.svg", f"{cfg['name']} - {cfg['tagline'][lang]}")]
    for i, p in enumerate(cfg["projects"]):
        a = img(f"project-{i}-{lang}.svg", f"{t['project']}: {p['name']} ({p['status'][lang]})")
        rows.append(f'<a href="{p["href"]}">{a}</a>' if p.get("href") else a)
    for i, l in enumerate(cfg["links"]):
        rows.append(f'<a href="{l["href"]}">{img(f"link-{i}-{lang}.svg", l["label"][lang] + ": " + l["value"])}</a>')
    rows.append(img(f"activity-{lang}.svg", f"{t['contrib']}: {data['total']} {t['year']}"))
    foot = " · ".join(x for x in (cfg["name"], cfg.get("email")) if x)
    return (f'<p align="right">{nav}</p>\n\n<p align="center">\n' + "\n".join(rows) +
            f'\n</p>\n\n<p align="center"><sub>{escape(foot)}</sub></p>\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=".", help="output root (cards/ and READMEs go here)")
    a = ap.parse_args()
    cfg = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = ROOT / a.out
    (out / "cards").mkdir(parents=True, exist_ok=True)

    cache = ROOT / "data/contributions.json"
    if a.demo:
        data = demo_contributions()
    elif os.environ.get("GH_TOKEN"):
        data = fetch_contributions(cfg["login"], os.environ["GH_TOKEN"])
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
    elif cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        sys.exit("No GH_TOKEN and no data/contributions.json: refusing to draw an empty graph.")

    for lang in LANGS:
        w = lambda name, s: (out / "cards" / name).write_text(s, encoding="utf-8")
        w(f"hero-{lang}.svg", hero(cfg, lang))
        for i, p in enumerate(cfg["projects"]):
            w(f"project-{i}-{lang}.svg", row_card("project", T[lang]["project"], p["name"], p.get("icon", "link"), p["status"][lang]))
        for i, l in enumerate(cfg["links"]):
            w(f"link-{i}-{lang}.svg", row_card("link", l["label"][lang], l["value"], l.get("icon", "link")))
        w(f"activity-{lang}.svg", activity(data, lang))
        (out / ("README.md" if lang == "en" else "README.fr.md")).write_text(readme(cfg, lang, data), encoding="utf-8")
    print("ok ->", out)


if __name__ == "__main__":
    main()
