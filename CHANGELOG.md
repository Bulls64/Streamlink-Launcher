# Changelog

**[English](#english) · [Français](#français)**

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## English

## [Unreleased]

### Changed
- **`launcher/app.py` split into smaller modules** (2,276 → about 680 lines): favorites and live status, launching and log drawer, side panels, updates, desktop integration (tray, clipboard, drag and drop). The methods are moved unchanged into mixins of `App`; no change in behavior.
- **`launcher/core.py` and `launcher/widgets.py` split as well**: `core.py` (1,705 → about 760 lines) keeps paths, configuration, languages, platforms, history and launching; input validation and links go to `inputs.py`, backup to `backup.py`, updates to `updater.py`, live status to `live.py`. `widgets.py` now re-exports the components grouped in `widgets_base`, `widgets_controls`, `widgets_cards`, `widgets_field` and `widgets_layout`. Code moved unchanged; no change in behavior.

### Planned
- Viewing statistics (time per channel, peak hours).

## [1.5.1] - 2026-10-24

### Added
- **Code of conduct** (`CODE_OF_CONDUCT.md`, English and French).
- **Website and documentation**, in French and English, on GitHub Pages: https://bulls64.github.io/Streamlink-Launcher. The README links to it.

### Changed
- Every French comment and docstring now has its English translation. No change in behavior.

## [1.5.0] - 2026-10-16

### Added
- **Linux AppImage.** Each release now also comes with `StreamlinkLauncher-<version>-x86_64.AppImage`: one file with its own Python and Tcl/Tk (recompiled with Xft for smooth text and system fonts), for any distribution with glibc 2.35 or newer. Streamlink and the video player are the ones installed on the system. Settings and favorites go to `~/.config/streamlink-launcher`, including `platforms.json` (a copy of the bundled file, so it stays editable). Built by `packaging/appimage/build_appimage.sh`, with pinned and checksummed downloads, and smoke-tested under Xvfb by the CI.

### Changed
- On Linux, the interface language follows `LC_ALL` / `LC_MESSAGES` / `LANG` even when that locale is not generated on the system.
- The window class is now `StreamlinkLauncher` (Linux), so desktop environments match the window with its menu entry.

## [1.4.3] - 2026-10-16

### Changed
- **The executable is renamed after an update.** `StreamlinkLauncher-1.4.1.exe` updated to 1.4.2 becomes `StreamlinkLauncher-1.4.2.exe` (a file name without a version number is kept). Start with Windows follows the new name, and the old file is removed at the next start.
- Silent `try/except: pass` blocks in the Windows integration (tray, drag and drop, notifications, title bar) now write to `launcher.log` (debug level), which makes problems easier to diagnose.
- The executable metadata now names *Bulls64* as the publisher, like the repository.

### Added
- Project hygiene: `ruff` static analysis and a GUI smoke test (Xvfb) in the CI, GitHub Actions pinned by commit and kept up to date by Dependabot, `SECURITY.md`, `CONTRIBUTING.md`, issue and pull request templates.
- Updated screenshots in the README, and the `packaging/winget/` and `.signpath/` folders listed in the project structure.

## [1.4.2] - 2026-10-14

### Added
- **Platform colors on favorite cards.** Cards are now tinted with their platform's color (Twitch purple, Kick green, YouTube red…): faint background tint, colored border, solid border when live and on hover. The color comes from the platform definition (`platforms.json`), so custom platforms get theirs too. Can be turned off in Settings → General (*Platform colors*).

## [1.4.1] - 2026-10-14

### Added
- **Automatic launcher updates.** New setting *Update the launcher automatically* (Settings → About, off by default). When it is on and *Check for updates at start-up* is on, a newer release found at start-up is downloaded, verified and installed without asking, then the launcher restarts (staying in the notification area if it was started there). It never runs while a stream is running (the update card offers it instead), only for the executable in a writable folder, not on a manual check, and not right after an update (no update loop). A failure (network, checksum, signature) is shown on the update card and in the log, and the current version stays in place.

## [1.4.0] - 2026-10-14

### Added
- **Update the launcher from GitHub.** Settings → About now has an update card. It checks the latest release of the repository (automatically a few seconds after start-up when *Check for updates* is on, or with the *Check* button) and, when a newer version exists, *Update* downloads the executable, verifies it, replaces the running one and restarts the launcher. Checks: the file must be the release asset of this repository, have the size and the SHA-256 published by GitHub, and look like a Windows executable; if the current executable is signed, the new one must be validly signed by the same publisher (no way back to an unsigned file). Redirects are followed only to GitHub. The previous executable is renamed `.old` and removed at the next start; on any failure it is put back. Running streams are stopped after a confirmation. Run from the sources, or from a write-protected folder, the button opens the release page instead. *Release notes* and *GitHub repository* links sit under the card, and a badge shows when an update is available.
- **Optional code signing in the release workflow.** The workflow can have the executable signed through [SignPath.io](https://about.signpath.io): it waits for the manual approval, checks that the signature is valid and timestamped, and never publishes an unsigned file once signing is enabled. Signing stays off unless the `SIGNPATH_ORGANIZATION_ID` repository variable is set; **releases are currently unsigned**, and the README (*Code signing*) explains why and what protects you instead (builds by GitHub Actions only, `SHA256SUMS.txt`, hash check by the updater).
- Each release comes with `SHA256SUMS.txt` (attached since v1.3.0), and its notes show the SHA-256 of the executable.
- README: new *If Windows blocks the executable* section (check the SHA-256, SmartScreen, *Unblock*, antivirus quarantine, run from source), and `packaging/winget/` to generate the [winget](https://learn.microsoft.com/windows/package-manager/) manifests of a release.

### Changed
- **Fewer antivirus false positives**: PyInstaller's bootloader is now compiled from source on GitHub Actions instead of using the prebuilt one shared by countless programs, UPX compression is disabled, and the PyInstaller version is pinned (`packaging/requirements-build.txt`).
- Every pull request now builds the executable, so a build problem shows up before the release.

## [1.3.0] - 2026-10-13

### Changed
- **Favorites sorted by platform.** The favorites on the main screen now follow the selected platform button: *Twitch* shows only Twitch favorites, *Kick* only Kick favorites, and so on (a script shows the favorites of that script). The section title shows the platform (*Favorites · Kick*), live favorites still come first, and a platform with no favorites says so. Selecting a platform by typing or pasting a link, or by clicking a recent stream, switches the list too. *See all* still opens every favorite, and live notifications still cover all platforms.

## [1.2.0] - 2026-10-13

### Added
- **Live previews in favorites.** When a Twitch favorite is live, its card on the main screen shows a preview image of the stream with a *LIVE* badge and the viewer count, then the stream title and the game. Previews are refreshed at each live check without flickering, and resized to the card when the window is resized. Kick favorites that are live show the badge, title and game (Kick gives no preview or viewer count). With nobody live, cards keep their compact look. Can be turned off in Settings → Live (*Live previews*); compact cards then show the viewer count instead of *Live*.
- The viewer count also appears in the Favorites panel, in the mini bar suggestions and in the tray menu. Numbers are shortened according to the language (12.3K, 12,3 k, 12,3 Tsd.…).
- Images are decoded with GDI+, built into Windows: still no dependency to install.

## [1.1.0] - 2026-10-12

### Added
- **Smart clipboard.** When you come back to the window, the launcher notices a stream link you just copied and offers to launch it from a notification (*Launch* button). Opening the mini bar with the shortcut pre-fills it with the copied link, selected, so you can press <kbd>Enter</kbd> or simply type to replace it. A link is offered only once (copying it again offers it again), never when it is already in the field, and only links are looked at: ordinary text is ignored. It can be turned off in the settings (*Detect copied links*).
- **Drag and drop.** Drop a link onto the window — from a browser address bar or tab, selected text, or an Internet shortcut (`.url`) / text file — and it fills the field, selects the right platform and offers to launch it. A dashed drop zone appears while you drag. Windows only; no new dependency.
- **Export / import of settings and favorites** (Settings → Backup): one JSON file to restore your setup or copy it to another computer. Importing asks whether to add the favorites to the current ones or replace them. Paths specific to the computer (Streamlink, player, scripts folder, window position) are neither exported nor imported, and only known settings with valid values are accepted, so a file received from someone else cannot point to a program to run. A plain `config.json` or `favorites.json` can also be imported.
- **Spanish, German and Italian translations** (complete interface). The language is chosen in the settings, now a drop-down list since five languages no longer fit side by side; the system language is detected at first launch.

### Changed
- **Faster interface**: rebuilding the window (theme or language change) is about 35-45 % faster, the History panel opens about 40 % faster, and start-up is a little quicker. Each control is now drawn once at its final size instead of twice, text measurements are remembered, the window icon is computed only where needed, and on Windows the tray, shortcut and drag-and-drop share one 100 ms check instead of two. The display is pixel-identical.

### Fixed
- Importing a backup with *Start with Windows* enabled now really registers the launcher at start-up (the setting was saved but Windows was never told).
- The hover highlight of the *Stop* button (log drawer) and of the Streamlink card button no longer stays lit after the mouse leaves.

### Removed
- Dead code: unused constants, method and attribute, and 5 translation texts (× 5 languages) left over from the old *Test* button. A test now fails if a translation is no longer used.

## [1.0.2] - 2026-10-11

### Fixed
- **The launcher no longer crashes at start-up in a read-only folder** (for example `C:\Program Files`). Data then goes to `%APPDATA%\Streamlink Launcher`, and the log drawer says so.
- **Favorites, history and settings can no longer be lost silently.** Files are written atomically (temporary file, then replace), and the previous version is kept as `.bak`. A damaged file (power cut during a write) is set aside as `.corrupt` and restored from its backup, with an on-screen warning, instead of being overwritten by an empty list.
- A failed save is now reported on screen instead of being ignored.

### Added
- `launcher.log` error log next to the data (2 × 512 KB maximum): network, live check, notification and file errors that used to be ignored.
- *About* section in the settings: version number, data folder and a button to open it.
- Unit tests (`tests/`) and a GitHub Actions workflow: tests on Windows and Linux at every push, and the `.exe` built and attached to the release at every `v*` tag.
- MIT license.

### Changed
- Repository layout: the sources are at the root, so the README instructions and screenshots work. The `.exe` and the zip are published in the Releases only, no longer in Git.
- `.bat` scripts are stored with Windows line endings (CRLF).

## [1.0.1] - 2026-10-11

### Fixed
- **The global shortcut crashed the application on Windows.** The tray/shortcut window called Tkinter from inside Windows message processing, which corrupted Python's internal state ("PyEval_RestoreThread: GIL is released"). With `pythonw` or the `.exe`, the app closed silently. Clicking the tray icon triggered the same crash. Windows events are now queued and handled from the Tk event loop.
- **Mini mode never appeared on Windows.** It bound a Linux-only key name (`ISO_Left_Tab`), which raised an error halfway through opening the window.
- Mini mode could close immediately when Windows refused to bring it to the foreground. It is now forced to the foreground, and it no longer closes before it has received focus.
- Translation: a `{key}` placeholder conflicted with a parameter name of the translation function.

### Added
- Choice of global shortcut: <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd>, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd>, <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd> or <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>L</kbd>.
- Shortcut status in the settings (active, or already used by another application), plus a warning when Windows refuses it (error 1409).
- Diagnostics in the log drawer: shortcut registered, and each shortcut press received.

### Changed
- Pressing the shortcut while the mini bar is open but not focused brings it back instead of closing it.

## 1.0.0 - 2026-10-11

### Added
- Standalone Windows executable `Streamlink Launcher.exe`: a single file, no console, no Python required. Built with PyInstaller, with an embedded icon and version information.
- `packaging/build_exe.bat` script to rebuild the executable.
- Bilingual `README.md` (English and French) with screenshots.

### Changed
- In the packaged version, user data (`config.json`, `platforms.json`, `streams/`) stays next to the `.exe`, and translations and the icon are embedded. A `lang/` folder next to the `.exe` takes precedence over the embedded translations.
- The *Start with Windows* entry is rewritten at each start-up, so it always points to the version actually in use (`.py` or `.exe`).

## 0.7.0 - 2026-10-11

### Added
- Streamlink update check: compares the installed version (`streamlink --version`) with the latest version published on PyPI.
- Context-aware Streamlink card in the settings: *up to date*, *update available* (with an **Update** button), *not found* (with an **Install** button).
- **Update** button: opens the installer download page (Windows install) or copies `python -m pip install --upgrade streamlink` to the clipboard (pip install).
- *Check for updates at start-up* option, enabled by default, with an orange badge on the settings icon when an update is available.

### Fixed
- The Streamlink card stayed empty when the settings panel opened.

## 0.6.0 - 2026-10-11

### Added
- **Mini mode**: a floating Spotlight-style bar opened with a global shortcut. It shows live favorites first, then suggestions as you type. <kbd>Tab</kbd> changes the platform and <kbd>Enter</kbd> launches.
- **Notification area icon**: closing the window minimizes it to the tray, with streams and live checks still running. The right-click menu offers live favorites, mini mode and *Quit*.
- Clickable live notifications attached to the tray icon (a click launches the stream).
- *Start with Windows* option, which starts minimized (`--tray`).
- Single instance: launching the app again shows the existing window.
- Multi-size application icon (`app.ico`).

### Fixed
- The platform pill in mini mode was clipped.

## 0.5.0 - 2026-10-11

### Added
- **Live status for favorites**: *Live* / *Offline* on cards, live favorites shown first, game and title in the favorites panel.
- Twitch: a single batched request for all Twitch favorites. Kick: check through `streamlink --json`. The method is set per platform in `platforms.json` (`live_check`).
- Notifications when a favorite goes live: inside the app (with a **Launch** button), as a Windows notification, and by flashing the taskbar button.
- *Live* settings: on/off, check frequency (2 to 30 min), Windows notifications.

### Changed
- At start-up, a single discreet summary is shown instead of one notification per live favorite.
- A secondary notification never hides an error that is still displayed.
- The web module is loaded only when it is first needed (about 5 MB less memory at start-up).

## 0.4.0 - 2026-10-11

### Added
- **Completely redesigned interface**, still pure Tkinter with no dependency:
  - a smart search field that detects the platform when a link is pasted, with suggestions from favorites and history;
  - platform pills with an accent color per platform (button, field, window border);
  - favorite cards (right-click menu), recent streams, and a log drawer with a **Stop** button per stream;
  - non-blocking notifications with an **Undo** action;
  - side panels for Settings, History and Favorites.
- Light, dark or **automatic** theme (follows Windows), dark title bar and rounded corners on Windows 11, sharp rendering at 125/150 % scaling.
- Windows icon font (Segoe Fluent Icons / MDL2), with drawn icons as a fallback.
- Code split into modules (`core`, `theme`, `gfx`, `widgets`, `app`).

### Changed
- Old favorites without a platform get their platform from the history (Twitch by default).
- Stopping a stream manually is logged as *stopped* instead of an error code.

### Fixed
- Infinite redraw loop in a field with a badge.
- `Canvas.lift()` moved drawn items instead of the widget.

## 0.3.0 - 2026-10-11

### Added
- `platforms.json`: platforms defined in a file (Twitch, Kick, YouTube, **Dailymotion**, Steam TV, **Direct link**). Streamlink is called directly, so the `.bat` files are no longer needed.
- Streamlink output shown in the application log.
- Quality selection, remembered per platform, including fallback lists.
- Video player selection (default, VLC, mpv, PotPlayer, custom) with automatic path detection and player arguments.
- **French and English** interface (`lang/fr.json`, `lang/en.json`), using the Windows language by default.
- *Settings* tab: language, theme, Streamlink path with a **Test** button, player, custom scripts.

### Changed
- Custom `.bat` scripts are still available as an option (*Show .bat scripts*).
- The application asks for confirmation before quitting while streams are running.

## 0.2.0 - 2026-10-11

### Added
- Favorites remember their platform.
- The input label and field adapt to the selected script (Twitch channel, YouTube video ID, nothing for Steam TV).
- Pasted links are accepted (`twitch.tv/…`, `youtube.com/watch?v=…`, `youtu.be/…`).
- `config.json` remembers the selected folder.

### Changed
- Paths are portable: the hard-coded folder `C:\Users\…\streams` was removed, and the app uses its own folder.

### Security
- Scripts are launched **without `shell=True`**, and user input is validated, which prevents command injection through `&`, `|`, `%`…

### Fixed
- Old YouTube history entries (`ID&list=…`) are cleaned up when relaunched.

## 0.1.0 - 2025-10-16

### Added
- First version: a Tkinter window that lists the `.bat` scripts in a folder (Twitch, Kick, YouTube, Steam TV) and runs them with a channel name.
- Launch history (200 entries) and favorites.
- Dark mode.

> Versions 0.1.0 to 1.0.0 were never published on GitHub; 1.0.1 is the first release. The date of 0.1.0 is the oldest date found in the application data.

---

## Français

## [Non publié]

### Modifié
- **`launcher/app.py` découpé en modules plus petits** (2 276 → environ 680 lignes) : favoris et statut en direct, lancement et tiroir du journal, panneaux latéraux, mises à jour, intégration au bureau (zone de notification, presse-papiers, glisser-déposer). Les méthodes sont déplacées sans modification dans des mixins de `App` ; aucun changement de comportement.
- **`launcher/core.py` et `launcher/widgets.py` découpés aussi** : `core.py` (1 705 → environ 760 lignes) garde les chemins, la configuration, les langues, les plateformes, l'historique et le lancement ; la validation des saisies et des liens passe dans `inputs.py`, la sauvegarde dans `backup.py`, les mises à jour dans `updater.py`, le statut en direct dans `live.py`. `widgets.py` réexporte maintenant les composants rangés dans `widgets_base`, `widgets_controls`, `widgets_cards`, `widgets_field` et `widgets_layout`. Code déplacé sans modification ; aucun changement de comportement.

### Prévu
- Statistiques de visionnage (temps par chaîne, heures de pointe).

## [1.5.1] - 2026-10-24

### Ajouté
- **Code de conduite** (`CODE_OF_CONDUCT.md`, anglais et français).
- **Site et documentation**, en français et en anglais, sur GitHub Pages : https://bulls64.github.io/Streamlink-Launcher. Le README y renvoie.

### Modifié
- Chaque commentaire et chaque docstring en français a maintenant sa traduction anglaise. Aucun changement de comportement.

## [1.5.0] - 2026-10-16

### Ajouté
- **AppImage pour Linux.** Chaque release contient aussi `StreamlinkLauncher-<version>-x86_64.AppImage` : un seul fichier avec son propre Python et Tcl/Tk (recompilé avec Xft pour un texte lissé et les polices du système), pour toute distribution avec la glibc 2.35 ou plus récente. Streamlink et le lecteur vidéo sont ceux installés sur le système. Réglages et favoris vont dans `~/.config/streamlink-launcher`, y compris `platforms.json` (copie du fichier livré, pour qu'il reste modifiable). Construite par `packaging/appimage/build_appimage.sh`, téléchargements figés et vérifiés, et testée au démarrage sous Xvfb par la CI.

### Modifié
- Sous Linux, la langue de l'interface suit `LC_ALL` / `LC_MESSAGES` / `LANG` même quand cette locale n'est pas générée sur le système.
- La classe de fenêtre est maintenant `StreamlinkLauncher` (Linux), pour que les environnements de bureau associent la fenêtre à son entrée de menu.

## [1.4.3] - 2026-10-16

### Modifié
- **L'exécutable est renommé après une mise à jour.** `StreamlinkLauncher-1.4.1.exe` mis à jour vers la 1.4.2 devient `StreamlinkLauncher-1.4.2.exe` (un nom de fichier sans numéro de version est conservé). Le démarrage avec Windows suit le nouveau nom, et l'ancien fichier est supprimé au démarrage suivant.
- Les blocs `try/except: pass` silencieux de l'intégration Windows (zone de notification, glisser-déposer, notifications, barre de titre) écrivent maintenant dans `launcher.log` (niveau debug), ce qui facilite le diagnostic.
- Les métadonnées de l'exécutable indiquent *Bulls64* comme éditeur, comme le dépôt.

### Ajouté
- Hygiène du projet : analyse statique `ruff` et test de fumée de l'interface (Xvfb) dans la CI, GitHub Actions épinglées par commit et tenues à jour par Dependabot, `SECURITY.md`, `CONTRIBUTING.md`, modèles de tickets et de pull requests.
- Captures d'écran du README mises à jour, et dossiers `packaging/winget/` et `.signpath/` ajoutés à la structure du projet.

## [1.4.2] - 2026-10-14

### Ajouté
- **Couleurs par plateforme sur les cartes de favoris.** Les cartes prennent la couleur de leur plateforme (violet Twitch, vert Kick, rouge YouTube…) : fond légèrement teinté, contour coloré, contour plein en direct et au survol. La couleur vient de la définition de la plateforme (`platforms.json`), donc les plateformes personnalisées ont aussi la leur. Désactivable dans Paramètres → Général (*Couleurs par plateforme*).

## [1.4.1] - 2026-10-14

### Ajouté
- **Mise à jour automatique du lanceur.** Nouveau réglage *Mises à jour automatiques du lanceur* (Paramètres → À propos, désactivé par défaut). Quand il est activé avec *Vérifier les mises à jour au démarrage*, une version plus récente trouvée au démarrage est téléchargée, vérifiée et installée sans demander, puis le lanceur redémarre (en restant dans la zone de notification s'il y était). Rien ne se fait pendant un stream (la carte de mise à jour la propose alors), ni pour une vérification manuelle, ni juste après une mise à jour (pas de boucle), et seulement pour l'exécutable dans un dossier modifiable. Un échec (réseau, empreinte, signature) s'affiche sur la carte et dans le journal, et la version actuelle reste en place.

## [1.4.0] - 2026-10-14

### Ajouté
- **Mise à jour du lanceur depuis GitHub.** Paramètres → À propos contient maintenant une carte de mise à jour. Elle cherche la dernière release du dépôt (automatiquement quelques secondes après le démarrage si *Vérifier les mises à jour* est activé, ou avec le bouton *Vérifier*) et, quand une version plus récente existe, *Mettre à jour* télécharge l'exécutable, le vérifie, remplace celui qui tourne et redémarre le lanceur. Contrôles : le fichier doit être l'asset de release de ce dépôt, avoir la taille et le SHA-256 publiés par GitHub et ressembler à un exécutable Windows ; si l'exécutable actuel est signé, le nouveau doit l'être valablement par le même éditeur (impossible de revenir à un fichier non signé). Les redirections ne sont suivies que vers GitHub. L'ancien exécutable est renommé en `.old` puis supprimé au démarrage suivant ; en cas d'échec, il est remis en place. Les streams en cours sont arrêtés après confirmation. Lancé depuis les sources ou depuis un dossier protégé en écriture, le bouton ouvre la page de la release. Les liens *Notes de version* et *Dépôt GitHub* sont sous la carte, et un badge signale une mise à jour disponible.
- **Signature du code facultative dans le workflow de release.** Le workflow peut faire signer l'exécutable via [SignPath.io](https://about.signpath.io) : il attend l'approbation manuelle, vérifie que la signature est valide et horodatée, et ne publie jamais de fichier non signé une fois la signature activée. La signature reste désactivée tant que la variable de dépôt `SIGNPATH_ORGANIZATION_ID` n'est pas définie ; **les releases sont actuellement non signées**, et le README (*Signature du code*) explique pourquoi et ce qui te protège à la place (compilation par GitHub Actions uniquement, `SHA256SUMS.txt`, contrôle du hash par la mise à jour).
- Chaque release est accompagnée de `SHA256SUMS.txt` (joint depuis la v1.3.0), et ses notes affichent le SHA-256 de l'exécutable.
- README : nouvelle section *Si Windows bloque l'exécutable* (vérifier le SHA-256, SmartScreen, *Débloquer*, quarantaine de l'antivirus, lancement depuis les sources), et `packaging/winget/` pour générer les manifestes [winget](https://learn.microsoft.com/windows/package-manager/) d'une release.

### Modifié
- **Moins de faux positifs antivirus** : le chargeur de PyInstaller est maintenant compilé depuis ses sources sur GitHub Actions au lieu d'utiliser celui précompilé partagé par d'innombrables programmes, la compression UPX est désactivée, et la version de PyInstaller est figée (`packaging/requirements-build.txt`).
- Chaque pull request compile maintenant l'exécutable : un problème de compilation se voit avant la release.

## [1.3.0] - 2026-10-13

### Modifié
- **Favoris classés par plateforme.** Les favoris de l'écran principal suivent maintenant le bouton de plateforme choisi : *Twitch* n'affiche que les favoris Twitch, *Kick* que les favoris Kick, etc. (un script affiche les favoris de ce script). Le titre de la section indique la plateforme (*Favoris · Kick*), les favoris en direct restent en premier, et une plateforme sans favori l'indique. Choisir une plateforme en tapant ou collant un lien, ou en cliquant sur un stream récent, change aussi la liste. *Tout voir* ouvre toujours tous les favoris, et les notifications de live concernent toujours toutes les plateformes.

## [1.2.0] - 2026-10-13

### Ajouté
- **Aperçu des lives dans les favoris.** Quand un favori Twitch est en direct, sa carte sur l'écran principal affiche une image d'aperçu du stream avec un badge *EN DIRECT* et le nombre de spectateurs, puis le titre du stream et le jeu. Les aperçus sont mis à jour à chaque vérification sans clignoter, et redimensionnés à la carte quand la fenêtre change de taille. Les favoris Kick en direct affichent le badge, le titre et le jeu (Kick ne fournit ni aperçu ni nombre de spectateurs). Quand personne n'est en direct, les cartes gardent leur aspect compact. Désactivable dans Paramètres → En direct (*Aperçu des lives*) ; les cartes compactes affichent alors le nombre de spectateurs à la place de *En direct*.
- Le nombre de spectateurs apparaît aussi dans le panneau Favoris, dans les suggestions du mode mini et dans le menu de l'icône de notification. Les nombres sont abrégés selon la langue (12,3 k, 12.3K, 12,3 Tsd.…).
- Les images sont décodées par GDI+, inclus dans Windows : toujours aucune dépendance à installer.

## [1.1.0] - 2026-10-12

### Ajouté
- **Presse-papiers intelligent.** Quand tu reviens sur la fenêtre, le lanceur repère un lien de stream que tu viens de copier et propose de le lancer depuis une notification (bouton *Lancer*). L'ouverture de la barre mini avec le raccourci la pré-remplit avec le lien copié, sélectionné : <kbd>Entrée</kbd> pour lancer, ou tape directement pour le remplacer. Un lien n'est proposé qu'une fois (le recopier le propose de nouveau), jamais s'il est déjà dans le champ, et seuls les liens sont regardés : un texte ordinaire est ignoré. Désactivable dans les Paramètres (*Détecter les liens copiés*).
- **Glisser-déposer.** Dépose un lien sur la fenêtre — depuis la barre d'adresse ou un onglet d'un navigateur, du texte sélectionné, ou un raccourci Internet (`.url`) / fichier texte — et il remplit le champ, choisit la bonne plateforme et propose de le lancer. Une zone de dépôt en pointillés apparaît pendant le glissement. Windows uniquement ; aucune nouvelle dépendance.
- **Export / import des réglages et des favoris** (Paramètres → Sauvegarde) : un fichier JSON pour restaurer ta configuration ou la copier sur un autre ordinateur. L'import demande s'il faut ajouter les favoris aux actuels ou les remplacer. Les chemins propres à l'ordinateur (Streamlink, lecteur, dossier des scripts, position de la fenêtre) ne sont ni exportés ni importés, et seuls les réglages connus aux valeurs valides sont acceptés : un fichier reçu d'ailleurs ne peut donc pas désigner un programme à lancer. Un simple `config.json` ou `favorites.json` peut aussi être importé.
- **Traductions en espagnol, allemand et italien** (interface complète). La langue se choisit dans les Paramètres, désormais une liste déroulante car cinq langues ne tiennent plus côte à côte ; la langue du système est détectée au premier lancement.

### Modifié
- **Interface plus rapide** : la reconstruction de la fenêtre (changement de thème ou de langue) est environ 35 à 45 % plus rapide, le panneau Historique s'ouvre environ 40 % plus vite, et le démarrage est un peu plus court. Chaque composant est maintenant dessiné une seule fois à sa taille finale au lieu de deux, les mesures de texte sont mémorisées, l'icône de la fenêtre n'est calculée finement que sur ses bords, et sous Windows l'icône de notification, le raccourci et le glisser-déposer partagent une seule vérification toutes les 100 ms au lieu de deux. L'affichage est identique au pixel près.

### Corrigé
- L'import d'une sauvegarde avec *Lancer au démarrage de Windows* activé inscrit maintenant vraiment le lanceur au démarrage (le réglage était enregistré mais Windows n'était jamais prévenu).
- Le survol du bouton *Arrêter* (tiroir du journal) et du bouton de la carte Streamlink ne reste plus allumé quand la souris s'en va.

### Retiré
- Code mort : constantes, méthode et attribut inutilisés, et 5 textes de traduction (× 5 langues) restés de l'ancien bouton *Tester*. Un test échoue désormais si une traduction n'est plus utilisée.

## [1.0.2] - 2026-10-11

### Corrigé
- **Le lanceur ne plante plus au démarrage dans un dossier protégé en écriture** (par exemple `C:\Program Files`). Les données vont alors dans `%APPDATA%\Streamlink Launcher`, et le tiroir du journal l'indique.
- **Favoris, historique et réglages ne peuvent plus être perdus sans prévenir.** Les fichiers sont écrits de façon atomique (fichier temporaire, puis remplacement), et la version précédente est gardée en `.bak`. Un fichier endommagé (coupure de courant pendant l'écriture) est mis de côté en `.corrupt` et restauré depuis sa sauvegarde, avec un avertissement à l'écran, au lieu d'être écrasé par une liste vide.
- Un enregistrement qui échoue est désormais signalé à l'écran au lieu d'être ignoré.

### Ajouté
- Journal d'erreurs `launcher.log` à côté des données (2 × 512 Ko maximum) : erreurs réseau, de détection du direct, de notification et de fichiers, auparavant ignorées.
- Section *À propos* dans les Paramètres : numéro de version, dossier des données et bouton pour l'ouvrir.
- Tests unitaires (`tests/`) et workflow GitHub Actions : tests sous Windows et Linux à chaque push, et `.exe` compilé et joint à la release à chaque tag `v*`.
- Licence MIT.

### Modifié
- Organisation du dépôt : les sources sont à la racine, les instructions et captures du README fonctionnent. L'`.exe` et le zip sont publiés uniquement dans les Releases, plus dans Git.
- Les scripts `.bat` sont stockés avec les fins de ligne Windows (CRLF).

## [1.0.1] - 2026-10-11

### Corrigé
- **Le raccourci global faisait planter l'application sous Windows.** La fenêtre de l'icône et du raccourci appelait Tkinter pendant le traitement des messages Windows, ce qui corrompait l'état interne de Python (« PyEval_RestoreThread: GIL is released »). Avec `pythonw` ou l'`.exe`, l'application se fermait sans message. Le clic sur l'icône de notification provoquait le même plantage. Les événements Windows passent désormais par une file, traitée depuis la boucle Tk.
- **Le mode mini ne s'affichait jamais sous Windows.** Il associait un nom de touche propre à Linux (`ISO_Left_Tab`), ce qui provoquait une erreur au milieu de l'ouverture de la fenêtre.
- Le mode mini pouvait se refermer aussitôt quand Windows refusait de le mettre au premier plan. Il est maintenant mis au premier plan de force, et ne se ferme plus avant d'avoir reçu le focus.
- Traduction : une variable `{key}` entrait en conflit avec un nom de paramètre de la fonction de traduction.

### Ajouté
- Choix du raccourci global : <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Espace</kbd>, <kbd>Ctrl</kbd>+<kbd>Maj</kbd>+<kbd>Espace</kbd>, <kbd>Alt</kbd>+<kbd>Maj</kbd>+<kbd>S</kbd> ou <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>L</kbd>.
- État du raccourci dans les Paramètres (actif, ou déjà utilisé par une autre application), et alerte quand Windows le refuse (erreur 1409).
- Diagnostic dans le tiroir du journal : raccourci enregistré, et chaque appui reçu.

### Modifié
- Appuyer sur le raccourci quand la barre mini est ouverte mais sans le focus la ramène au premier plan au lieu de la fermer.

## 1.0.0 - 2026-10-11

### Ajouté
- Exécutable Windows autonome `Streamlink Launcher.exe` : un seul fichier, sans console, sans Python à installer. Construit avec PyInstaller, avec l'icône et les informations de version intégrées.
- Script `packaging/build_exe.bat` pour recompiler l'exécutable.
- `README.md` bilingue (anglais et français) avec captures d'écran.

### Modifié
- Dans la version empaquetée, les données personnelles (`config.json`, `platforms.json`, `streams/`) restent à côté de l'`.exe`, et les traductions et l'icône sont intégrées. Un dossier `lang/` placé à côté de l'`.exe` est prioritaire sur les traductions intégrées.
- L'entrée *Lancer au démarrage de Windows* est réécrite à chaque démarrage, pour pointer toujours vers la version utilisée (`.py` ou `.exe`).

## 0.7.0 - 2026-10-11

### Ajouté
- Vérification des mises à jour de Streamlink : compare la version installée (`streamlink --version`) à la dernière version publiée sur PyPI.
- Carte Streamlink contextuelle dans les Paramètres : *à jour*, *mise à jour disponible* (bouton **Mettre à jour**), *introuvable* (bouton **Installer**).
- Bouton **Mettre à jour** : ouvre la page de téléchargement de l'installateur (installation Windows) ou copie `python -m pip install --upgrade streamlink` dans le presse-papiers (installation pip).
- Option *Vérifier les mises à jour au démarrage*, activée par défaut, avec une pastille orange sur l'icône des Paramètres quand une mise à jour est disponible.

### Corrigé
- La carte Streamlink restait vide à l'ouverture des Paramètres.

## 0.6.0 - 2026-10-11

### Ajouté
- **Mode mini** : barre flottante façon Spotlight, ouverte avec un raccourci global. Elle affiche d'abord les favoris en direct, puis des suggestions pendant la frappe. <kbd>Tab</kbd> change de plateforme, <kbd>Entrée</kbd> lance.
- **Icône dans la zone de notification** : fermer la fenêtre la réduit à côté de l'horloge, sans arrêter les streams ni la surveillance des lives. Le menu clic droit propose les favoris en direct, le mode mini et *Quitter*.
- Notifications de live cliquables, attachées à l'icône (un clic lance le stream).
- Option *Lancer au démarrage de Windows*, qui démarre réduit (`--tray`).
- Instance unique : relancer l'application affiche la fenêtre déjà ouverte.
- Icône de l'application en plusieurs tailles (`app.ico`).

### Corrigé
- La pastille de plateforme du mode mini était rognée.

## 0.5.0 - 2026-10-11

### Ajouté
- **Statut en direct des favoris** : *En direct* / *Hors ligne* sur les cartes, favoris en direct affichés en premier, jeu et titre dans le panneau Favoris.
- Twitch : une seule requête groupée pour tous les favoris Twitch. Kick : vérification via `streamlink --json`. La méthode se règle par plateforme dans `platforms.json` (`live_check`).
- Notifications quand un favori commence un live : dans l'application (avec un bouton **Lancer**), par une notification Windows, et en faisant clignoter le bouton dans la barre des tâches.
- Réglages *En direct* : activation, fréquence de vérification (2 à 30 min), notifications Windows.

### Modifié
- Au démarrage, un seul résumé discret s'affiche au lieu d'une notification par favori en direct.
- Une notification secondaire ne cache jamais une erreur encore affichée.
- Le module web n'est chargé qu'à sa première utilisation (environ 5 Mo de mémoire en moins au démarrage).

## 0.4.0 - 2026-10-11

### Ajouté
- **Interface entièrement repensée**, toujours en Tkinter pur et sans dépendance :
  - champ de recherche intelligent qui reconnaît la plateforme d'un lien collé, avec des suggestions tirées des favoris et de l'historique ;
  - pastilles de plateforme, avec une couleur d'accent par plateforme (bouton, champ, bordure de fenêtre) ;
  - cartes de favoris (menu clic droit), streams récents, et tiroir du journal avec un bouton **Arrêter** par stream ;
  - notifications non bloquantes avec une action **Annuler** ;
  - panneaux latéraux Paramètres, Historique et Favoris.
- Thème clair, sombre ou **automatique** (suit Windows), barre de titre sombre et coins arrondis sous Windows 11, affichage net en mise à l'échelle 125/150 %.
- Icônes issues de la police Windows (Segoe Fluent Icons / MDL2), avec des icônes dessinées en secours.
- Code découpé en modules (`core`, `theme`, `gfx`, `widgets`, `app`).

### Modifié
- Les anciens favoris sans plateforme retrouvent leur plateforme grâce à l'historique (Twitch par défaut).
- Un stream arrêté manuellement est noté *arrêté* dans le journal, au lieu d'un code d'erreur.

### Corrigé
- Boucle de redessin infinie dans un champ avec badge.
- `Canvas.lift()` déplaçait les éléments dessinés au lieu du widget.

## 0.3.0 - 2026-10-11

### Ajouté
- `platforms.json` : plateformes définies dans un fichier (Twitch, Kick, YouTube, **Dailymotion**, Steam TV, **Lien direct**). Streamlink est appelé directement, les `.bat` ne sont plus nécessaires.
- Sortie de Streamlink affichée dans le journal de l'application.
- Choix de la qualité, mémorisé par plateforme, listes de secours comprises.
- Choix du lecteur vidéo (par défaut, VLC, mpv, PotPlayer, personnalisé), avec détection automatique du chemin et arguments du lecteur.
- Interface **en français et en anglais** (`lang/fr.json`, `lang/en.json`), dans la langue de Windows par défaut.
- Onglet *Paramètres* : langue, thème, chemin de Streamlink avec un bouton **Tester**, lecteur, scripts personnalisés.

### Modifié
- Les scripts `.bat` personnels restent disponibles en option (*Afficher les scripts .bat*).
- L'application demande confirmation avant de quitter si des streams sont en cours.

## 0.2.0 - 2026-10-11

### Ajouté
- Les favoris mémorisent leur plateforme.
- Le libellé et le champ de saisie s'adaptent au script choisi (chaîne Twitch, ID de vidéo YouTube, rien pour Steam TV).
- Les liens collés sont acceptés (`twitch.tv/…`, `youtube.com/watch?v=…`, `youtu.be/…`).
- `config.json` mémorise le dossier choisi.

### Modifié
- Chemins portables : le dossier codé en dur `C:\Users\…\streams` est supprimé, l'application utilise son propre dossier.

### Sécurité
- Les scripts sont lancés **sans `shell=True`**, et la saisie est validée, ce qui empêche l'injection de commandes via `&`, `|`, `%`…

### Corrigé
- Les anciennes entrées YouTube de l'historique (`ID&list=…`) sont nettoyées à la relance.

## 0.1.0 - 2025-10-16

### Ajouté
- Première version : une fenêtre Tkinter qui liste les scripts `.bat` d'un dossier (Twitch, Kick, YouTube, Steam TV) et les lance avec un nom de chaîne.
- Historique des lancements (200 entrées) et favoris.
- Mode sombre.

> Les versions 0.1.0 à 1.0.0 n'ont jamais été publiées sur GitHub ; la 1.0.1 est la première release. La date de la 0.1.0 est la plus ancienne date trouvée dans les données de l'application.

[Unreleased]: https://github.com/Bulls64/Streamlink-Launcher/compare/v1.5.1...HEAD
[1.5.1]: https://github.com/Bulls64/Streamlink-Launcher/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.5.0
[1.4.3]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.4.3
[Non publié]: https://github.com/Bulls64/Streamlink-Launcher/compare/v1.5.1...HEAD
[1.4.2]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.4.2
[1.4.1]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.4.1
[1.4.0]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.4.0
[1.3.0]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.3.0
[1.2.0]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.2.0
[1.1.0]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.1.0
[1.0.2]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.0.2
[1.0.1]: https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v1.0.1
