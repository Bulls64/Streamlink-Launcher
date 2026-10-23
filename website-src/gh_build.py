"""gh_build.py : version GitHub Pages du site (référencement compris).

Mêmes sources que l'artefact (site_head/body/script.html, content_fr/en.html, docs_script.html),
mais une vraie page par langue et par rubrique, pré-rendue, pour que les moteurs indexent tout :

    /            accueil en français        /en/          accueil en anglais
    /docs/       documentation en français  /en/docs/     documentation en anglais

Sortie : ../website/  (publié par .github/workflows/pages.yml)
Usage :  python3 gh_build.py [URL_DU_SITE]
"""
import json, re, shutil, subprocess, sys, datetime
from pathlib import Path
from bs4 import BeautifulSoup
import docs_embed

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://bulls64.github.io/Streamlink-Launcher/").rstrip("/") + "/"
BASE_PATH = "/" + BASE.split("://", 1)[1].split("/", 1)[1]           # ex. /Streamlink-Launcher/
TODAY = datetime.date.today().isoformat()
here = Path(__file__).parent
OUT = here.parent / "website"
FONTS = here / "node_modules" / "@fontsource"
read = lambda n: (here / n).read_text(encoding="utf-8")

PATHS = {("home", "fr"): "", ("home", "en"): "en/", ("docs", "fr"): "docs/", ("docs", "en"): "en/docs/"}
def up(cur): return "../" * cur.count("/")                    # chemin relatif vers la racine du site
def link(cur, kind, lang, frag=""): return (up(cur) + PATHS[(kind, lang)] or "./") + frag
def absu(kind, lang): return BASE + PATHS[(kind, lang)]

LAUNCHER, CHAT = "1.5.0", "0.2.0"
META = {
    ("home", "fr"): ("Streamlink Launcher & Chat : Twitch et Kick dans VLC ou mpv",
                     "Applis libres pour Windows et Linux : regarde Twitch, Kick, YouTube et Steam TV dans VLC, mpv ou PotPlayer, avec les chats dans une fenêtre à part."),
    ("home", "en"): ("Streamlink Launcher & Chat: Twitch and Kick in VLC or mpv",
                     "Free apps for Windows and Linux: watch Twitch, Kick, YouTube and Steam TV in VLC, mpv or PotPlayer, with the chats in a separate window."),
    ("docs", "fr"): ("Documentation · Streamlink Launcher & Chat",
                     "Installer Streamlink, lancer un premier stream, écrire dans le chat Twitch ou Kick, raccourcis, réglages et dépannage : le guide complet des deux applis."),
    ("docs", "en"): ("Documentation · Streamlink Launcher & Chat",
                     "Install Streamlink, open your first stream, write in Twitch or Kick chat, shortcuts, settings and troubleshooting: the complete guide to both apps."),
}
OG_ALT = {"fr": "Streamlink Launcher et Streamlink Chat : le live sort du navigateur.", "en": "Streamlink Launcher and Streamlink Chat: live, minus the browser."}
LOCALE = {"fr": "fr_FR", "en": "en_US"}

# ---------------------------------------------------------------- textes anglais du script du site
SCRIPT = read("site_script.html")
def js_object(name):
    i = SCRIPT.index(f"const {name} = ") + len(f"const {name} = ")
    j = SCRIPT.index("\n  };", i) + 4
    r = subprocess.run(["node", "-e", f"process.stdout.write(JSON.stringify({SCRIPT[i:j]}))"], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)
EN, T = js_object("EN"), js_object("T")

# ---------------------------------------------------------------- morceaux de page
HEAD = read("site_head.html")
CSS = HEAD[HEAD.index("<style>") + 7:HEAD.index("</style>")]
BODY = read("site_body.html")
SVG_DEFS = BODY[:BODY.index('<div class="boot"')].strip()
HEADER = BODY[BODY.index('<header class="top">'):BODY.index("</header>") + 9]
FOOTER = BODY[BODY.index("<footer>"):BODY.index("</footer>") + 9]
BOOT = '<div class="boot" id="boot" aria-hidden="true"></div>\n\n'
MAIN = BODY[BODY.index("</header>") + 9:BODY.index("<footer>")].replace("{{DOCS}}", "")   # sans l'en-tête, ajouté à part

FONT_FACES = ([("Big Shoulders Display", "big-shoulders-display", w, "normal") for w in (600, 800, 900)]
              + [("Instrument Sans", "instrument-sans", w, "normal") for w in (400, 500, 600, 700)] + [("Instrument Sans", "instrument-sans", 400, "italic")]
              + [("IBM Plex Mono", "ibm-plex-mono", w, "normal") for w in (400, 500)])
