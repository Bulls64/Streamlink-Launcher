# Sources du site

`gh_build.py` génère `../website/` (10 pages pré-rendues : accueil et documentation en français, anglais, espagnol, allemand et italien ; sitemap, robots.txt, 404…), publié par
`.github/workflows/pages.yml`. Ne modifie pas `website/` à la main : il est reconstruit à chaque génération.

Le HTML généré ne contient ni CSS ni JavaScript : les styles vont dans `assets/css/` (`site.css`, `docs.css`, `404.css`),
les scripts dans `assets/js/` (un fichier par page, minifié), appelés avec une empreinte `?v=…` qui change avec leur contenu.
Seules les données structurées (JSON-LD) restent dans la page.

| Fichier | Rôle |
|---|---|
| `content_fr.html`, `content_en.html`, `content_es.html`, `content_de.html`, `content_it.html` | le texte de la documentation, une langue par fichier (mêmes rubriques, dans le même ordre) |
| `site_body.html`, `site.css`, `site.js` | l'accueil : HTML, styles, script (démo ; le français est dans la page, les autres langues dans le script) |
| `docs.css`, `docs.js`, `docs_embed.py` | les styles et le script de la doc, et leur intégration au site |
| `site_head.html`, `shell_head.html` | en-têtes de l'artefact d'origine (polices, liens vers `site.css` et `docs.css`) ; pas utilisés par `gh_build.py` |
| `img/` | captures (accueil dans `img/site/{fr,en}`, doc dans `img/` et `img/en` ; l'espagnol, l'allemand et l'italien réutilisent les captures anglaises) |
| `gh_assets/` | icônes et images de partage (refaites par `make_assets.mjs`) |

## Générer

    pip install -r requirements.txt
    npm install                      # polices @fontsource (et Playwright pour make_assets.mjs)
    python3 gh_build.py              # https://bulls64.github.io/Streamlink-Launcher/
    python3 gh_build.py https://exemple.fr/   # ou avec un domaine à toi

Les adresses absolues (canonical, hreflang, sitemap, Open Graph, JSON-LD, 404) suivent l'URL donnée.

Pour refaire les icônes et les images de partage : `npx playwright install chromium && node make_assets.mjs`
(`ONLY=home-es,docs-es node make_assets.mjs` ne refait que les images de partage nommées)
(Playwright cherche Chromium là où il l'installe ; ou donne son chemin avec la variable `CHROMIUM`).
