#!/usr/bin/env bash
# Construit StreamlinkLauncher-<version>-x86_64.AppImage (Linux).
#
# Contenu : un Python autonome (python-build-standalone) + le lanceur. Aucune dépendance sur le Python
# du système. Streamlink et le lecteur vidéo restent ceux installés sur la machine.
#
# Tcl/Tk est recompilé avec Xft : celui de python-build-standalone n'a que les polices X11 de base
# (texte non lissé, sans les polices du système). Même version que la sienne, pour rester compatible
# avec son module _tkinter. Il faut donc les paquets de développement (Debian/Ubuntu) :
#   build-essential libx11-dev libxft-dev libxss-dev libfontconfig-dev patchelf
# Compilé sur Ubuntu 22.04 (CI), l'AppImage fonctionne avec la glibc 2.35 et plus récente.
#
# Usage (depuis la racine du dépôt) :  bash packaging/appimage/build_appimage.sh [dossier_de_sortie]
# Les téléchargements sont épinglés (version + SHA-256) et mis en cache dans packaging/appimage/.cache.
set -euo pipefail

PBS_TAG=20261013
PBS_FILE="cpython-3.12.15+${PBS_TAG}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PBS_SHA256=178d3d83b6e8e99285a65d3fce9c16b87952cc5efdb4d1a0e3ff3be18ff0fc9c
TOOL_VERSION=1.9.1
TOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
TCLTK_TAG=core-9-0-4                                   # = version de Tcl/Tk de python-build-standalone
TCL_COMMIT=c655b4770b1d6d32a8cbffd6cef59db6029fe19e
TK_COMMIT=584f8fcf62c320d7c341e77171188cb4d79c3725
RUNTIME_TAG=20251108
RUNTIME_SHA256=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/packaging/appimage"
OUT="${1:-$ROOT/dist}"
CACHE="$HERE/.cache"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/launcher/__init__.py")"
[ -n "$VERSION" ] || { echo "Version introuvable dans launcher/__init__.py" >&2; exit 1; }
APPDIR="$(mktemp -d)/StreamlinkLauncher.AppDir"
mkdir -p "$CACHE" "$OUT"

fetch() {  # fetch <url> <fichier> <sha256>
    local dest="$CACHE/$2"
    if [ ! -f "$dest" ] || ! echo "$3  $dest" | sha256sum -c --status; then
        echo "Téléchargement de $2"
        curl -fsSL --retry 3 -o "$dest.part" "$1"
        mv "$dest.part" "$dest"
    fi
    echo "$3  $dest" | sha256sum -c --quiet || { echo "SHA-256 inattendu pour $2" >&2; exit 1; }
}

fetch "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG/$PBS_FILE" "$PBS_FILE" "$PBS_SHA256"
fetch "https://github.com/AppImage/appimagetool/releases/download/$TOOL_VERSION/appimagetool-x86_64.AppImage" \
      "appimagetool-$TOOL_VERSION.AppImage" "$TOOL_SHA256"
fetch "https://github.com/AppImage/type2-runtime/releases/download/$RUNTIME_TAG/runtime-x86_64" \
      "runtime-$RUNTIME_TAG-x86_64" "$RUNTIME_SHA256"
chmod +x "$CACHE/appimagetool-$TOOL_VERSION.AppImage"
command -v patchelf >/dev/null || { echo "patchelf est nécessaire (apt install patchelf)" >&2; exit 1; }

# Tcl/Tk avec Xft (mis en cache : la compilation prend une à deux minutes)
TCLTK="$CACHE/tcltk-$TCLTK_TAG"
if [ ! -f "$TCLTK/lib/libtcl9tk9.0.so" ]; then
    rm -rf "$CACHE/src" "$TCLTK"
    for repo in tcl:$TCL_COMMIT tk:$TK_COMMIT; do
        name="${repo%%:*}" commit="${repo#*:}"
        git -c advice.detachedHead=false clone -q --depth 1 --branch "$TCLTK_TAG" \
            "https://github.com/tcltk/$name" "$CACHE/src/$name"
        [ "$(git -C "$CACHE/src/$name" rev-parse HEAD)" = "$commit" ] || { echo "Commit inattendu pour $name" >&2; exit 1; }
    done
    echo "Compilation de Tcl/Tk ($TCLTK_TAG, Xft)"
    (cd "$CACHE/src/tcl/unix" && ./configure -q --prefix="$TCLTK" --enable-shared --disable-symbols >/dev/null \
        && make -s -j"$(nproc)" >/dev/null && make -s install >/dev/null)
    (cd "$CACHE/src/tk/unix" && ./configure -q --prefix="$TCLTK" --with-tcl="$CACHE/src/tcl/unix" --enable-xft \
        --enable-shared --disable-symbols >/dev/null && make -s -j"$(nproc)" >/dev/null && make -s install >/dev/null)
    rm -rf "$CACHE/src"
