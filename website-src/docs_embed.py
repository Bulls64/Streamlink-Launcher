"""docs_embed.py : transforme la doc (shell_head.html, content_fr/en.html) en section intégrable au site.
- CSS de la doc limité à #docs (rien ne déborde sur le reste du site) ;
- classes communes avec le site renommées en d-… ; recherche renommée dq (le site a déjà un #q)."""
import re
from pathlib import Path
here = Path(__file__).parent
read = lambda n: (here / n).read_text(encoding="utf-8")

SHARED = ["app", "card", "cm", "num", "pr", "shots", "steps", "tabs", "tbl", "term", "wrap"]
CLS_RE = re.compile(r"\.(" + "|".join(SHARED) + r")(?![\w-])")

def scope_sel(sel):
    sel = sel.strip()
    if sel in ("*", "html"): return None
    if sel == ":root": return "#docs"
    if sel.startswith(":root"): return sel + " #docs"
    if sel == "body": return "#docs"
    if sel.startswith(".js "): sel = sel[4:]
    return "#docs " + CLS_RE.sub(r".d-\1", sel)

def scope(css):
    out, i = [], 0
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    while True:
        j = css.find("{", i)
        if j < 0: break
        head = css[i:j].strip()
        if head.startswith("@media"):
            depth, k = 1, j + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(css[k], 0); k += 1
            inner = scope(css[j + 1:k - 1])
            if inner.strip(): out.append(f"{head} {{\n{inner}}}\n")
            i = k; continue
        k = css.index("}", j)
        sels = [s for s in (scope_sel(x) for x in head.split(",")) if s]
        if sels: out.append(", ".join(sels) + " {" + css[j + 1:k] + "}\n")
        i = k + 1
    return "".join(out)

def css():
    h = read("shell_head.html")
    c = h[h.index("<style>") + 7:h.index("/* Menu de langue")]
    # l'en-tête de la doc est remplacé par celui du site
    c = re.sub(r"\n\.top[^\n]*|\n\.brand[^\n]*|\n\.nav[^\n]*", "", c)
    return scope(c)

def content(name):
    c = read(name)
    c = c[:c.rindex("<footer>")].rstrip() + "\n"
    c = re.sub(r'class="([^"]*)"', lambda m: 'class="' + " ".join("d-" + x if x in SHARED else x for x in m.group(1).split()) + '"', c)
    return c.replace('id="q"', 'id="dq"').replace('for="q"', 'for="dq"')

def section():
    return ('<div id="docs" class="docs-view" hidden>\n<div id="docroot">\n' + content("content_fr.html")
            + '</div>\n<template id="doc-en">\n' + content("content_en.html") + '</template>\n'
            + '<dialog class="lb" id="lb"><button type="button">×</button><img alt=""><p></p></dialog>\n</div>\n')

if __name__ == "__main__":
    print(css()[:3000])
