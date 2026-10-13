"""Génère les fichiers de manifeste winget (Windows Package Manager) d'une release GitHub.

Usage :  python packaging/winget/make_manifest.py 1.4.0 [dossier_de_sortie]

Lit la release publiée (adresse et SHA-256 de l'exécutable donnés par l'API GitHub), puis écrit trois
fichiers YAML dans  <sortie>/manifests/b/Bulls64/StreamlinkLauncher/<version>/  prêts à être copiés
dans un fork de https://github.com/microsoft/winget-pkgs (voir packaging/winget/README.md).
Aucune dépendance : bibliothèque standard uniquement.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = "Bulls64/Streamlink-Launcher"
IDENT = "Bulls64.StreamlinkLauncher"
SCHEMA = "1.6.0"


def release_asset(version):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/v{version}",
                                 headers={"User-Agent": "streamlink-launcher-winget"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    name = f"StreamlinkLauncher-{version}.exe"
    for a in data.get("assets", []):
        m = re.fullmatch(r"sha256:([0-9a-f]{64})", a.get("digest") or "")
        if a.get("name") == name and m:
            return a["browser_download_url"], m.group(1).upper(), data.get("published_at", "")[:10]
    sys.exit(f"{name} (avec son SHA-256) est introuvable dans la release v{version}")


def manifests(version, url, sha256, date):
    head = f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{{kind}}.{SCHEMA}.schema.json\n"
    version_yaml = (head.format(kind="version") + f"PackageIdentifier: {IDENT}\nPackageVersion: {version}\n"
                    f"DefaultLocale: en-US\nManifestType: version\nManifestVersion: {SCHEMA}\n")
    installer_yaml = (head.format(kind="installer") + f"""PackageIdentifier: {IDENT}
PackageVersion: {version}
InstallerType: portable
Commands:
- streamlink-launcher
ReleaseDate: {date}
Installers:
- Architecture: x64
  InstallerUrl: {url}
  InstallerSha256: {sha256}
ManifestType: installer
ManifestVersion: {SCHEMA}
""")
    locale_yaml = (head.format(kind="defaultLocale") + f"""PackageIdentifier: {IDENT}
PackageVersion: {version}
PackageLocale: en-US
Publisher: Bulls64
PublisherUrl: https://github.com/Bulls64
PublisherSupportUrl: https://github.com/{REPO}/issues
PackageName: Streamlink Launcher
PackageUrl: https://github.com/{REPO}
License: MIT
LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE
ShortDescription: Graphical launcher for Streamlink (Twitch, Kick, YouTube and more), with favorites, live checks and a mini mode.
Description: Streamlink Launcher is a Tkinter interface for Streamlink. It launches streams from a channel name or a link, keeps favorites and history, notifies you when a favorite goes live, and updates itself from GitHub releases. Streamlink must be installed separately.
Moniker: streamlink-launcher
Tags:
- streamlink
- twitch
- kick
- youtube
- streaming
- launcher
ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/v{version}
ManifestType: defaultLocale
ManifestVersion: {SCHEMA}
""")
    return {f"{IDENT}.yaml": version_yaml, f"{IDENT}.installer.yaml": installer_yaml,
            f"{IDENT}.locale.en-US.yaml": locale_yaml}


def main():
    if len(sys.argv) < 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit(__doc__)
    version = sys.argv[1]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "winget-out") / "manifests" / "b" / "Bulls64" / "StreamlinkLauncher" / version
    out.mkdir(parents=True, exist_ok=True)
    url, sha, date = release_asset(version)
    for name, text in manifests(version, url, sha, date).items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Manifestes écrits dans {out}")


if __name__ == "__main__":
    main()
