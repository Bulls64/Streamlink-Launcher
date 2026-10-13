"""Affiche les notes d'une version, en anglais puis en français, extraites de CHANGELOG.md.

Usage : python packaging/release_notes.py 1.4.2
"""
import re
import sys
from pathlib import Path

version = sys.argv[1]
text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
pattern = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |^---|^\[)", re.M | re.S)
sections = [m.group(1).strip() for m in pattern.finditer(text)]
if not sections:
    sys.exit(f"Version {version} introuvable dans CHANGELOG.md")
titles = ["English", "Français"]
out = []
for title, body in zip(titles, sections):
    out.append(f"## {title}\n\n{body}")
sys.stdout.reconfigure(encoding="utf-8")
print("\n\n".join(out))
