# Contributing · Contribuer

## English

Thanks for helping! Bug reports, translations and pull requests are welcome.

1. **Open an issue first** for anything bigger than a small fix, so we can agree on the approach.
2. **Setup**: Python 3.10+ and nothing else (no third-party dependency). Tkinter is needed to run the interface.
3. **Run the checks** before opening a pull request:
   ```
   python -m unittest discover -s tests -v     # logic tests (no display needed)
   python -m pip install ruff && python -m ruff check .
   xvfb-run -a python -m unittest tests.test_gui   # GUI smoke test (Linux; skipped without a display)
   ```
4. **Translations** live in `lang/*.json`. Every language must have exactly the same keys (a test checks it). Keep texts short: they sit in fixed-size cards.
5. **Rules of the code base**: Windows/OLE callbacks never touch Tk (they push events to a queue); slow work goes through `App.run_in_thread`; `launcher/core.py` stays free of any UI.
6. **Changelog**: add a line under *Unreleased* in `CHANGELOG.md`, in both English and French.
7. Releases are cut by the maintainer (version in `launcher/__init__.py` and `packaging/version_info.txt`, then a `vX.Y.Z` tag).

## Français

Merci d'aider ! Signalements de bugs, traductions et pull requests sont les bienvenus.

1. **Ouvrez d'abord un ticket** pour tout ce qui dépasse un petit correctif.
2. **Environnement** : Python 3.10+ et rien d'autre (aucune dépendance tierce). Tkinter est nécessaire pour l'interface.
3. **Lancez les vérifications** avant la pull request (commandes ci-dessus).
4. **Traductions** : `lang/*.json`, mêmes clés dans toutes les langues (un test le vérifie). Textes courts : ils tiennent dans des cartes de taille fixe.
5. **Règles du code** : les rappels Windows/OLE ne touchent jamais Tk (ils déposent des événements dans une file) ; le travail lent passe par `App.run_in_thread` ; `launcher/core.py` ne contient aucune interface.
6. **Journal des modifications** : une ligne sous *Unreleased* dans `CHANGELOG.md`, en anglais et en français.
7. Les versions sont publiées par le mainteneur (version dans `launcher/__init__.py` et `packaging/version_info.txt`, puis un tag `vX.Y.Z`).
