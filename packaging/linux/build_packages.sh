#!/usr/bin/env bash
# Construit les paquets .deb et .rpm à partir de l'AppImage : même contenu (Python embarqué, Tcl/Tk avec Xft),
# installé dans /opt/<paquet>, avec la commande /usr/bin/<paquet>, l'entrée de menu, l'icône et la fiche AppStream.
# Outils : dpkg-deb (toujours présent sur Debian/Ubuntu) et rpmbuild (paquet « rpm » sur Debian/Ubuntu).
#
# Builds the .deb and .rpm packages from the AppImage: same content (embedded Python, Tcl/Tk with Xft),
# installed in /opt/<package>, with the /usr/bin/<package> command, the menu entry, the icon and the AppStream file.
# Tools: dpkg-deb (always on Debian/Ubuntu) and rpmbuild ("rpm" package on Debian/Ubuntu).
#
# Usage (depuis la racine du dépôt / from the repository root):
#   bash packaging/linux/build_packages.sh dist/StreamlinkLauncher-<version>-x86_64.AppImage [dossier_de_sortie]
set -euo pipefail

PKG=streamlink-launcher
ENTRY=slink_launcher.py
SUMMARY="Graphical launcher for Streamlink (Twitch, Kick, YouTube...)"
DESCRIPTION="Opens Twitch, Kick, YouTube and other streams in your video player with Streamlink:
favorites with live status, mini mode, history, viewing statistics, 5 languages.
Streamlink and a video player (mpv, VLC...) must be installed."
HOMEPAGE="https://github.com/Bulls64/Streamlink-Launcher"
# Bibliothèques du système utilisées par Tk (le reste est embarqué) / System libraries used by Tk (the rest is embedded)
DEB_DEPENDS="libc6 (>= 2.35), libx11-6, libxext6, libxrender1, libfontconfig1, libfreetype6"
RPM_REQUIRES="glibc >= 2.35, libX11, libXext, libXrender, fontconfig, freetype"
MAINTAINER="Bulls64 <bulls64@users.noreply.github.com>"
SECTION=video

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APPIMAGE="$(readlink -f "${1:?Usage: build_packages.sh <AppImage> [dossier]}")"
OUT="$(mkdir -p "${2:-$ROOT/dist}" && cd "${2:-$ROOT/dist}" && pwd)"
VERSION="$(basename "$APPIMAGE" | sed -n 's/.*-\([0-9][0-9.]*\)-x86_64\.AppImage$/\1/p')"
[ -n "$VERSION" ] || { echo "Version introuvable dans le nom de $APPIMAGE" >&2; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Extraction de $(basename "$APPIMAGE")"
(cd "$WORK" && "$APPIMAGE" --appimage-extract >/dev/null)
SRC="$WORK/squashfs-root"
[ -x "$SRC/usr/python/bin/python3" ] && [ -f "$SRC/usr/share/$PKG/$ENTRY" ] || { echo "AppImage inattendue" >&2; exit 1; }

# Arborescence installée / Installed tree
STAGE="$WORK/stage"
mkdir -p "$STAGE/opt/$PKG" "$STAGE/usr/bin" "$STAGE/usr/share"
cp -a "$SRC/usr/python" "$STAGE/opt/$PKG/python"
cp -a "$SRC/usr/share/$PKG" "$STAGE/opt/$PKG/app"
# Repère lu par l'appli : données dans ~/.config, jamais dans /opt / Marker read by the app: data in ~/.config, never in /opt
echo "$PKG $VERSION" > "$STAGE/opt/$PKG/app/.system-install"
cp -a "$SRC/usr/share/applications" "$SRC/usr/share/metainfo" "$SRC/usr/share/icons" "$STAGE/usr/share/"
mkdir -p "$STAGE/usr/share/doc/$PKG"
cp "$STAGE/opt/$PKG/app/LICENSE" "$STAGE/usr/share/doc/$PKG/copyright"
# -E : ignore PYTHONPATH/PYTHONHOME de l'utilisateur ; -s : ignore son site-packages (comme l'AppImage)
# -E: ignores the user's PYTHONPATH/PYTHONHOME; -s: ignores their site-packages (like the AppImage)
cat > "$STAGE/usr/bin/$PKG" <<SH
#!/bin/sh
exec /opt/$PKG/python/bin/python3 -E -s /opt/$PKG/app/$ENTRY "\$@"
SH
chmod 755 "$STAGE/usr/bin/$PKG"
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE/usr/share" -type f -exec chmod 644 {} +

# --- .deb
DEB="$WORK/deb"
cp -a "$STAGE" "$DEB"
mkdir -p "$DEB/DEBIAN"
SIZE=$(du -sk "$STAGE" | cut -f1)
{
    echo "Package: $PKG"
    echo "Version: $VERSION"
    echo "Architecture: amd64"
    echo "Maintainer: $MAINTAINER"
    echo "Installed-Size: $SIZE"
    echo "Depends: $DEB_DEPENDS"
    echo "Recommends: streamlink"
    echo "Section: $SECTION"
    echo "Priority: optional"
    echo "Homepage: $HOMEPAGE"
    echo "Description: $SUMMARY"
    echo "$DESCRIPTION" | sed 's/^/ /'
} > "$DEB/DEBIAN/control"
DEB_FILE="$OUT/${PKG}_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group -Zxz --build "$DEB" "$DEB_FILE" >/dev/null
echo "Paquet .deb : $DEB_FILE ($(du -h "$DEB_FILE" | cut -f1))"

# --- .rpm
command -v rpmbuild >/dev/null || { echo "rpmbuild est nécessaire (apt install rpm)" >&2; exit 1; }
TOP="$WORK/rpm"
mkdir -p "$TOP"/{BUILD,RPMS,SPECS,SOURCES,SRPMS}
cat > "$TOP/SPECS/$PKG.spec" <<SPEC
Name:           $PKG
Version:        $VERSION
Release:        1
Summary:        $SUMMARY
License:        MIT
URL:            $HOMEPAGE
BuildArch:      x86_64
Requires:       $RPM_REQUIRES
Recommends:     streamlink
# Contenu déjà compilé (celui de l'AppImage) : pas de dépendances automatiques, ni de retouche des binaires
# Already built content (the AppImage's): no automatic dependencies, nor changes to the binaries
AutoReqProv:    no
%define __os_install_post %{nil}
%define _build_id_links none
%define debug_package %{nil}
%define _binary_payload w9.xzdio

%description
$DESCRIPTION

%install
mkdir -p %{buildroot}
cp -a $STAGE/. %{buildroot}/

%files
%license /usr/share/doc/$PKG/copyright
/opt/$PKG
/usr/bin/$PKG
/usr/share/applications/*
/usr/share/metainfo/*
/usr/share/icons/hicolor/256x256/apps/$PKG.png
SPEC
rpmbuild --quiet -bb --define "_topdir $TOP" "$TOP/SPECS/$PKG.spec"
RPM_FILE="$OUT/$PKG-$VERSION-1.x86_64.rpm"
cp "$TOP/RPMS/x86_64/$PKG-$VERSION-1.x86_64.rpm" "$RPM_FILE"
echo "Paquet .rpm : $RPM_FILE ($(du -h "$RPM_FILE" | cut -f1))"