FONT_FILES = {f"{slug}-latin-{w}-{st}.woff2" for _, slug, w, st in FONT_FACES}

def font_css(prefix):
    faces = FONT_FACES
    return "".join(f'@font-face {{ font-family: "{fam}"; font-style: {st}; font-weight: {w}; font-display: swap; '
                   f'src: url("{prefix}assets/fonts/{slug}-latin-{w}-{st}.woff2") format("woff2"); }}\n' for fam, slug, w, st in faces)

def translate(html, lang):
    """Pré-rend un morceau de page dans la langue voulue (attributs data-i18n du site)."""
    if lang == "fr": return html
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("[data-i18n]"):
        v = EN.get(el["data-i18n"])
        if v is not None: el.clear(); el.append(BeautifulSoup(v, "html.parser"))
    for el in soup.select("[data-i18n-aria]"):
        v = EN.get(el["data-i18n-aria"])
        if v is not None: el["aria-label"] = v
    for el in soup.select("[data-i18n-alt]"):
        v = EN.get(el["data-i18n-alt"])
        if v is not None: el["alt"] = v
    shot = soup.select_one("#shot")
    if shot: shot["alt"] = T["en"]["alt"]["l_main"]
    q = soup.select_one("#q")
    if q: q["placeholder"] = T["en"]["ph"]["twitch"]
    say = soup.select_one("#say")
    if say: say["placeholder"] = T["en"]["ch"]["twitch"][1]
    return str(soup)

def header(cur, kind, lang):
    h = HEADER
    if kind == "docs":
        h = h.replace('href="#top"', f'href="{link(cur, "home", lang)}"')
        for sec in ("launcher", "chat", "download"):
            h = h.replace(f'href="#{sec}"', f'href="{link(cur, "home", lang, "#" + sec)}"')
        h = h.replace('<a href="#docs" id="nav-docs">', f'<a href="{link(cur, "docs", lang)}" id="nav-docs" aria-current="page">')
    else:
        h = h.replace('<a href="#docs" id="nav-docs">', f'<a href="{link(cur, "docs", lang)}" id="nav-docs">')
    h = h.replace('<option value="fr" lang="fr">', '<option value="fr" lang="fr"' + (' selected' if lang == "fr" else '') + '>')
    h = h.replace('<option value="en" lang="en">', '<option value="en" lang="en"' + (' selected' if lang == "en" else '') + '>')
    return translate(h, lang)

# ---------------------------------------------------------------- données structurées
AUTHOR = {"@type": "Person", "@id": BASE + "#author", "name": "Bulls64", "url": "https://github.com/Bulls64"}
def apps(lang):
    fr = lang == "fr"
    def app(name, ver, repo, desc, shot):
        return {"@type": "SoftwareApplication", "name": name, "softwareVersion": ver,
                "applicationCategory": "MultimediaApplication", "operatingSystem": "Windows 10, Windows 11, Linux",
                "description": desc, "url": absu("home", lang) + ("#launcher" if "Launcher" in name else "#chat"),
                "downloadUrl": f"https://github.com/Bulls64/{repo}/releases/latest",
                "screenshot": BASE + f"assets/img/site/{lang}/{shot}.webp",
                "license": "https://opensource.org/licenses/MIT", "isAccessibleForFree": True,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                "author": {"@id": BASE + "#author"}, "sameAs": f"https://github.com/Bulls64/{repo}", "inLanguage": ["fr", "en"]}
    return [
        app("Streamlink Launcher", LAUNCHER, "Streamlink-Launcher",
            "Interface légère pour Streamlink : ouvre Twitch, Kick, YouTube, Dailymotion et Steam TV dans VLC, mpv ou PotPlayer, avec favoris en direct et mode mini." if fr else
            "Lightweight interface for Streamlink: opens Twitch, Kick, YouTube, Dailymotion and Steam TV in VLC, mpv or PotPlayer, with live favorites and a mini mode.", "l_main"),
        app("Streamlink Chat", CHAT, "Streamlink-Chat",
            "Chats Twitch, Kick et Steam TV dans une seule fenêtre, un onglet par chaîne, lecture sans compte et écriture après connexion." if fr else
            "Twitch, Kick and Steam TV chats in one window, one tab per channel, read without an account and write once logged in.", "c_tw"),
    ]

