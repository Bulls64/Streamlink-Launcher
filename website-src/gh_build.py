"""gh_build.py : version GitHub Pages du site (référencement compris).

Mêmes sources que l'artefact (site_body.html, site.css, site.js, content_*.html, docs.css, docs.js),
mais une vraie page par langue et par rubrique, pré-rendue, pour que les moteurs indexent tout :

    /            accueil en français        /en/ /es/ /de/ /it/          accueil dans les autres langues
    /docs/       documentation en français  /en/docs/ /es/docs/ …       documentation dans les autres langues

Le CSS et le JavaScript sont dans des fichiers à part (assets/css/, assets/js/), jamais dans le HTML.

Sortie : ../website/  (publié par .github/workflows/pages.yml)
Usage :  python3 gh_build.py [URL_DU_SITE] [--no-minify]
"""
import hashlib, json, re, shutil, subprocess, sys, datetime
from pathlib import Path
from bs4 import BeautifulSoup
import docs_embed

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (ARGS[0] if ARGS else "https://bulls64.github.io/Streamlink-Launcher/").rstrip("/") + "/"
BASE_PATH = "/" + BASE.split("://", 1)[1].split("/", 1)[1]           # ex. /Streamlink-Launcher/
TODAY = datetime.date.today().isoformat()
here = Path(__file__).parent
OUT = here.parent / "website"
FONTS = here / "node_modules" / "@fontsource"
read = lambda n: (here / n).read_text(encoding="utf-8")

LANGS = ("fr", "en", "es", "de", "it")                         # le français est la langue par défaut (à la racine)
PATHS = {("home", l): ("" if l == "fr" else f"{l}/") for l in LANGS}
PATHS.update({("docs", l): ("docs/" if l == "fr" else f"{l}/docs/") for l in LANGS})
def up(cur): return "../" * cur.count("/")                    # chemin relatif vers la racine du site
def link(cur, kind, lang, frag=""): return (up(cur) + PATHS[(kind, lang)] or "./") + frag
def absu(kind, lang): return BASE + PATHS[(kind, lang)]

# Google Search Console, propriété « Préfixe de l'URL » (validation par balise HTML)
GOOGLE_SITE_VERIFICATION = "CNNycSFV-w4cvtyv4_P8k8AITTl89dwfBTBh9jasFlM"

LAUNCHER, CHAT = "1.5.1", "0.2.1"
META = {
    ("home", "fr"): ("Streamlink Launcher & Chat : Twitch et Kick dans VLC ou mpv",
                     "Applis libres pour Windows et Linux : regarde Twitch, Kick, YouTube et Steam TV dans VLC, mpv ou PotPlayer, avec les chats dans une fenêtre à part."),
    ("home", "en"): ("Streamlink Launcher & Chat: Twitch and Kick in VLC or mpv",
                     "Free apps for Windows and Linux: watch Twitch, Kick, YouTube and Steam TV in VLC, mpv or PotPlayer, with the chats in a separate window."),
    ("docs", "fr"): ("Documentation · Streamlink Launcher & Chat",
                     "Installer Streamlink, lancer un premier stream, écrire dans le chat Twitch ou Kick, raccourcis, réglages et dépannage : le guide complet des deux applis."),
    ("docs", "en"): ("Documentation · Streamlink Launcher & Chat",
                     "Install Streamlink, open your first stream, write in Twitch or Kick chat, shortcuts, settings and troubleshooting: the complete guide to both apps."),
    ("home", "es"): ("Streamlink Launcher y Chat: Twitch y Kick en VLC o mpv",
                     "Aplicaciones libres para Windows y Linux: mira Twitch, Kick, YouTube y Steam TV en VLC, mpv o PotPlayer, con los chats en una ventana aparte."),
    ("docs", "es"): ("Documentación · Streamlink Launcher y Chat",
                     "Instalar Streamlink, abrir tu primer stream, escribir en el chat de Twitch o Kick, atajos, ajustes y solución de problemas: la guía completa de las dos aplicaciones."),
    ("home", "de"): ("Streamlink Launcher & Chat: Twitch und Kick in VLC oder mpv",
                     "Freie Apps für Windows und Linux: Twitch, Kick, YouTube und Steam TV in VLC, mpv oder PotPlayer ansehen, mit den Chats in einem eigenen Fenster."),
    ("docs", "de"): ("Dokumentation · Streamlink Launcher & Chat",
                     "Streamlink installieren, den ersten Stream öffnen, im Twitch- oder Kick-Chat schreiben, Tastenkürzel, Einstellungen und Fehlerbehebung: das vollständige Handbuch der beiden Apps."),
    ("home", "it"): ("Streamlink Launcher e Chat: Twitch e Kick in VLC o mpv",
                     "App libere per Windows e Linux: guarda Twitch, Kick, YouTube e Steam TV in VLC, mpv o PotPlayer, con le chat in una finestra a parte."),
    ("docs", "it"): ("Documentazione · Streamlink Launcher e Chat",
                     "Installare Streamlink, aprire il primo stream, scrivere nella chat di Twitch o Kick, scorciatoie, impostazioni e risoluzione dei problemi: la guida completa delle due app."),
}
OG_ALT = {"fr": "Streamlink Launcher et Streamlink Chat : le live sort du navigateur.", "en": "Streamlink Launcher and Streamlink Chat: live, minus the browser.",
          "es": "Streamlink Launcher y Streamlink Chat: el directo, fuera del navegador.", "de": "Streamlink Launcher und Streamlink Chat: Live, aber ohne Browser.",
          "it": "Streamlink Launcher e Streamlink Chat: il live esce dal browser."}
