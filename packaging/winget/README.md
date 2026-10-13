# Publier sur winget / Publishing to winget

Le paquet `Bulls64.StreamlinkLauncher` est un exécutable *portable* : winget le télécharge depuis la release GitHub,
vérifie son SHA-256 et crée un alias `streamlink-launcher`. (Streamlink doit être installé à part.)

## À chaque nouvelle version (après la publication de la release GitHub)

1. Générer les manifestes à partir de la release publiée :
   ```
   python packaging/winget/make_manifest.py 1.4.0 winget-out
   ```
2. Valider (sous Windows, avec winget) :
   ```
   winget validate --manifest winget-out\manifests\b\Bulls64\StreamlinkLauncher\1.4.0
   winget settings --enable LocalManifestFiles
   winget install --manifest winget-out\manifests\b\Bulls64\StreamlinkLauncher\1.4.0
   ```
3. **Première fois** : forker [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs), copier le dossier
   `manifests\b\Bulls64\StreamlinkLauncher\<version>` au même emplacement dans le fork, et ouvrir une pull request
   (titre : `New package: Bulls64.StreamlinkLauncher version 1.4.0`). Un robot valide l'installation et l'analyse
   antivirus ; un modérateur peut demander des changements.
4. **Versions suivantes** : même chose avec `Update: Bulls64.StreamlinkLauncher version <x.y.z>`
   (ou l'outil officiel [wingetcreate](https://github.com/microsoft/winget-create) : `wingetcreate update Bulls64.StreamlinkLauncher --version <x.y.z> --urls <url de l'exe>`).

Remarques : l'exécutable n'étant pas signé, la validation automatique (analyse antivirus) peut le signaler ; un faux positif
se corrige en le signalant à l'éditeur de l'antivirus, comme expliqué dans le README.
Une fois le paquet accepté, ajouter `winget install Bulls64.StreamlinkLauncher` au README.