def faq_items(content_html):
    soup = BeautifulSoup(content_html, "html.parser")
    items = []
    for d in soup.select("details.faq"):
        q = d.find("summary")
        for tag in q.select(".d-app"): tag.decompose()
        a = d.select_one(".a")
        if not (q and a): continue
        items.append({"@type": "Question", "name": q.get_text(" ", strip=True),
                      "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\s+", " ", a.get_text(" ", strip=True))}})
    return items

def jsonld(kind, lang, content=None):
    title, desc = META[(kind, lang)]
    site = {"@type": "WebSite", "@id": BASE + "#website", "url": BASE, "name": "Streamlink Launcher & Chat", "inLanguage": ["fr", "en"], "publisher": {"@id": BASE + "#author"}}
    page = {"@type": "WebPage" if kind == "home" else "TechArticle", "@id": absu(kind, lang) + "#page", "url": absu(kind, lang),
            "name": title, "description": desc, "inLanguage": lang, "isPartOf": {"@id": BASE + "#website"},
            "dateModified": TODAY, "image": BASE + f"assets/og/{kind}-{lang}.jpg", "author": {"@id": BASE + "#author"}}
    graph = [site, AUTHOR, page]
    if kind == "home":
        graph += apps(lang)
    else:
        page["headline"] = "Documentation Streamlink Launcher & Chat"
        page["about"] = [{"@type": "SoftwareApplication", "name": "Streamlink Launcher"}, {"@type": "SoftwareApplication", "name": "Streamlink Chat"}]
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Streamlink Launcher & Chat", "item": absu("home", lang)},
            {"@type": "ListItem", "position": 2, "name": "Documentation", "item": absu(kind, lang)}]})
        faqs = faq_items(content)
        if faqs: graph.append({"@type": "FAQPage", "@id": absu(kind, lang) + "#faq-data", "inLanguage": lang, "mainEntity": faqs})
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)
    return '<script type="application/ld+json">\n' + data.replace("</", "<\\/") + "\n</script>"

def head(cur, kind, lang, extra_css="", content=None):
    title, desc = META[(kind, lang)]
    other = "en" if lang == "fr" else "fr"
    p = up(cur)
    esc = lambda s: s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return f"""<!doctype html>
<html lang="{lang}"{' class="nointro static"' if kind == "docs" else ''}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="Bulls64">
<link rel="canonical" href="{absu(kind, lang)}">
<link rel="alternate" hreflang="fr" href="{absu(kind, 'fr')}">
<link rel="alternate" hreflang="en" href="{absu(kind, 'en')}">
<link rel="alternate" hreflang="x-default" href="{absu(kind, 'fr')}">
<meta property="og:type" content="{'website' if kind == 'home' else 'article'}">
<meta property="og:site_name" content="Streamlink Launcher &amp; Chat">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{absu(kind, lang)}">
<meta property="og:locale" content="{LOCALE[lang]}">
<meta property="og:locale:alternate" content="{LOCALE[other]}">
<meta property="og:image" content="{BASE}assets/og/{kind}-{lang}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(OG_ALT[lang])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{BASE}assets/og/{kind}-{lang}.jpg">
<meta name="theme-color" content="#E9ECF1" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0F1116" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{p}favicon.ico" sizes="32x32">
<link rel="icon" href="{p}assets/icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{p}assets/icons/apple-touch-icon.png">
<link rel="manifest" href="{p}site.webmanifest">
<link rel="preload" href="{p}assets/fonts/instrument-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{p}assets/fonts/big-shoulders-display-latin-900-normal.woff2" as="font" type="font/woff2" crossorigin>
{jsonld(kind, lang, content)}
<style>
{font_css(p)}{CSS.replace("{{DOCS_CSS}}", extra_css)}</style>
</head>
<body>
"""

# ---------------------------------------------------------------- scripts
def lang_switch_js(cur, kind):
    """Le menu de langue mène à la page de l'autre langue (même section quand c'est possible)."""
    alt = {l: link(cur, kind, l) for l in ("fr", "en")}
    idmap = {}
    if kind == "docs":
        ids = {l: re.findall(r'<section class="doc" id="([^"]+)"', read(f"content_{l}.html")) for l in ("fr", "en")}
        assert len(ids["fr"]) == len(ids["en"])
        for a, b in zip(ids["fr"], ids["en"]): idmap[a] = b; idmap[b] = a
    return ("<script>\nwindow.SL_PAGES = " + json.dumps({"alt": alt, "ids": idmap}, ensure_ascii=False) + ";\n"
            "function slGoLang(l) {\n"
            "  try { localStorage.setItem(\"slSiteLang\", l); } catch {}\n"
            "  let id = \"\"; try { id = decodeURIComponent(location.hash.slice(1)); } catch {}\n"
            "  const target = SL_PAGES.ids[id] || (id && document.getElementById(id) && !Object.keys(SL_PAGES.ids).length ? id : \"\");\n"
            "  location.href = SL_PAGES.alt[l] + (target ? \"#\" + target : \"\");\n"
            "}\n</script>\n")