IMG_DIR = {l: ("fr" if l == "fr" else "en") for l in LANGS}      # es, de, it : mêmes captures que l'anglais
LOCALE = {"fr": "fr_FR", "en": "en_US", "es": "es_ES", "de": "de_DE", "it": "it_IT"}

# ---------------------------------------------------------------- textes anglais du script du site
SCRIPT = read("site.js")
def js_object(name):
    i = SCRIPT.index(f"const {name} = ") + len(f"const {name} = ")
    j = SCRIPT.index("\n  };", i) + 4
    r = subprocess.run(["node", "-e", f"process.stdout.write(JSON.stringify({SCRIPT[i:j]}))"], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)
EN, T, HOME_TR, T_TR = js_object("EN"), js_object("T"), js_object("HOME_TR"), js_object("T_TR")
DICT = {"en": EN, **{l: {**EN, **HOME_TR[l]} for l in HOME_TR}}          # textes de l'accueil par langue (le français est dans la page)
TT = {"en": T["en"], **{l: {**T["en"], **T_TR[l]} for l in T_TR}}        # textes produits par le script (placeholders, alt…)

# ---------------------------------------------------------------- morceaux de page
CSS = read("site.css")
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

def font_css(fonts):
    """Les @font-face, avec l'adresse du dossier des polices vue depuis le fichier CSS."""
    faces = FONT_FACES
    return "".join(f'@font-face {{ font-family: "{fam}"; font-style: {st}; font-weight: {w}; font-display: swap; '
                   f'src: url("{fonts}{slug}-latin-{w}-{st}.woff2") format("woff2"); }}\n' for fam, slug, w, st in faces)

def translate(html, lang):
    """Pré-rend un morceau de page dans la langue voulue (attributs data-i18n du site)."""
    if lang == "fr": return html
    D, TL = DICT[lang], TT[lang]
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("[data-i18n]"):
        v = D.get(el["data-i18n"])
        if v is not None: el.clear(); el.append(BeautifulSoup(v, "html.parser"))
    for el in soup.select("[data-i18n-aria]"):
        v = D.get(el["data-i18n-aria"])
        if v is not None: el["aria-label"] = v
    for el in soup.select("[data-i18n-alt]"):
        v = D.get(el["data-i18n-alt"])
        if v is not None: el["alt"] = v
    shot = soup.select_one("#shot")
    if shot: shot["alt"] = TL["alt"]["l_main"]
    q = soup.select_one("#q")
    if q: q["placeholder"] = TL["ph"]["twitch"]
    say = soup.select_one("#say")
    if say: say["placeholder"] = TL["ch"]["twitch"][1]
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
    for l in LANGS:
        h = h.replace(f'<option value="{l}" lang="{l}">', f'<option value="{l}" lang="{l}"' + (' selected' if lang == l else '') + '>')
    return translate(h, lang)