fi

echo "Préparation de l'AppDir (version $VERSION)"
mkdir -p "$APPDIR/usr" "$APPDIR/usr/share/streamlink-launcher" \
         "$APPDIR/usr/share/applications" "$APPDIR/usr/share/metainfo" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
tar -xzf "$CACHE/$PBS_FILE" -C "$APPDIR/usr"          # -> usr/python
PY="$APPDIR/usr/python"
STDLIB="$(echo "$PY"/lib/python3.*)"
# Allègement : tests, IDLE, outils de développement, en-têtes C
rm -rf "$PY/include" "$PY/share" "$PY"/lib/pkgconfig "$STDLIB"/{test,idlelib,ensurepip,lib2to3,turtledemo,pydoc_data,venv} \
       "$STDLIB"/tkinter/test "$STDLIB"/site-packages/* "$PY"/bin/{idle3*,pydoc3*,pip*,2to3*}
find "$PY" -name "__pycache__" -type d -prune -exec rm -rf {} +
# Tcl/Tk avec Xft à la place de celui d'origine ; libXft et libXss sont fournies (petites, pas toujours
# installées), le reste (X11, fontconfig, freetype) vient du système, comme pour toute AppImage.
cp "$TCLTK/lib/libtcl9.0.so" "$TCLTK/lib/libtcl9tk9.0.so" "$PY/lib/"
for lib in libXft.so.2 libXss.so.1; do
    cp -L "$(ldconfig -p | awk -v l="$lib" '$1 == l && /x86-64/ {print $NF; exit}')" "$PY/lib/$lib"
done
for so in "$PY"/lib/libtcl9.0.so "$PY"/lib/libtcl9tk9.0.so "$PY"/lib/libXft.so.2 "$PY"/lib/libXss.so.1; do
    patchelf --set-rpath '$ORIGIN' "$so"
done

APP="$APPDIR/usr/share/streamlink-launcher"
cp -r "$ROOT/slink_launcher.py" "$ROOT/slink_chat.py" "$ROOT/launcher" "$ROOT/chat" "$ROOT/lang" "$ROOT/platforms.json" "$ROOT/LICENSE" "$APP/"
find "$APP" -name "__pycache__" -type d -prune -exec rm -rf {} +
# Pré-compilation (démarrage plus rapide ; le dossier de l'AppImage est en lecture seule)
"$PY/bin/python3" -E -s -m compileall -q -j 0 "$STDLIB" "$APP" >/dev/null

install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m 644 "$HERE/io.github.bulls64.StreamlinkLauncher.desktop" "$APPDIR/"
install -m 644 "$HERE/io.github.bulls64.StreamlinkLauncher.desktop" "$APPDIR/usr/share/applications/"
install -m 644 "$HERE/io.github.bulls64.StreamlinkLauncher.appdata.xml" "$APPDIR/usr/share/metainfo/"
install -m 644 "$HERE/streamlink-launcher.png" "$APPDIR/streamlink-launcher.png"
install -m 644 "$HERE/streamlink-launcher.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"
ln -s streamlink-launcher.png "$APPDIR/.DirIcon"

TARGET="$OUT/StreamlinkLauncher-$VERSION-x86_64.AppImage"
rm -f "$TARGET"
# --appimage-extract-and-run : appimagetool fonctionne aussi sans FUSE (conteneurs, CI)
ARCH=x86_64 "$CACHE/appimagetool-$TOOL_VERSION.AppImage" --appimage-extract-and-run --no-appstream \
    --runtime-file "$CACHE/runtime-$RUNTIME_TAG-x86_64" "$APPDIR" "$TARGET"
rm -rf "$(dirname "$APPDIR")"
echo "AppImage : $TARGET ($(du -h "$TARGET" | cut -f1))"