def home_script(cur, lang):
    s = SCRIPT
    def cut(a, b):
        nonlocal s
        i, j = s.index(a), s.index(b)
        s = s[:i] + s[j:]
    def sub(a, b):
        nonlocal s
        assert a in s, a[:60]
        s = s.replace(a, b, 1)
    cut("  /* ---------- onglet Docs", "  /* ---------- langue ---------- */")
    sub("    SLDocs.setLang(l, live); setTitle();\n", "")
    sub('''    try { localStorage.setItem(KEY, sel.value); } catch {}
    apply(sel.value, true);''', "    slGoLang(sel.value);")
    s = re.sub(r"  function startLang\(\) \{.*?\n  \}\n", "  function startLang() { return document.documentElement.lang; }\n", s, count=1, flags=re.S)
    sub("  route();\n", "")
    sub('if (reduce || view === "docs")', "if (reduce)")
    imgs = {l: {k: f"{up(cur)}assets/img/site/{l}/{k}.webp" for k in ("l_main", "l_mini", "l_set", "l_light", "c_tw", "c_kick", "c_light")} for l in ("fr", "en")}
    return s.replace("{{IMG_JSON}}", json.dumps(imgs)), imgs

def docs_script(lang):
    s = read("docs_script.html")
    for a, b in [('en: document.getElementById("doc-en").innerHTML', "en: root.innerHTML"),
                 ('let shownLang = "fr";', "let shownLang = document.documentElement.lang;"),
                 ('} else if (visible() && location.hash && location.hash !== "#docs") {', '} else if (keepPlace && location.hash) {')]:
        assert a in s, a; s = s.replace(a, b)
    theme = SCRIPT[SCRIPT.index("  /* ---------- thème clair / sombre"):SCRIPT.index("  /* ---------- onglet Docs")]
    return s + f"""<script>
(() => {{
  const root = document.documentElement, lang = root.lang;
{theme}  drawTheme();
  const sel = document.getElementById("lang");
  sel.value = lang;
  sel.addEventListener("change", () => slGoLang(sel.value));
  SLDocs.setLang(lang, false);
  if (location.hash) {{ const t = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) t.scrollIntoView({{ behavior: "instant" }}); }}
}})();
</script>
"""

# ---------------------------------------------------------------- pages
def build_home(lang):
    cur = PATHS[("home", lang)]
    js, imgs = home_script(cur, lang)
    main = re.sub(r"\{\{img:(\w+):(\w+)\}\}", lambda m: imgs[lang][m.group(2)], MAIN)
    main = main.replace('<figure><img data-img=', '<figure><img loading="lazy" decoding="async" data-img=')
    body = SVG_DEFS + "\n\n" + BOOT + header(cur, "home", lang) + "\n\n" + translate(main, lang) + "\n" + translate(FOOTER, lang) + "\n"
    return head(cur, "home", lang) + body + lang_switch_js(cur, "home") + js + "</body>\n</html>\n"

def build_docs(lang):
    cur = PATHS[("docs", lang)]
    content = docs_embed.content(f"content_{lang}.html")
    content = re.sub(r'src="img/(en/)?([^"]+\.webp)"', lambda m: f'src="{up(cur)}assets/img/docs/{"en/" if m.group(1) else ""}{m.group(2)}" decoding="async"', content)
    view = ('<div id="docs" class="docs-view">\n<main id="docroot">\n' + content + '</main>\n'
            '<dialog class="lb" id="lb"><button type="button">×</button><img alt=""><p></p></dialog>\n</div>\n')
    body = SVG_DEFS + "\n\n" + header(cur, "docs", lang) + "\n\n" + view + "\n" + translate(FOOTER, lang) + "\n"
    return head(cur, "docs", lang, docs_embed.css(), content) + body + lang_switch_js(cur, "docs") + docs_script(lang) + "</body>\n</html>\n"