# ---------------------------------------------------------------- données structurées
AUTHOR = {"@type": "Person", "@id": BASE + "#author", "name": "Bulls64", "url": "https://github.com/Bulls64"}
APP_DESC = {
    "Launcher": {
        "fr": "Interface légère pour Streamlink : ouvre Twitch, Kick, YouTube, Dailymotion et Steam TV dans VLC, mpv ou PotPlayer, avec favoris en direct et mode mini.",
        "en": "Lightweight interface for Streamlink: opens Twitch, Kick, YouTube, Dailymotion and Steam TV in VLC, mpv or PotPlayer, with live favorites and a mini mode.",
        "es": "Interfaz ligera para Streamlink: abre Twitch, Kick, YouTube, Dailymotion y Steam TV en VLC, mpv o PotPlayer, con favoritos en directo y modo mini.",
        "de": "Schlanke Oberfläche für Streamlink: öffnet Twitch, Kick, YouTube, Dailymotion und Steam TV in VLC, mpv oder PotPlayer, mit Live-Favoriten und Mini-Modus.",
        "it": "Interfaccia leggera per Streamlink: apre Twitch, Kick, YouTube, Dailymotion e Steam TV in VLC, mpv o PotPlayer, con preferiti in diretta e modalità mini."},
    "Chat": {
        "fr": "Chats Twitch, Kick et Steam TV dans une seule fenêtre, un onglet par chaîne, lecture sans compte et écriture après connexion.",
        "en": "Twitch, Kick and Steam TV chats in one window, one tab per channel, read without an account and write once logged in.",
        "es": "Los chats de Twitch, Kick y Steam TV en una sola ventana, una pestaña por canal; lectura sin cuenta y escritura tras iniciar sesión.",
        "de": "Die Chats von Twitch, Kick und Steam TV in einem Fenster, ein Tab pro Kanal; Lesen ohne Konto, Schreiben nach der Anmeldung.",
        "it": "Le chat di Twitch, Kick e Steam TV in un'unica finestra, una scheda per canale; lettura senza account e scrittura dopo l'accesso."},
}
def apps(lang):
    def app(name, ver, repo, desc, shot):
        return {"@type": "SoftwareApplication", "name": name, "softwareVersion": ver,
                "applicationCategory": "MultimediaApplication", "operatingSystem": "Windows 10, Windows 11, Linux",
                "description": desc, "url": absu("home", lang) + ("#launcher" if "Launcher" in name else "#chat"),
                "downloadUrl": f"https://github.com/Bulls64/{repo}/releases/latest",
                "screenshot": BASE + f"assets/img/site/{IMG_DIR[lang]}/{shot}.webp",
                "license": "https://opensource.org/licenses/MIT", "isAccessibleForFree": True,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                "author": {"@id": BASE + "#author"}, "sameAs": f"https://github.com/Bulls64/{repo}", "inLanguage": list(LANGS)}
    return [
        app("Streamlink Launcher", LAUNCHER, "Streamlink-Launcher", APP_DESC["Launcher"][lang], "l_main"),
        app("Streamlink Chat", CHAT, "Streamlink-Chat", APP_DESC["Chat"][lang], "c_tw"),
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
    site = {"@type": "WebSite", "@id": BASE + "#website", "url": BASE, "name": "Streamlink Launcher & Chat", "inLanguage": list(LANGS), "publisher": {"@id": BASE + "#author"}}
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
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">\n' + data.replace("</", "<\\/") + "\n</script>"

def head(cur, kind, lang, extra_css="", content=None):
    title, desc = META[(kind, lang)]
    alt_locales = "".join(f'<meta property="og:locale:alternate" content="{LOCALE[l]}">\n' for l in LANGS if l != lang)
    hreflangs = "".join(f'<link rel="alternate" hreflang="{l}" href="{absu(kind, l)}">\n' for l in LANGS)
    p = up(cur)
    styles = f'<link rel="stylesheet" href="{p}{asset("css/site.css", font_css("../fonts/") + CSS)}">'
    if extra_css: styles += f'\n<link rel="stylesheet" href="{p}{asset("css/docs.css", extra_css)}">'
    esc = lambda s: s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return f"""<!doctype html>
<html lang="{lang}"{' class="nointro static"' if kind == "docs" else ''}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="Bulls64">
<meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">
<link rel="canonical" href="{absu(kind, lang)}">
{hreflangs}<link rel="alternate" hreflang="x-default" href="{absu(kind, 'fr')}">
<meta property="og:type" content="{'website' if kind == 'home' else 'article'}">
<meta property="og:site_name" content="Streamlink Launcher &amp; Chat">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{absu(kind, lang)}">
<meta property="og:locale" content="{LOCALE[lang]}">
{alt_locales.rstrip()}
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
{styles}
</head>
<body>
"""

# ---------------------------------------------------------------- scripts
def lang_switch_js(cur, kind):
    """Le menu de langue mène à la page de l'autre langue (même section quand c'est possible)."""
    alt = {l: link(cur, kind, l) for l in LANGS}
    idmap = {}                                       # ancre de la rubrique -> ancre de la même rubrique dans chaque langue
    if kind == "docs":
        ids = {l: re.findall(r'<section class="doc" id="([^"]+)"', read(f"content_{l}.html")) for l in LANGS}
        assert all(len(v) == len(ids["fr"]) for v in ids.values()), {l: len(v) for l, v in ids.items()}
        for i in range(len(ids["fr"])):
            same = {l: ids[l][i] for l in LANGS}
            for a in sorted(set(same.values())):
                assert idmap.get(a, same) == same, f"ancre ambiguë : {a}"
                idmap[a] = same
    return ("window.SL_PAGES = " + json.dumps({"alt": alt, "ids": idmap}, ensure_ascii=False) + ";\n"
            "function slGoLang(l) {\n"
            "  try { localStorage.setItem(\"slSiteLang\", l); } catch {}\n"
            "  let id = \"\"; try { id = decodeURIComponent(location.hash.slice(1)); } catch {}\n"
            "  const target = (SL_PAGES.ids[id] && SL_PAGES.ids[id][l]) || (id && document.getElementById(id) && !Object.keys(SL_PAGES.ids).length ? id : \"\");\n"
            "  location.href = SL_PAGES.alt[l] + (target ? \"#\" + target : \"\");\n"
            "}\n")

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
    # Page pré-rendue dans une seule langue : les dictionnaires, la copie des textes français
    # et leur réapplication au chargement ne servent plus (le HTML est déjà dans la bonne langue).
    extra = ""                                   # es, de, it : leurs textes du script, fusionnés avec les anglais
    if lang not in ("fr", "en"):
        extra = f'  T["{lang}"] = Object.assign({{}}, T.en, {lang_block(s, "  const T_TR = {", lang)});\n'
    cut("  const EN = {", "  /* textes produits par le script */")
    sub("    const d = DICT[l];\n", "")
    s = re.sub(r"    document\.querySelectorAll\(\"\[data-i18n(?:-aria|-alt)?\]\"\)\.forEach\(el => \{ const v = d\[.*?\n", "", s)
    assert "DICT" not in s and "const EN" not in s
    s = keep_lang(s, "  const T = {", lang if lang in ("fr", "en") else "en", "{")
    s = re.sub(r"  for \(const l in T_TR\) \{.*?\}\n", lambda m: extra, s, count=1, flags=re.S)
    assert "T_TR" not in s and "HOME_TR" not in s
    sub('  let lang = "fr";', "  let lang = document.documentElement.lang;")
    imgs = {l: {k: f"{up(cur)}assets/img/site/{l}/{k}.webp" for k in ("l_main", "l_mini", "l_set", "l_light", "c_tw", "c_kick", "c_light")} for l in ("fr", "en")}
    imgs = {l: imgs[IMG_DIR[l]] for l in LANGS}
    return s.replace("{{IMG_JSON}}", json.dumps({lang: imgs[lang]})), imgs

def lang_spans(s, start, opener):
    """Dans un objet { fr: …, en: …, es: … } du script : (début de l'objet, fin, {langue: (début, fin)})."""
    i = s.index(start)
    end = s.index("\n  };", i)
    pos = {l: s.index(f"\n    {l}: {opener}", i) for l in LANGS if 0 <= s.find(f"\n    {l}: {opener}", i) < end}
    order = sorted(pos.values()) + [end]
    return i, end, {l: (p, order[order.index(p) + 1]) for l, p in pos.items()}

def keep_lang(s, start, lang, opener):
    """Dans un objet { fr: …, en: …, es: … } du script, ne garde que la langue de la page."""
    _, end, spans = lang_spans(s, start, opener)
    first = min(a for a, _ in spans.values())
    a, b = spans[lang]
    return s[:first] + s[a:b] + s[end:]

def lang_block(s, start, lang):
    """Le texte { … } d'une langue dans un objet du script (sans la virgule finale)."""
    _, _, spans = lang_spans(s, start, "{")
    a, b = spans[lang]
    return s[a:b].split(": ", 1)[1].strip().rstrip(",")

def docs_script(lang):
    s = read("docs.js")
    # une seule langue par page : pas de copie du contenu pour changer de langue sur place
    for a, b in [('  const HTML = { fr: root.innerHTML, en: document.getElementById("doc-en").innerHTML };\n  let shownLang = "fr";\n', ""),
                 ('    if (l !== shownLang) { root.innerHTML = HTML[l]; shownLang = l; }\n', ""),
                 ('  return { setLang: apply, langFor, refresh: spy };', '  return { setLang: apply, refresh: spy };'),
                 ('} else if (visible() && location.hash && location.hash !== "#docs") {', '} else if (keepPlace && location.hash) {')]:
        assert a in s, a; s = s.replace(a, b)
    s = re.sub(r"  /\* langue d'une ancre.*?\n  \}\n", "", s, count=1, flags=re.S)
    assert "HTML" not in s and "langFor" not in s
    s = keep_lang(s, "  const STR = {", lang, "{")
    s = keep_lang(s, "  const SYN = {", lang, "[")
    theme = SCRIPT[SCRIPT.index("  /* ---------- thème clair / sombre"):SCRIPT.index("  /* ---------- onglet Docs")]
    return s + f"""
(() => {{
  const root = document.documentElement, lang = root.lang;
{theme}  drawTheme();
  const sel = document.getElementById("lang");
  sel.value = lang;
  sel.addEventListener("change", () => slGoLang(sel.value));
  SLDocs.setLang(lang, false);
  if (location.hash) {{ const t = document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) t.scrollIntoView({{ behavior: "instant" }}); }}
}})();
"""

# ---------------------------------------------------------------- pages
def build_home(lang):
    cur = PATHS[("home", lang)]
    js, imgs = home_script(cur, lang)
    main = re.sub(r"\{\{img:(\w+):(\w+)\}\}", lambda m: imgs[lang][m.group(2)], MAIN)
    main = main.replace('<figure><img data-img=', '<figure><img loading="lazy" decoding="async" data-img=')
    body = SVG_DEFS + "\n\n" + BOOT + header(cur, "home", lang) + "\n\n" + translate(main, lang) + "\n" + translate(FOOTER, lang) + "\n"
    return head(cur, "home", lang) + body + script_tag(cur, f"js/home.{lang}.js", lang_switch_js(cur, "home") + js) + "</body>\n</html>\n"

def build_docs(lang):
    cur = PATHS[("docs", lang)]
    content = docs_embed.content(f"content_{lang}.html")
    content = re.sub(r'src="img/(en/)?([^"]+\.webp)"', lambda m: f'src="{up(cur)}assets/img/docs/{"en/" if m.group(1) else ""}{m.group(2)}" decoding="async"', content)
    view = ('<div id="docs" class="docs-view">\n<main id="docroot">\n' + content + '</main>\n'
            '<dialog class="lb" id="lb"><button type="button">×</button><img alt=""><p></p></dialog>\n</div>\n')
    body = SVG_DEFS + "\n\n" + header(cur, "docs", lang) + "\n\n" + view + "\n" + translate(FOOTER, lang) + "\n"
    return head(cur, "docs", lang, docs_embed.css(), content) + body + script_tag(cur, f"js/docs.{lang}.js", lang_switch_js(cur, "docs") + docs_script(lang)) + "</body>\n</html>\n"

MINIFY = "--no-minify" not in sys.argv
ESBUILD = here / "node_modules" / ".bin" / "esbuild"

def minify_js(js):
    """Minifie un fichier JavaScript du site. Sources lisibles : website-src/."""
    if not MINIFY: return js
    r = subprocess.run([str(ESBUILD), "--minify", "--target=es2020", "--loader=js", "--log-level=warning"],
                       input=js, capture_output=True, text=True, check=True)
    return r.stdout

ASSETS = {}                                      # fichiers CSS et JS à écrire : chemin sous assets/ -> contenu

def asset(name, text):
    """Enregistre un fichier CSS ou JS et renvoie son adresse, avec une empreinte du contenu (?v=…)
    pour que les navigateurs prennent la nouvelle version après chaque publication."""
    assert ASSETS.get(name, text) == text, f"{name} : deux contenus différents"
    ASSETS[name] = text
    return f"assets/{name}?v={hashlib.sha256(text.encode()).hexdigest()[:10]}"

def script_tag(cur, name, js):
    return f'<script src="{up(cur)}{asset(name, minify_js(js))}"></script>\n'


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
        for lang in LANGS:
            alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{absu(kind, l)}"/>' for l in LANGS)
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
    for name, text in ASSETS.items():               # CSS et JS, à part du HTML
        f = OUT / "assets" / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text, encoding="utf-8")
    print("ok", BASE, sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) // 1024, "Ko")

