#!/usr/bin/env bash
# Installe des paquets apt en CI, avec des reprises. Si le miroir du runner ne répond pas (panne DNS du miroir
# Azure, déjà vue), passe au dépôt principal d'Ubuntu et réessaie.
# Installs apt packages in CI, with retries. If the runner's mirror does not answer (DNS outage of the Azure
# mirror, already seen), switches to Ubuntu's main archive and tries again.
# Usage: bash packaging/ci_apt.sh paquet1 paquet2…
set -u
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