def build():
    if OUT.exists(): shutil.rmtree(OUT)          # dossier généré : reconstruit à chaque fois
    for (kind, lang), path in PATHS.items():
        f = OUT / path / "index.html"; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(build_home(lang) if kind == "home" else build_docs(lang), encoding="utf-8")
    # images
    shutil.copytree(here / "img" / "site", OUT / "assets/img/site")
    (OUT / "assets/img/docs/en").mkdir(parents=True)
    for p in (here / "img").glob("*.webp"): shutil.copy(p, OUT / "assets/img/docs" / p.name)
    for p in (here / "img" / "en").glob("*.webp"): shutil.copy(p, OUT / "assets/img/docs/en" / p.name)
    # polices (licence SIL OFL 1.1, copiées avec leur licence)
    fd = OUT / "assets/fonts"; fd.mkdir(parents=True)
    for slug in ("big-shoulders-display", "instrument-sans", "ibm-plex-mono"):
        for f in (FONTS / slug / "files").glob(f"{slug}-latin-*.woff2"):
            if f.name in FONT_FILES: shutil.copy(f, fd / f.name)
        shutil.copy(FONTS / slug / "LICENSE", fd / f"LICENSE-{slug}.txt")
    # icônes, images de partage (faites par make_assets.mjs)
    shutil.copytree(here / "gh_assets" / "icons", OUT / "assets/icons")
    shutil.copytree(here / "gh_assets" / "og", OUT / "assets/og")
    shutil.copy(here / "gh_assets" / "favicon.ico", OUT / "favicon.ico")
    # fichiers pour les moteurs
    urls = []
    for kind in ("home", "docs"):
        for lang in ("fr", "en"):
            alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{absu(kind, l)}"/>' for l in ("fr", "en"))
            alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{absu(kind, "fr")}"/>'
            urls.append(f"  <url>\n    <loc>{absu(kind, lang)}</loc>\n    <lastmod>{TODAY}</lastmod>{alts}\n  </url>")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                     'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    (OUT / "site.webmanifest").write_text(json.dumps({
        "name": "Streamlink Launcher & Chat", "short_name": "Streamlink", "start_url": "./", "scope": "./", "display": "browser",
        "background_color": "#0F1116", "theme_color": "#9146FF", "lang": "fr",
        "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "assets/icons/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "404.html").write_text(page_404(), encoding="utf-8")
    print("ok", BASE, sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) // 1024, "Ko")

def page_404():
    b = BASE_PATH
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page introuvable · Streamlink Launcher &amp; Chat</title>
<meta name="robots" content="noindex">
<link rel="icon" href="{b}favicon.ico" sizes="32x32">
<link rel="icon" href="{b}assets/icons/icon.svg" type="image/svg+xml">
<style>
@font-face {{ font-family: "Big Shoulders Display"; font-weight: 900; font-display: swap; src: url("{b}assets/fonts/big-shoulders-display-latin-900-normal.woff2") format("woff2"); }}
@font-face {{ font-family: "Instrument Sans"; font-weight: 400; font-display: swap; src: url("{b}assets/fonts/instrument-sans-latin-400-normal.woff2") format("woff2"); }}
@font-face {{ font-family: "Instrument Sans"; font-weight: 600; font-display: swap; src: url("{b}assets/fonts/instrument-sans-latin-600-normal.woff2") format("woff2"); }}
:root {{ --bg: #E9ECF1; --surface: #F7F8FA; --ink: #13151B; --muted: #586071; --line: #CDD2DB; --accent: #6E2BD9; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0F1116; --surface: #161920; --ink: #ECEEF3; --muted: #959CAD; --line: #2A2F3A; --accent: #B794FF; color-scheme: dark; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--ink); font-family: "Instrument Sans", "Segoe UI", system-ui, sans-serif; line-height: 1.6; padding: 24px 16px; }}
main {{ max-width: 560px; display: grid; gap: 14px; }}
.code {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: .8rem; letter-spacing: .2em; color: var(--muted); }}
h1 {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; text-transform: uppercase; font-size: clamp(2.6rem, 11vw, 4.6rem); line-height: .9; margin: 0; }}
p {{ margin: 0; color: var(--muted); }}
nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }}
nav a {{ color: var(--ink); text-decoration: none; font-weight: 600; background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 7px 14px; }}
nav a:hover {{ border-color: var(--accent); }}
</style>
</head>
<body>
<main>
  <div class="code">CH 404 · NO SIGNAL</div>
  <h1>Pas de signal</h1>
  <p>Cette page n'existe pas ou a changé d'adresse. <span lang="en">This page doesn't exist or has moved.</span></p>
  <nav>
    <a href="{b}">Accueil</a><a href="{b}docs/">Documentation</a>
    <a href="{b}en/" lang="en">Home (English)</a><a href="{b}en/docs/" lang="en">Docs (English)</a>
  </nav>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    build()
