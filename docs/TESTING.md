# Release checklist · Liste de contrôle avant une release

**[English](#english) · [Français](#français)**

The automated tests imitate Windows (notification area, drag and drop, update) and only start the AppImage in a virtual screen. Before tagging a release, go through this list on a **real Windows 10/11 PC** and a **real Linux desktop** with the files built by the CI for the release branch (*Actions › CI › artifacts*). Copy the list into the release pull request and tick what was checked.

Les tests automatiques imitent Windows (zone de notification, glisser-déposer, mise à jour) et ne lancent l'AppImage que dans un écran virtuel. Avant de poser le tag d'une release, passer cette liste sur un **vrai PC Windows 10/11** et un **vrai bureau Linux**, avec les fichiers compilés par la CI pour la branche de release (*Actions › CI › artifacts*). Copier la liste dans la pull request de la release et cocher ce qui a été vérifié.

---

## English

### Windows (`StreamlinkLauncher-x.y.z.exe`)

**Start**
- [ ] The exe starts (SmartScreen: *More info › Run anyway* the first time); the window, fonts and icons are sharp at 100% and 150% scaling.
- [ ] A second start brings the open window to the front instead of opening another one.

**Streams**
- [ ] A Twitch channel and a Kick channel start in the player; the stream appears in the log drawer and stops with its button.
- [ ] A *Direct link* (YouTube) starts.

**Favorites and live status**
- [ ] A live Twitch favorite shows *Live*, its viewer count and a preview image.
- [ ] A live Kick favorite shows *Live*, its title and viewer count (no image if Kick's preview is WebP, a placeholder is shown).
- [ ] When a favorite goes live: notification, and a click on it starts the stream.

**Notification area and shortcut**
- [ ] With *Minimize to the notification area* on, ✕ hides the window to the tray, with the hint balloon only the first time.
- [ ] Tray menu: *Open Streamlink Launcher*, *Mini mode*, the live favorites (a click starts them), *Open the chats of live favorites*, *Quit*.
- [ ] The global shortcut opens the mini bar; a second press closes it; a click elsewhere closes it.
- [ ] Mini bar: typing, ↑/↓ and Enter start a favorite; a copied link fills it in.

**Desktop integration**
- [ ] A link dragged from the browser's address bar, and a `.url` file, fill the field (overlay shown while dragging).
- [ ] A stream link copied in the browser is offered by a notification when coming back to the launcher.
- [ ] *Start with Windows* survives a restart of Windows.

**Streamlink Chat** (with `StreamlinkChat-x.y.z.exe` next to the launcher)
- [ ] Right-click a Twitch favorite › *Open the chat* opens it; with two live favorites, *Open the chats of live favorites* opens one tab each in a single window.

**Statistics**
- [ ] After watching a stream for more than one minute and closing it, *History › Statistics* shows the time for the channel and the hour in *Peak hours*; a stream still running when quitting is counted too.

**Update**
- [ ] With the previous release installed, *Settings › About › Update* downloads, restarts on the new version, and the exe has the new version in its name; *Start with Windows* points to the new name.

**Settings**
- [ ] Export, then import the settings and favorites; switch language and theme.

### Linux (`StreamlinkLauncher-x.y.z-x86_64.AppImage`)

- [ ] `chmod +x`, then a double-click starts it (GNOME and KDE if possible; Wayland and X11).
- [ ] A Twitch stream starts in mpv or VLC; live status and Kick status work.
- [ ] *Open the chat* with the Streamlink Chat AppImage in the same folder or in `~/Applications`.
- [ ] Statistics and the update check (*Settings › About*) work.

---

## Français

### Windows (`StreamlinkLauncher-x.y.z.exe`)

**Démarrage**
- [ ] L'exe démarre (SmartScreen : *Informations complémentaires › Exécuter quand même* la première fois) ; fenêtre, polices et icônes nettes à 100 % et 150 %.
- [ ] Un second lancement ramène la fenêtre ouverte au premier plan au lieu d'en ouvrir une autre.

**Streams**
- [ ] Une chaîne Twitch et une chaîne Kick démarrent dans le lecteur ; le stream apparaît dans le journal et s'arrête avec son bouton.
- [ ] Un *Lien direct* (YouTube) démarre.

**Favoris et statut en direct**
- [ ] Un favori Twitch en direct affiche *En direct*, le nombre de spectateurs et un aperçu.
- [ ] Un favori Kick en direct affiche *En direct*, son titre et le nombre de spectateurs (pas d'image si l'aperçu de Kick est en WebP : un fond de remplacement s'affiche).
- [ ] Quand un favori commence un live : notification, et un clic dessus lance le stream.

**Zone de notification et raccourci**
- [ ] Avec *Réduire dans la zone de notification* activé, ✕ réduit la fenêtre dans la zone, avec la bulle d'aide la première fois seulement.
- [ ] Menu de l'icône : *Ouvrir Streamlink Launcher*, *Mode mini*, les favoris en direct (un clic les lance), *Ouvrir les chats des favoris en direct*, *Quitter*.
- [ ] Le raccourci global ouvre la barre mini ; un second appui la ferme ; un clic ailleurs la ferme.
- [ ] Barre mini : la saisie, ↑/↓ et Entrée lancent un favori ; un lien copié la remplit.

**Intégration au bureau**
- [ ] Un lien glissé depuis la barre d'adresse du navigateur, et un fichier `.url`, remplissent le champ (calque affiché pendant le glisser).
- [ ] Un lien de stream copié dans le navigateur est proposé par une notification en revenant au lanceur.
- [ ] *Lancer au démarrage de Windows* tient après un redémarrage de Windows.

**Streamlink Chat** (avec `StreamlinkChat-x.y.z.exe` à côté du lanceur)
- [ ] Clic droit sur un favori Twitch › *Ouvrir le chat* l'ouvre ; avec deux favoris en direct, *Ouvrir les chats des favoris en direct* ouvre un onglet par chaîne dans une seule fenêtre.

**Statistiques**
- [ ] Après plus d'une minute de stream puis sa fermeture, *Historique › Statistiques* montre le temps de la chaîne et l'heure dans *Heures de pointe* ; un stream encore ouvert en quittant compte aussi.

**Mise à jour**
- [ ] Avec la release précédente installée, *Paramètres › À propos › Mettre à jour* télécharge, redémarre sur la nouvelle version, et l'exe porte le nouveau numéro ; *Lancer au démarrage de Windows* suit le nouveau nom.

**Paramètres**
- [ ] Exporter puis importer les réglages et favoris ; changer de langue et de thème.

### Linux (`StreamlinkLauncher-x.y.z-x86_64.AppImage`)

- [ ] `chmod +x`, puis un double-clic la lance (GNOME et KDE si possible ; Wayland et X11).
- [ ] Un stream Twitch démarre dans mpv ou VLC ; le statut en direct et celui de Kick marchent.
- [ ] *Ouvrir le chat* avec l'AppImage de Streamlink Chat dans le même dossier ou dans `~/Applications`.
- [ ] Les statistiques et la recherche de mise à jour (*Paramètres › À propos*) marchent.
