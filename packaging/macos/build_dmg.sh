#!/usr/bin/env bash
# Construit l'application macOS (.app) et son image disque (.dmg), sur un Mac Apple Silicon (arm64).
# PyInstaller embarque Python et Tcl/Tk ; l'app est signée ad hoc (pas de certificat Apple Developer) : au premier
# lancement, macOS demande de l'autoriser (Réglages Système › Confidentialité et sécurité › Ouvrir quand même).
#
# Builds the macOS application (.app) and its disk image (.dmg), on an Apple Silicon Mac (arm64).
# PyInstaller embeds Python and Tcl/Tk; the app is ad-hoc signed (no Apple Developer certificate): on first
# launch, macOS asks to allow it (System Settings › Privacy & Security › Open Anyway).
#
# Usage (depuis la racine du dépôt / from the repository root): bash packaging/macos/build_dmg.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

NAME="Streamlink Launcher"
FILE=StreamlinkLauncher
BUNDLE_ID=io.github.bulls64.StreamlinkLauncher
ENTRY=slink_launcher.py
ICON=packaging/appimage/streamlink-launcher.png
CATEGORY=public.app-category.video
DATA=(--add-data "lang:lang" --add-data "launcher/app.ico:launcher")
VERSION=$(python3 -c "import launcher; print(launcher.__version__)")
ARCH=$(uname -m)

[ "$(uname -s)" = Darwin ] || { echo "À lancer sur macOS / Run on macOS" >&2; exit 1; }
python3 -c "import tkinter; tkinter.Tcl()" || { echo "Ce Python n'a pas tkinter / This Python has no tkinter" >&2; exit 1; }
python3 -m pip install -q -r packaging/requirements-build.txt -r packaging/macos/requirements-macos.txt

rm -rf build "dist/$NAME.app"
# --windowed : un .app sans terminal ; --onedir (par défaut) : démarrage rapide, recommandé sur macOS
# --windowed: an .app without a terminal; --onedir (default): fast start, recommended on macOS
python3 -m PyInstaller --noconfirm --clean --windowed --noupx \
    --name "$NAME" --icon "$ICON" --osx-bundle-identifier "$BUNDLE_ID" "${DATA[@]}" \
    --exclude-module unittest --exclude-module doctest --exclude-module pydoc_data --exclude-module lib2to3 \
    "$ENTRY"

APP="dist/$NAME.app"
PLIST="$APP/Contents/Info.plist"
# plutil -replace : remplace la clé, ou l'ajoute / replaces the key, or adds it
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
plutil -replace NSHumanReadableCopyright -string "Bulls64 - MIT License" "$PLIST"
plutil -replace NSHighResolutionCapable -bool YES "$PLIST"
plutil -replace LSApplicationCategoryType -string "$CATEGORY" "$PLIST"
# Info.plist modifié : nouvelle signature ad hoc de tout le bundle / Info.plist changed: new ad-hoc signature
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

DMG="dist/$FILE-$VERSION-macOS-$ARCH.dmg"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # glisser l'app sur ce raccourci / drag the app onto this shortcut
rm -f "$DMG"
hdiutil create -quiet -volname "$NAME $VERSION" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
echo "Image disque : $DMG ($(du -h "$DMG" | cut -f1))"