CSS_404 = """@font-face { font-family: "Big Shoulders Display"; font-weight: 900; font-display: swap; src: url("../fonts/big-shoulders-display-latin-900-normal.woff2") format("woff2"); }
@font-face { font-family: "Instrument Sans"; font-weight: 400; font-display: swap; src: url("../fonts/instrument-sans-latin-400-normal.woff2") format("woff2"); }
@font-face { font-family: "Instrument Sans"; font-weight: 600; font-display: swap; src: url("../fonts/instrument-sans-latin-600-normal.woff2") format("woff2"); }
:root { --bg: #E9ECF1; --surface: #F7F8FA; --ink: #13151B; --muted: #586071; --line: #CDD2DB; --accent: #6E2BD9; }
@media (prefers-color-scheme: dark) { :root { --bg: #0F1116; --surface: #161920; --ink: #ECEEF3; --muted: #959CAD; --line: #2A2F3A; --accent: #B794FF; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--ink); font-family: "Instrument Sans", "Segoe UI", system-ui, sans-serif; line-height: 1.6; padding: 24px 16px; }
main { max-width: 560px; display: grid; gap: 14px; }
.code { font-family: "IBM Plex Mono", Consolas, monospace; font-size: .8rem; letter-spacing: .2em; color: var(--muted); }
h1 { font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; text-transform: uppercase; font-size: clamp(2.6rem, 11vw, 4.6rem); line-height: .9; margin: 0; }
p { margin: 0; color: var(--muted); }
nav { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
nav a { color: var(--ink); text-decoration: none; font-weight: 600; background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 7px 14px; }
nav a:hover { border-color: var(--accent); }
"""

def page_404():
    b = BASE_PATH
    asset404 = asset("css/404.css", CSS_404)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page introuvable · Streamlink Launcher &amp; Chat</title>
<meta name="robots" content="noindex">
<link rel="icon" href="{b}favicon.ico" sizes="32x32">
<link rel="icon" href="{b}assets/icons/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{b}{asset404}">
</head>
<body>
<main>
  <div class="code">CH 404 · NO SIGNAL</div>
  <h1>Pas de signal</h1>
  <p>Cette page n'existe pas ou a changé d'adresse. <span lang="en">This page doesn't exist or has moved.</span></p>
  <nav>
    <a href="{b}">Accueil</a><a href="{b}docs/">Documentation</a>
    <a href="{b}en/" lang="en">Home (English)</a><a href="{b}en/docs/" lang="en">Docs (English)</a>
    <a href="{b}es/" lang="es">Inicio (Español)</a><a href="{b}de/" lang="de">Startseite (Deutsch)</a><a href="{b}it/" lang="it">Home (Italiano)</a>
  </nav>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    build()
