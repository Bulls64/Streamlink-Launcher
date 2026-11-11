#!/usr/bin/env bash
# Installe des paquets apt en CI, avec des reprises. Si le miroir du runner ne répond pas (panne DNS du miroir
# Azure, déjà vue), passe au dépôt principal d'Ubuntu et réessaie.
# Installs apt packages in CI, with retries. If the runner's mirror does not answer (DNS outage of the Azure
# mirror, already seen), switches to Ubuntu's main archive and tries again.
# Usage: bash packaging/ci_apt.sh paquet1 paquet2…
set -u
# Les images des runners ont déjà beaucoup de paquets (xvfb, par exemple) : seuls les manquants sont installés,
# et apt n'est pas appelé du tout s'il ne manque rien. / Runner images already have many packages (xvfb, for
# example): only the missing ones are installed, and apt is not called at all if nothing is missing.
missing=()
for pkg in "$@"; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || missing+=("$pkg")
done
if [ ${#missing[@]} -eq 0 ]; then
  echo "apt: déjà installés / already installed: $*"
  exit 0
fi
echo "apt: à installer / to install: ${missing[*]}"
set -- "${missing[@]}"
for attempt in 1 2 3; do
  if sudo apt-get update -qq -o Acquire::Retries=3 \
     && sudo apt-get install -y -qq -o Acquire::Retries=3 "$@"; then
    exit 0
  fi
  echo "apt: essai $attempt échoué, passage à archive.ubuntu.com / attempt $attempt failed, switching mirror" >&2
  sudo sed -i 's#mirror+file:/etc/apt/apt-mirrors.txt#http://archive.ubuntu.com/ubuntu/#g' \
    /etc/apt/sources.list.d/*.sources /etc/apt/sources.list 2>/dev/null || true
  sleep 10
done
exit 1
