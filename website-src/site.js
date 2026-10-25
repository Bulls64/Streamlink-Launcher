(() => {
  const root = document.documentElement;
  const IMG = {{IMG_JSON}};
  const KEY = "slSiteLang";

  /* ---------- textes : le français est dans la page, l'anglais ici ---------- */
  const EN = {
    nav_dl: "Download",
    lang_label: "Language",
    onair: "Two free apps · Windows and Linux",
    h1: '<span class="w">Live,</span> <span class="w">minus</span> <span class="w">the</span> <span class="w"><em>browser</em>.</span>',
    lede: "<strong>Streamlink Launcher</strong> opens Twitch, Kick, YouTube, Dailymotion and Steam TV in VLC, mpv or PotPlayer. <strong>Streamlink Chat</strong> keeps Twitch, Kick and Steam TV chats in a window alongside. Same style, same lightness, no dependencies.",
    demo_aria: "Demo of the launcher's input field",
    demo_label: "<b>Try the launcher's field</b><span>type a channel name or paste a link: the platform is recognized on its own</span>",
    q_aria: "Channel name or link",
    enter: "Enter",
    quality: "Quality",
    launch: "Launch",
    platform: "Platform",
    examples: "Examples:",
    l_h2: "One field, Enter, and the stream opens in your player.",
    l_p: "A lightweight interface for Streamlink, in Python and Tkinter. It remembers your favorites, tells you who is live and launches the stream without Twitch ads, in the player of your choice.",
    views_aria: "Launcher screenshots",
    v_main: "Main screen", v_mini: "Mini mode", v_set: "Settings", v_light: "Light theme",
    lf1: "<dt>Smart field</dt><dd>A channel name or any link. Suggestions come from your favorites and your history.</dd>",
    lf2: "<dt>Live favorites</dt><dd>Stream preview, title and viewers. A Windows notification when a favorite goes live.</dd>",
    lf3: "<dt>Remembered quality</dt><dd>Per platform: <code>best</code>, <code>1080p60</code>, <code>audio_only</code>, or a fallback list such as <code>720p60,720p,best</code>.</dd>",
    lf4: "<dt>Clipboard</dt><dd>A copied link is offered as soon as you come back to the window. You can also drag and drop a link or a <code>.url</code> shortcut.</dd>",
    lf5: "<dt>Notification area</dt><dd>Closing the window leaves the launcher next to the clock, with your streams and live monitoring.</dd>",
    lf6: "<dt>Your platforms</dt><dd>They are described in <code>platforms.json</code>: add your own, with their color.</dd>",
    keys_aria: "Mini mode shortcut",
    combo: "Mini mode: a Spotlight-style floating bar, from any application.",
    s1: "<b>0</b><span>external dependencies: Python and Tkinter</span>",
    s2: "<b>≈ 0.25 s</b><span>start-up from source</span>",
    s3: "<b>≈ 30 MB</b><span>of memory</span>",
    s4: "<b>5</b><span>languages: EN, FR, ES, DE, IT</span>",
    c_h2: "All your chats, one tab each.",
    c_p: "The launcher's companion, in the spirit of Chatterino. Twitch, Kick and Steam TV in a single window, each in its platform's color. Reading needs no account.",
    demo_small: "demo · simulated messages",
    tabs_aria: "Open chats",
    send: "Send",
    paused: "New messages ↓",
    chat_note: "Hover over the chat or scroll up: auto-scroll pauses, just like in the app. On Twitch, write a message; <kbd>Tab</kbd> completes usernames.",
    cf1: "<dt>Readable messages</dt><dd>Badges, username colors adjusted to the theme, emotes as images, animated GIFs included (Twitch, BetterTTV, FrankerFaceZ, 7TV).</dd>",
    cf2: "<dt>Mentions</dt><dd>Messages that mention your username, or words of your choice, are highlighted.</dd>",
    cf3: "<dt>Write</dt><dd>On Twitch and Kick, once logged in. <kbd>Tab</kbd> completes usernames and emotes, <kbd>↑</kbd> recalls your last messages.</dd>",
    cf4: "<dt>Watch</dt><dd>The chat's ▶ button launches the stream with Streamlink.</dd>",
    cf5: "<dt>Protected tokens</dt><dd>On Windows, your logins are encrypted with DPAPI, readable only by your session.</dd>",
    pt_head: "<tr><th>Platform</th><th>Read</th><th>Write</th></tr>",
    pt_body: '<tr><td><i class="pf-twitch"></i>Twitch</td><td>No account</td><td>Once logged in</td></tr>'
      + '<tr><td><i class="pf-kick"></i>Kick</td><td>No account <span class="exp">experimental</span></td><td>Once logged in</td></tr>'
      + '<tr><td><i class="pf-steamtv"></i>Steam TV</td><td>No account</td><td>Read-only</td></tr>',
    alt_ctw: "Streamlink Chat screenshot: Twitch chat tinted purple",
    alt_ckick: "Streamlink Chat screenshot: Kick chat tinted green",
    alt_clight: "Streamlink Chat screenshot in the light theme",
    together: "Together",
    t_h2: "The player on the left, the chat on the right.",
    t1: "<h3>One click to watch</h3><p>In the chat, ▶ launches the stream with the same Streamlink as the launcher. In the launcher, your favorites tell you who is live.</p>",
    t2: "<h3>One look</h3><p>Same drawn components, same platform colors, light, dark or automatic theme that follows Windows.</p>",
    t3: "<h3>Self-updating</h3><p>Each app looks for its new version on GitHub, checks its size and SHA-256, replaces the executable and restarts.</p>",
    dl_tag: "GitHub releases",
    dl_p: 'Free and MIT-licensed. You need <a href="https://streamlink.github.io/install.html" target="_blank" rel="noopener">Streamlink</a> and a video player such as VLC or mpv.',
    size_l_exe: "12.3 MB", size_c_exe: "12.9 MB", size_img: "31.8 MB",
    step_chmod: "On Linux, make the AppImage executable, then run it:",
    step_l2: "On first launch, the launcher finds Streamlink by itself, or tells you how to install it.",
    step_c2: "Type a channel name or paste a Twitch, Kick or Steam TV link. To write, connect your account in <em>Settings › Accounts</em>.",
    src: "Source code", notes: "Release notes",
    trust: "Each release publishes a <code>SHA256SUMS.txt</code> file so you can check what you download. The Windows executables aren't code-signed yet: if SmartScreen shows up, choose <em>More info</em>, then <em>Run anyway</em>.",
    foot1: 'Streamlink Launcher and Streamlink Chat, by <a href="https://github.com/Bulls64" target="_blank" rel="noopener">Bulls64</a>. MIT license.',
    foot2: "Independent projects, not affiliated with Streamlink, Twitch, Kick, YouTube, Dailymotion or Valve.",
  };
  const FR = {};
  document.querySelectorAll("[data-i18n]").forEach(el => { FR[el.dataset.i18n] = el.innerHTML; });
  document.querySelectorAll("[data-i18n-aria]").forEach(el => { FR[el.dataset.i18nAria] = el.getAttribute("aria-label"); });
  document.querySelectorAll("[data-i18n-alt]").forEach(el => { FR[el.dataset.i18nAlt] = el.getAttribute("alt"); });
  const DICT = { fr: FR, en: EN };

  /* espagnol, allemand, italien : textes de la page d'accueil */
  const HOME_TR = {
    es: {
      nav_dl: "Descargar",
      lang_label: "Idioma",
      onair: "Dos aplicaciones libres · Windows y Linux",
      h1: '<span class="w">El</span> <span class="w">directo,</span> <span class="w">fuera</span> <span class="w">del</span> <span class="w"><em>navegador</em>.</span>',
      lede: "<strong>Streamlink Launcher</strong> abre Twitch, Kick, YouTube, Dailymotion y Steam TV en VLC, mpv o PotPlayer. <strong>Streamlink Chat</strong> reúne los chats de Twitch, Kick y Steam TV en una ventana al lado. El mismo estilo, la misma ligereza, sin dependencias.",
      demo_aria: "Demostración del campo del lanzador",
      demo_label: "<b>Prueba el campo del lanzador</b><span>escribe el nombre de un canal o pega un enlace: la plataforma se reconoce sola</span>",
      q_aria: "Nombre del canal o enlace",
      enter: "Intro",
      quality: "Calidad",
      launch: "Iniciar",
      platform: "Plataforma",
      examples: "Ejemplos:",
      l_h2: "Un campo, Intro, y el stream se abre en tu reproductor.",
      l_p: "Una interfaz ligera para Streamlink, en Python y Tkinter. Recuerda tus favoritos, te dice quién está en directo e inicia el stream sin anuncios de Twitch, en el reproductor que elijas.",
      views_aria: "Capturas del lanzador",
      v_main: "Pantalla principal", v_mini: "Modo mini", v_set: "Ajustes", v_light: "Tema claro",
      lf1: "<dt>Campo inteligente</dt><dd>Un nombre de canal o cualquier enlace. Las sugerencias vienen de tus favoritos y de tu historial.</dd>",
      lf2: "<dt>Favoritos en directo</dt><dd>Vista previa del stream, título y espectadores. Una notificación de Windows cuando un favorito empieza un directo.</dd>",
      lf3: "<dt>Calidad recordada</dt><dd>Por plataforma: <code>best</code>, <code>1080p60</code>, <code>audio_only</code>, o una lista de alternativas como <code>720p60,720p,best</code>.</dd>",
      lf4: "<dt>Portapapeles</dt><dd>Un enlace copiado se te propone en cuanto vuelves a la ventana. También puedes arrastrar y soltar un enlace o un acceso directo <code>.url</code>.</dd>",
      lf5: "<dt>Área de notificación</dt><dd>Al cerrar la ventana, el lanzador se queda junto al reloj, con tus streams y la vigilancia de directos.</dd>",
      lf6: "<dt>Tus plataformas</dt><dd>Se describen en <code>platforms.json</code>: añade las tuyas, con su color.</dd>",
      keys_aria: "Atajo del modo mini",
      combo: "Modo mini: una barra flotante al estilo Spotlight, desde cualquier aplicación.",
      s1: "<b>0</b><span>dependencias externas: Python y Tkinter</span>",
      s2: "<b>≈ 0,25 s</b><span>de arranque desde el código fuente</span>",
      s3: "<b>≈ 30 MB</b><span>de memoria</span>",
      s4: "<b>5</b><span>idiomas: EN, FR, ES, DE, IT</span>",
      c_h2: "Todos tus chats, una pestaña cada uno.",
      c_p: "El compañero del lanzador, al estilo de Chatterino. Twitch, Kick y Steam TV en una sola ventana, cada uno con el color de su plataforma. Leer no requiere cuenta.",
      demo_small: "demo · mensajes simulados",
      tabs_aria: "Chats abiertos",
      send: "Enviar",
      paused: "Mensajes nuevos ↓",
      chat_note: "Pasa el ratón por el chat o desplázate hacia arriba: el desplazamiento automático se pausa, igual que en la aplicación. En Twitch, escribe un mensaje; <kbd>Tab</kbd> completa los nombres.",
      cf1: "<dt>Mensajes legibles</dt><dd>Insignias, colores de nombre ajustados al tema, emotes como imágenes, GIF animados incluidos (Twitch, BetterTTV, FrankerFaceZ, 7TV).</dd>",
      cf2: "<dt>Menciones</dt><dd>Los mensajes que mencionan tu nombre, o las palabras que elijas, se resaltan.</dd>",
      cf3: "<dt>Escribir</dt><dd>En Twitch y Kick, tras iniciar sesión. <kbd>Tab</kbd> completa nombres y emotes, <kbd>↑</kbd> recupera tus últimos mensajes.</dd>",
      cf4: "<dt>Ver</dt><dd>El botón ▶ del chat inicia el stream con Streamlink.</dd>",
      cf5: "<dt>Tokens protegidos</dt><dd>En Windows, tus inicios de sesión se cifran con DPAPI y solo tu sesión puede leerlos.</dd>",
      pt_head: "<tr><th>Plataforma</th><th>Lectura</th><th>Escritura</th></tr>",
      pt_body: '<tr><td><i class="pf-twitch"></i>Twitch</td><td>Sin cuenta</td><td>Tras iniciar sesión</td></tr>'
        + '<tr><td><i class="pf-kick"></i>Kick</td><td>Sin cuenta <span class="exp">experimental</span></td><td>Tras iniciar sesión</td></tr>'
        + '<tr><td><i class="pf-steamtv"></i>Steam TV</td><td>Sin cuenta</td><td>Solo lectura</td></tr>',
      alt_ctw: "Captura de Streamlink Chat: chat de Twitch en tono violeta",
      alt_ckick: "Captura de Streamlink Chat: chat de Kick en tono verde",
      alt_clight: "Captura de Streamlink Chat con el tema claro",
      together: "Juntos",
      t_h2: "El reproductor a la izquierda, el chat a la derecha.",
      t1: "<h3>Un clic para ver</h3><p>En el chat, ▶ inicia el stream con el mismo Streamlink que el lanzador. En el lanzador, tus favoritos te dicen quién está en directo.</p>",
      t2: "<h3>Un mismo aspecto</h3><p>Los mismos componentes dibujados, los mismos colores de plataforma, tema claro, oscuro o automático según Windows.</p>",
      t3: "<h3>Se actualizan solas</h3><p>Cada aplicación busca su nueva versión en GitHub, comprueba su tamaño y su SHA-256, sustituye el ejecutable y se reinicia.</p>",
      dl_tag: "Versiones en GitHub",
      dl_p: 'Libres y con licencia MIT. Necesitas <a href="https://streamlink.github.io/install.html" target="_blank" rel="noopener">Streamlink</a> y un reproductor de vídeo como VLC o mpv.',
      size_l_exe: "12,3 MB", size_c_exe: "12,9 MB", size_img: "31,8 MB",
      step_chmod: "En Linux, haz ejecutable la AppImage y luego iníciala:",
      step_l2: "En el primer inicio, el lanzador encuentra Streamlink por sí solo, o te explica cómo instalarlo.",
      step_c2: "Escribe el nombre de un canal o pega un enlace de Twitch, Kick o Steam TV. Para escribir, conecta tu cuenta en <em>Ajustes › Cuentas</em>.",
      src: "Código fuente", notes: "Notas de la versión",
      trust: "Cada versión publica un archivo <code>SHA256SUMS.txt</code> para que compruebes lo que descargas. Los ejecutables de Windows todavía no tienen firma de código: si aparece SmartScreen, elige <em>Más información</em> y luego <em>Ejecutar de todas formas</em>.",
      foot1: 'Streamlink Launcher y Streamlink Chat, por <a href="https://github.com/Bulls64" target="_blank" rel="noopener">Bulls64</a>. Licencia MIT.',
      foot2: "Proyectos independientes, sin relación con Streamlink, Twitch, Kick, YouTube, Dailymotion ni Valve.",
    },
    de: {
      nav_dl: "Download",
      lang_label: "Sprache",
      onair: "Zwei freie Apps · Windows und Linux",
      h1: '<span class="w">Live,</span> <span class="w">aber</span> <span class="w">ohne</span> <span class="w"><em>Browser</em>.</span>',
      lede: "<strong>Streamlink Launcher</strong> öffnet Twitch, Kick, YouTube, Dailymotion und Steam TV in VLC, mpv oder PotPlayer. <strong>Streamlink Chat</strong> hält die Chats von Twitch, Kick und Steam TV in einem Fenster daneben. Gleicher Stil, gleiche Leichtigkeit, keine Abhängigkeiten.",
      demo_aria: "Demo des Eingabefelds des Launchers",
      demo_label: "<b>Probier das Feld des Launchers aus</b><span>gib einen Kanalnamen ein oder füge einen Link ein: Die Plattform wird von selbst erkannt</span>",
      q_aria: "Kanalname oder Link",
      enter: "Enter",
      quality: "Qualität",
      launch: "Starten",
      platform: "Plattform",
      examples: "Beispiele:",
      l_h2: "Ein Feld, Enter, und der Stream öffnet sich in deinem Player.",
      l_p: "Eine schlanke Oberfläche für Streamlink, in Python und Tkinter. Sie merkt sich deine Favoriten, zeigt dir, wer live ist, und startet den Stream ohne Twitch-Werbung im Player deiner Wahl.",
      views_aria: "Screenshots des Launchers",
      v_main: "Hauptbildschirm", v_mini: "Mini-Modus", v_set: "Einstellungen", v_light: "Helles Design",
      lf1: "<dt>Smartes Feld</dt><dd>Ein Kanalname oder ein beliebiger Link. Die Vorschläge kommen aus deinen Favoriten und deinem Verlauf.</dd>",
      lf2: "<dt>Live-Favoriten</dt><dd>Stream-Vorschau, Titel und Zuschauer. Eine Windows-Benachrichtigung, wenn ein Favorit live geht.</dd>",
      lf3: "<dt>Gemerkte Qualität</dt><dd>Pro Plattform: <code>best</code>, <code>1080p60</code>, <code>audio_only</code> oder eine Ausweichliste wie <code>720p60,720p,best</code>.</dd>",
      lf4: "<dt>Zwischenablage</dt><dd>Ein kopierter Link wird dir angeboten, sobald du zum Fenster zurückkehrst. Du kannst auch einen Link oder eine <code>.url</code>-Verknüpfung per Drag-and-drop ablegen.</dd>",
      lf5: "<dt>Infobereich</dt><dd>Beim Schließen des Fensters bleibt der Launcher neben der Uhr, mit deinen Streams und der Live-Überwachung.</dd>",
      lf6: "<dt>Deine Plattformen</dt><dd>Sie sind in <code>platforms.json</code> beschrieben: Füge deine eigenen hinzu, mit ihrer Farbe.</dd>",
      keys_aria: "Tastenkombination des Mini-Modus",
      combo: "Mini-Modus: eine schwebende Leiste im Spotlight-Stil, aus jeder Anwendung.",
      s1: "<b>0</b><span>externe Abhängigkeiten: Python und Tkinter</span>",
      s2: "<b>≈ 0,25 s</b><span>Start aus dem Quellcode</span>",
      s3: "<b>≈ 30 MB</b><span>Arbeitsspeicher</span>",
      s4: "<b>5</b><span>Sprachen: EN, FR, ES, DE, IT</span>",
      c_h2: "Alle deine Chats, jeder in seinem Tab.",
      c_p: "Der Begleiter des Launchers, im Stil von Chatterino. Twitch, Kick und Steam TV in einem einzigen Fenster, jeder in der Farbe seiner Plattform. Zum Lesen brauchst du kein Konto.",
      demo_small: "Demo · simulierte Nachrichten",
      tabs_aria: "Geöffnete Chats",
      send: "Senden",
      paused: "Neue Nachrichten ↓",
      chat_note: "Fahre mit der Maus über den Chat oder scrolle nach oben: Das automatische Scrollen pausiert, genau wie in der App. Schreib auf Twitch eine Nachricht; <kbd>Tab</kbd> vervollständigt Namen.",
      cf1: "<dt>Lesbare Nachrichten</dt><dd>Abzeichen, an das Design angepasste Namensfarben, Emotes als Bilder, animierte GIFs inklusive (Twitch, BetterTTV, FrankerFaceZ, 7TV).</dd>",
      cf2: "<dt>Erwähnungen</dt><dd>Nachrichten, die deinen Namen oder Wörter deiner Wahl enthalten, werden hervorgehoben.</dd>",
      cf3: "<dt>Schreiben</dt><dd>Auf Twitch und Kick, nach der Anmeldung. <kbd>Tab</kbd> vervollständigt Namen und Emotes, <kbd>↑</kbd> holt deine letzten Nachrichten zurück.</dd>",
      cf4: "<dt>Ansehen</dt><dd>Die Schaltfläche ▶ im Chat startet den Stream mit Streamlink.</dd>",
      cf5: "<dt>Geschützte Tokens</dt><dd>Unter Windows sind deine Anmeldungen mit DPAPI verschlüsselt und nur von deiner Sitzung lesbar.</dd>",
      pt_head: "<tr><th>Plattform</th><th>Lesen</th><th>Schreiben</th></tr>",
      pt_body: '<tr><td><i class="pf-twitch"></i>Twitch</td><td>Ohne Konto</td><td>Nach der Anmeldung</td></tr>'
        + '<tr><td><i class="pf-kick"></i>Kick</td><td>Ohne Konto <span class="exp">experimentell</span></td><td>Nach der Anmeldung</td></tr>'
        + '<tr><td><i class="pf-steamtv"></i>Steam TV</td><td>Ohne Konto</td><td>Nur lesen</td></tr>',
      alt_ctw: "Screenshot von Streamlink Chat: Twitch-Chat in Violett",
      alt_ckick: "Screenshot von Streamlink Chat: Kick-Chat in Grün",
      alt_clight: "Screenshot von Streamlink Chat im hellen Design",
      together: "Zusammen",
      t_h2: "Links der Player, rechts der Chat.",
      t1: "<h3>Ein Klick zum Ansehen</h3><p>Im Chat startet ▶ den Stream mit demselben Streamlink wie der Launcher. Im Launcher zeigen dir deine Favoriten, wer live ist.</p>",
      t2: "<h3>Ein Look</h3><p>Dieselben gezeichneten Elemente, dieselben Plattformfarben, helles, dunkles oder automatisches Design nach Windows.</p>",
      t3: "<h3>Aktualisieren sich selbst</h3><p>Jede App sucht ihre neue Version auf GitHub, prüft Größe und SHA-256, ersetzt die ausführbare Datei und startet neu.</p>",
      dl_tag: "Releases auf GitHub",
      dl_p: 'Frei und unter MIT-Lizenz. Du brauchst <a href="https://streamlink.github.io/install.html" target="_blank" rel="noopener">Streamlink</a> und einen Videoplayer wie VLC oder mpv.',
      size_l_exe: "12,3 MB", size_c_exe: "12,9 MB", size_img: "31,8 MB",
      step_chmod: "Unter Linux machst du das AppImage ausführbar und startest es dann:",
      step_l2: "Beim ersten Start findet der Launcher Streamlink von selbst oder erklärt dir, wie du es installierst.",
      step_c2: "Gib einen Kanalnamen ein oder füge einen Twitch-, Kick- oder Steam-TV-Link ein. Zum Schreiben verbindest du dein Konto unter <em>Einstellungen › Konten</em>.",
      src: "Quellcode", notes: "Versionshinweise",
      trust: "Jedes Release veröffentlicht eine Datei <code>SHA256SUMS.txt</code>, damit du prüfen kannst, was du herunterlädst. Die Windows-Programme sind noch nicht signiert: Wenn SmartScreen erscheint, wähle <em>Weitere Informationen</em> und dann <em>Trotzdem ausführen</em>.",
      foot1: 'Streamlink Launcher und Streamlink Chat, von <a href="https://github.com/Bulls64" target="_blank" rel="noopener">Bulls64</a>. MIT-Lizenz.',
      foot2: "Unabhängige Projekte, ohne Verbindung zu Streamlink, Twitch, Kick, YouTube, Dailymotion oder Valve.",
    },
    it: {
      nav_dl: "Scarica",
      lang_label: "Lingua",
      onair: "Due app libere · Windows e Linux",
      h1: '<span class="w">La</span> <span class="w">diretta</span> <span class="w">esce</span> <span class="w">dal</span> <span class="w"><em>browser</em>.</span>',
      lede: "<strong>Streamlink Launcher</strong> apre Twitch, Kick, YouTube, Dailymotion e Steam TV in VLC, mpv o PotPlayer. <strong>Streamlink Chat</strong> tiene le chat di Twitch, Kick e Steam TV in una finestra accanto. Stesso stile, stessa leggerezza, nessuna dipendenza.",
      demo_aria: "Demo del campo del launcher",
      demo_label: "<b>Prova il campo del launcher</b><span>scrivi il nome di un canale o incolla un link: la piattaforma viene riconosciuta da sola</span>",
      q_aria: "Nome del canale o link",
      enter: "Invio",
      quality: "Qualità",
      launch: "Avvia",
      platform: "Piattaforma",
      examples: "Esempi:",
      l_h2: "Un campo, Invio, e lo stream si apre nel tuo lettore.",
      l_p: "Un'interfaccia leggera per Streamlink, in Python e Tkinter. Ricorda i tuoi preferiti, ti dice chi è in diretta e avvia lo stream senza pubblicità di Twitch, nel lettore che preferisci.",
      views_aria: "Screenshot del launcher",
      v_main: "Schermata principale", v_mini: "Modalità mini", v_set: "Impostazioni", v_light: "Tema chiaro",
      lf1: "<dt>Campo intelligente</dt><dd>Un nome di canale o qualsiasi link. I suggerimenti vengono dai tuoi preferiti e dalla cronologia.</dd>",
      lf2: "<dt>Preferiti in diretta</dt><dd>Anteprima dello stream, titolo e spettatori. Una notifica di Windows quando un preferito va in diretta.</dd>",
      lf3: "<dt>Qualità ricordata</dt><dd>Per piattaforma: <code>best</code>, <code>1080p60</code>, <code>audio_only</code>, o un elenco di riserva come <code>720p60,720p,best</code>.</dd>",
      lf4: "<dt>Appunti</dt><dd>Un link copiato ti viene proposto appena torni alla finestra. Puoi anche trascinare un link o un collegamento <code>.url</code>.</dd>",
      lf5: "<dt>Area di notifica</dt><dd>Chiudendo la finestra, il launcher resta accanto all'orologio, con i tuoi stream e il controllo delle dirette.</dd>",
      lf6: "<dt>Le tue piattaforme</dt><dd>Sono descritte in <code>platforms.json</code>: aggiungi le tue, con il loro colore.</dd>",
      keys_aria: "Scorciatoia della modalità mini",
      combo: "Modalità mini: una barra mobile in stile Spotlight, da qualsiasi applicazione.",
      s1: "<b>0</b><span>dipendenze esterne: Python e Tkinter</span>",
      s2: "<b>≈ 0,25 s</b><span>di avvio dal codice sorgente</span>",
      s3: "<b>≈ 30 MB</b><span>di memoria</span>",
      s4: "<b>5</b><span>lingue: EN, FR, ES, DE, IT</span>",
      c_h2: "Tutte le tue chat, una scheda ciascuna.",
      c_p: "Il compagno del launcher, nello spirito di Chatterino. Twitch, Kick e Steam TV in un'unica finestra, ognuna con il colore della sua piattaforma. Per leggere non serve un account.",
      demo_small: "demo · messaggi simulati",
      tabs_aria: "Chat aperte",
      send: "Invia",
      paused: "Nuovi messaggi ↓",
      chat_note: "Passa il mouse sulla chat o scorri verso l'alto: lo scorrimento automatico si mette in pausa, proprio come nell'app. Su Twitch, scrivi un messaggio; <kbd>Tab</kbd> completa i nomi.",
      cf1: "<dt>Messaggi leggibili</dt><dd>Badge, colori dei nomi adattati al tema, emote come immagini, GIF animate comprese (Twitch, BetterTTV, FrankerFaceZ, 7TV).</dd>",
      cf2: "<dt>Menzioni</dt><dd>I messaggi che citano il tuo nome, o parole a tua scelta, vengono evidenziati.</dd>",
      cf3: "<dt>Scrivere</dt><dd>Su Twitch e Kick, dopo l'accesso. <kbd>Tab</kbd> completa nomi ed emote, <kbd>↑</kbd> richiama i tuoi ultimi messaggi.</dd>",
      cf4: "<dt>Guardare</dt><dd>Il pulsante ▶ della chat avvia lo stream con Streamlink.</dd>",
      cf5: "<dt>Token protetti</dt><dd>Su Windows, i tuoi accessi sono cifrati con DPAPI e leggibili solo dalla tua sessione.</dd>",
      pt_head: "<tr><th>Piattaforma</th><th>Lettura</th><th>Scrittura</th></tr>",
      pt_body: '<tr><td><i class="pf-twitch"></i>Twitch</td><td>Senza account</td><td>Dopo l\'accesso</td></tr>'
        + '<tr><td><i class="pf-kick"></i>Kick</td><td>Senza account <span class="exp">sperimentale</span></td><td>Dopo l\'accesso</td></tr>'
        + '<tr><td><i class="pf-steamtv"></i>Steam TV</td><td>Senza account</td><td>Sola lettura</td></tr>',
      alt_ctw: "Screenshot di Streamlink Chat: chat di Twitch in viola",
      alt_ckick: "Screenshot di Streamlink Chat: chat di Kick in verde",
      alt_clight: "Screenshot di Streamlink Chat con il tema chiaro",
      together: "Insieme",
      t_h2: "Il lettore a sinistra, la chat a destra.",
      t1: "<h3>Un clic per guardare</h3><p>Nella chat, ▶ avvia lo stream con lo stesso Streamlink del launcher. Nel launcher, i tuoi preferiti ti dicono chi è in diretta.</p>",
      t2: "<h3>Un unico stile</h3><p>Gli stessi componenti disegnati, gli stessi colori delle piattaforme, tema chiaro, scuro o automatico che segue Windows.</p>",
      t3: "<h3>Si aggiornano da sole</h3><p>Ogni app cerca la nuova versione su GitHub, ne verifica dimensione e SHA-256, sostituisce l'eseguibile e si riavvia.</p>",
      dl_tag: "Release su GitHub",
      dl_p: 'Libere e con licenza MIT. Ti servono <a href="https://streamlink.github.io/install.html" target="_blank" rel="noopener">Streamlink</a> e un lettore video come VLC o mpv.',
      size_l_exe: "12,3 MB", size_c_exe: "12,9 MB", size_img: "31,8 MB",
      step_chmod: "Su Linux, rendi eseguibile l'AppImage, poi avviala:",
      step_l2: "Al primo avvio, il launcher trova Streamlink da solo, o ti spiega come installarlo.",
      step_c2: "Scrivi il nome di un canale o incolla un link di Twitch, Kick o Steam TV. Per scrivere, collega il tuo account in <em>Impostazioni › Account</em>.",
      src: "Codice sorgente", notes: "Note di rilascio",
      trust: "Ogni release pubblica un file <code>SHA256SUMS.txt</code> per verificare ciò che scarichi. Gli eseguibili di Windows non hanno ancora una firma del codice: se compare SmartScreen, scegli <em>Ulteriori informazioni</em>, poi <em>Esegui comunque</em>.",
      foot1: 'Streamlink Launcher e Streamlink Chat, di <a href="https://github.com/Bulls64" target="_blank" rel="noopener">Bulls64</a>. Licenza MIT.',
      foot2: "Progetti indipendenti, senza legami con Streamlink, Twitch, Kick, YouTube, Dailymotion o Valve.",
    },
  };
  /* espagnol, allemand, italien : textes produits par le script de la page d'accueil */
  const T_TR = {
    es: {
      ph: { twitch: "Nombre del canal de Twitch o enlace…", kick: "Nombre del canal de Kick o enlace…", youtube: "ID o enlace del vídeo de YouTube…",
            dailymotion: "ID o enlace del vídeo de Dailymotion…", steamtv: "Enlace de steam.tv (opcional)…", url: "Cualquier enlace compatible con Streamlink…" },
      direct: "Enlace directo",
      e_empty: "Escribe el nombre de un canal o pega un enlace.", e_chan: "Nombre de canal no válido: solo letras, cifras y _.",
      e_yt: "Un ID de YouTube tiene 11 caracteres, o pega el enlace del vídeo.", e_vid: "ID de vídeo no válido, o pega el enlace del vídeo.",
      e_url: "Pega un enlace completo, que empiece por https://", e_noch: "A este enlace le falta el nombre del canal.",
      cmd: p => `# ${p} reconocido · comando enviado a Streamlink`,
      idle: "Ningún stream en curso",
      run: n => `${n} stream${n > 1 ? "s" : ""} en curso`, demo: "(demo: en realidad no se abre nada)",
      alt: { l_main: "Pantalla principal de Streamlink Launcher con el tema oscuro: campo de búsqueda, plataformas, favoritos en directo con vistas previas y número de espectadores, recientes.",
             l_mini: "El modo mini de Streamlink Launcher: barra flotante con la lista de favoritos y su número de espectadores.",
             l_set: "El panel de ajustes de Streamlink Launcher.", l_light: "Pantalla principal de Streamlink Launcher con el tema claro." },
      copy: "Copiar", copied: "Copiado",
      lines: {
        twitch: ["gg wp, menuda ronda [e]", "ese flick [e] [e]", "ha fallado el clutch", "@chris ¿ves la final esta noche?", "smoke perfecta en B",
          "El torneo se reanuda en 5 minutos: https://eslgaming.com/cs", "TIMEOUT [e2]", "¿prórroga o no?", "menudo retake [e]", "repetición porfa",
          "los dos equipos están on fire", "1v3 increíble [e] [e]", "queremos el mapa 3", "@chris ¿has visto esa jugada?"],
        kick: ["W stream", "es demasiado bueno", "clipéalo", "[e2] [e2]", "hoy el sonido va mejor", "chat, con respeto", "¿cuántos somos ya?", "W", "lo va a conseguir", "@chris ¡hola!"],
        steamtv: ["[e] el nuevo parche", "qué ganas de probarlo", "¿ya está la demo?", "gg", "¿cuándo sale?", "el estilo artístico es una locura", "en la lista de deseos [e]"],
      },
      ev: { twitch: (n, m) => `¡${n} se ha suscrito con el nivel 1 durante ${m} meses!`, kick: n => `¡${n} acaba de suscribirse!` },
      spam: "compra seguidores en mi web",
      ch: { twitch: ["Twitch · Conectado", "Escribe en el chat de eslcs"], kick: ["Kick · Solo lectura", "Solo lectura: inicia sesión en Kick para escribir"],
            steamtv: ["Steam TV · Solo lectura", "Chat de Steam TV de solo lectura"] },
    },
    de: {
      ph: { twitch: "Twitch-Kanalname oder Link…", kick: "Kick-Kanalname oder Link…", youtube: "YouTube-Video-ID oder Link…",
            dailymotion: "Dailymotion-Video-ID oder Link…", steamtv: "steam.tv-Link (optional)…", url: "Jeder von Streamlink unterstützte Link…" },
      direct: "Direktlink",
      e_empty: "Gib einen Kanalnamen ein oder füge einen Link ein.", e_chan: "Ungültiger Kanalname: nur Buchstaben, Ziffern und _.",
      e_yt: "Eine YouTube-ID hat 11 Zeichen, oder füge den Link des Videos ein.", e_vid: "Ungültige Video-ID, oder füge den Link des Videos ein.",
      e_url: "Füge einen vollständigen Link ein, der mit https:// beginnt", e_noch: "In diesem Link fehlt der Kanalname.",
      cmd: p => `# ${p} erkannt · Befehl an Streamlink gesendet`,
      idle: "Kein Stream aktiv",
      run: n => `${n} Stream${n > 1 ? "s" : ""} aktiv`, demo: "(Demo: Es öffnet sich nichts wirklich)",
      alt: { l_main: "Hauptbildschirm von Streamlink Launcher im dunklen Design: Suchfeld, Plattformen, Live-Favoriten mit Vorschau und Zuschauerzahl, zuletzt gesehen.",
             l_mini: "Der Mini-Modus von Streamlink Launcher: schwebende Leiste mit der Liste der Favoriten und ihrer Zuschauerzahl.",
             l_set: "Die Einstellungen von Streamlink Launcher.", l_light: "Hauptbildschirm von Streamlink Launcher im hellen Design." },
      copy: "Kopieren", copied: "Kopiert",
      lines: {
        twitch: ["gg wp, was für eine Runde [e]", "dieser Flick [e] [e]", "er hat den Clutch verpasst", "@chris schaust du heute Abend das Finale?", "perfekte Smoke auf B",
          "Das Turnier geht in 5 Minuten weiter: https://eslgaming.com/cs", "TIMEOUT [e2]", "Overtime oder nicht?", "was für ein Retake [e]", "Replay bitte",
          "beide Teams sind heiß", "unglaubliches 1v3 [e] [e]", "wir wollen Map 3", "@chris hast du den Move gesehen"],
        kick: ["W Stream", "er ist einfach zu gut", "clippt das", "[e2] [e2]", "der Ton ist heute besser", "Chat, bleibt freundlich", "wie viele sind wir gerade?", "W", "er schafft das", "@chris hi!"],
        steamtv: ["[e] der neue Patch", "kann es kaum erwarten, das zu testen", "ist die Demo schon draußen?", "gg", "wann erscheint es?", "der Artstyle ist krass", "auf der Wunschliste [e]"],
      },
      ev: { twitch: (n, m) => `${n} hat seit ${m} Monaten Stufe 1 abonniert!`, kick: n => `${n} hat gerade abonniert!` },
      spam: "kauft Follower auf meiner Seite",
      ch: { twitch: ["Twitch · Verbunden", "In den Chat von eslcs schreiben"], kick: ["Kick · Nur lesen", "Nur lesen — bei Kick anmelden, um zu schreiben"],
            steamtv: ["Steam TV · Nur lesen", "Steam-TV-Chat nur lesbar"] },
    },
    it: {
      ph: { twitch: "Nome del canale Twitch o link…", kick: "Nome del canale Kick o link…", youtube: "ID o link del video YouTube…",
            dailymotion: "ID o link del video Dailymotion…", steamtv: "Link steam.tv (facoltativo)…", url: "Qualsiasi link supportato da Streamlink…" },
      direct: "Link diretto",
      e_empty: "Scrivi il nome di un canale o incolla un link.", e_chan: "Nome del canale non valido: solo lettere, cifre e _.",
      e_yt: "Un ID di YouTube è lungo 11 caratteri, oppure incolla il link del video.", e_vid: "ID del video non valido, oppure incolla il link del video.",
      e_url: "Incolla un link completo, che inizi con https://", e_noch: "In questo link manca il nome del canale.",
      cmd: p => `# ${p} riconosciuto · comando inviato a Streamlink`,
      idle: "Nessuno stream in corso",
      run: n => `${n} stream in corso`, demo: "(demo: in realtà non si apre nulla)",
      alt: { l_main: "Schermata principale di Streamlink Launcher con il tema scuro: campo di ricerca, piattaforme, preferiti in diretta con anteprime e numero di spettatori, recenti.",
             l_mini: "La modalità mini di Streamlink Launcher: barra mobile con l'elenco dei preferiti e il loro numero di spettatori.",
             l_set: "Il pannello delle impostazioni di Streamlink Launcher.", l_light: "Schermata principale di Streamlink Launcher con il tema chiaro." },
      copy: "Copia", copied: "Copiato",
      lines: {
        twitch: ["gg wp, che round [e]", "quel flick [e] [e]", "ha sbagliato il clutch", "@chris guardi la finale stasera?", "smoke perfetta su B",
          "Il torneo riprende tra 5 minuti: https://eslgaming.com/cs", "TIMEOUT [e2]", "overtime o no?", "che retake [e]", "replay pls",
          "entrambe le squadre sono in forma", "1v3 pazzesco [e] [e]", "vogliamo la mappa 3", "@chris hai visto quella giocata"],
        kick: ["W stream", "è troppo forte", "clippate", "[e2] [e2]", "oggi l'audio è migliore", "chat, restiamo civili", "quanti siamo adesso?", "W", "ce la fa", "@chris ciao!"],
        steamtv: ["[e] la nuova patch", "non vedo l'ora di provarlo", "la demo è uscita?", "gg", "quando esce?", "lo stile artistico è pazzesco", "in lista desideri [e]"],
      },
      ev: { twitch: (n, m) => `${n} si è abbonato al livello 1 da ${m} mesi!`, kick: n => `${n} si è appena abbonato!` },
      spam: "comprate follower sul mio sito",
      ch: { twitch: ["Twitch · Connesso", "Scrivi nella chat di eslcs"], kick: ["Kick · Sola lettura", "Sola lettura — accedi a Kick per scrivere"],
            steamtv: ["Steam TV · Sola lettura", "Chat di Steam TV in sola lettura"] },
    },
  };
  for (const l in HOME_TR) DICT[l] = Object.assign({}, EN, HOME_TR[l]);

  /* textes produits par le script */
  const T = {
    fr: {
      ph: { twitch: "Nom de la chaîne Twitch ou lien…", kick: "Nom de la chaîne Kick ou lien…", youtube: "ID ou lien de la vidéo YouTube…",
            dailymotion: "ID ou lien de la vidéo Dailymotion…", steamtv: "Lien steam.tv (facultatif)…", url: "N'importe quel lien pris en charge par Streamlink…" },
      direct: "Lien direct",
      e_empty: "Tape un nom de chaîne ou colle un lien.", e_chan: "Nom de chaîne invalide : lettres, chiffres et _ uniquement.",
      e_yt: "Un ID YouTube fait 11 caractères, ou colle le lien de la vidéo.", e_vid: "ID de vidéo invalide, ou colle le lien de la vidéo.",
      e_url: "Colle un lien complet, qui commence par https://", e_noch: "Il manque le nom de la chaîne dans ce lien.",
      cmd: p => `# ${p} reconnu · commande envoyée à Streamlink`,
      idle: "Aucun stream en cours",
      run: n => `${n} stream${n > 1 ? "s" : ""} en cours`, demo: "(démo : rien ne s'ouvre vraiment)",
      alt: { l_main: "Écran principal de Streamlink Launcher en thème sombre : champ de recherche, plateformes, favoris en direct avec aperçus et nombre de spectateurs, récents.",
             l_mini: "Le mode mini de Streamlink Launcher : barre flottante avec la liste des favoris et leur nombre de spectateurs.",
             l_set: "Le panneau Paramètres de Streamlink Launcher.", l_light: "Écran principal de Streamlink Launcher en thème clair." },
      copy: "Copier", copied: "Copié",
      lines: {
        twitch: ["gg wp, quelle manche [e]", "ce flick [e] [e]", "il a raté le clutch", "@chris tu regardes la finale ce soir ?", "la smoke parfaite sur B",
          "Le tournoi reprend dans 5 minutes : https://eslgaming.com/cs", "TIMEOUT [e2]", "overtime ou pas ?", "mais quel retake [e]", "replay svp",
          "les deux équipes sont chaudes", "1v3 incroyable [e] [e]", "on veut la carte 3", "@chris t'as vu ce move"],
        kick: ["W stream", "il est trop fort", "clip ça", "[e2] [e2]", "le son est mieux aujourd'hui", "chat on reste poli", "on est combien là ?", "W", "il va le faire", "@chris salut !"],
        steamtv: ["[e] le nouveau patch", "trop hâte de tester", "la démo est dispo ?", "gg", "il sort quand ?", "la DA est folle", "wishlisté [e]"],
      },
      ev: { twitch: (n, m) => `${n} s'est abonné(e) au niveau 1 depuis ${m} mois !`, kick: n => `${n} vient de s'abonner !` },
      spam: "achetez des followers sur mon site",
      ch: { twitch: ["Twitch · Connecté", "Écrire dans le chat de eslcs"], kick: ["Kick · Lecture seule", "Lecture seule — connecte-toi à Kick pour écrire"],
            steamtv: ["Steam TV · Lecture seule", "Chat Steam TV en lecture seule"] },
    },
    en: {
      ph: { twitch: "Twitch channel name or link…", kick: "Kick channel name or link…", youtube: "YouTube video ID or link…",
            dailymotion: "Dailymotion video ID or link…", steamtv: "steam.tv link (optional)…", url: "Any link Streamlink supports…" },
      direct: "Direct link",
      e_empty: "Type a channel name or paste a link.", e_chan: "Invalid channel name: letters, digits and _ only.",
      e_yt: "A YouTube ID is 11 characters long, or paste the video's link.", e_vid: "Invalid video ID, or paste the video's link.",
      e_url: "Paste a full link, starting with https://", e_noch: "This link is missing the channel name.",
      cmd: p => `# ${p} recognized · command sent to Streamlink`,
      idle: "No stream running",
      run: n => `${n} stream${n > 1 ? "s" : ""} running`, demo: "(demo: nothing actually opens)",
      alt: { l_main: "Streamlink Launcher main screen, dark theme: search field, platforms, live favorites with previews and viewer counts, recent launches.",
             l_mini: "Streamlink Launcher mini mode: floating bar listing favorites and their viewer counts.",
             l_set: "Streamlink Launcher settings panel.", l_light: "Streamlink Launcher main screen, light theme." },
      copy: "Copy", copied: "Copied",
      lines: {
        twitch: ["gg wp, what a round [e]", "that flick [e] [e]", "he missed the clutch", "@chris are you watching the final tonight?", "perfect smoke on B",
          "The tournament resumes in 5 minutes: https://eslgaming.com/cs", "TIMEOUT [e2]", "overtime or not?", "what a retake [e]", "replay pls",
          "both teams are on fire", "insane 1v3 [e] [e]", "we want map 3", "@chris did you see that move"],
        kick: ["W stream", "he's way too good", "clip it", "[e2] [e2]", "audio is better today", "chat stay civil", "how many of us are here?", "W", "he's gonna do it", "@chris hi!"],
        steamtv: ["[e] the new patch", "can't wait to try it", "is the demo out?", "gg", "when does it release?", "the art style is insane", "wishlisted [e]"],
      },
      ev: { twitch: (n, m) => `${n} subscribed at Tier 1 for ${m} months!`, kick: n => `${n} just subscribed!` },
      spam: "buy followers on my site",
      ch: { twitch: ["Twitch · Connected", "Write in eslcs's chat"], kick: ["Kick · Read-only", "Read-only — log in to Kick to write"],
            steamtv: ["Steam TV · Read-only", "Steam TV chat is read-only"] },
    },
  };
  for (const l in T_TR) { T[l] = Object.assign({}, T.en, T_TR[l]); IMG[l] = IMG.en; }
  let lang = "fr";
  const t = () => T[lang];

  /* ---------- plateformes (tirées de platforms.json du lanceur) ---------- */
  const PLATFORMS = [
    { id: "twitch", name: "Twitch", dot: "#9146FF", input: "channel", url: a => `https://www.twitch.tv/${a}`, args: ["--twitch-disable-ads"],
      q: ["best", "1080p60", "720p60", "720p", "480p", "360p", "160p", "audio_only", "worst"] },
    { id: "kick", name: "Kick", dot: "#53FC18", input: "channel", url: a => `https://kick.com/${a}`, args: [],
      q: ["best", "1080p60", "720p60", "480p30", "360p30", "160p30", "worst"] },
    { id: "youtube", name: "YouTube", dot: "#D91A1A", input: "youtube", url: a => `https://www.youtube.com/watch?v=${a}`, args: [],
      q: ["best", "1080p", "720p", "480p", "360p", "worst"] },
    { id: "dailymotion", name: "Dailymotion", dot: "#0A6CFF", input: "video", url: a => `https://www.dailymotion.com/video/${a}`, args: [],
      q: ["best", "1080p", "720p", "480p", "worst"] },
    { id: "steamtv", name: "Steam TV", dot: "#66C0F4", input: "none", url: () => "https://steam.tv", args: [],
      q: ["best", "worst"] },
    { id: "url", name: null, dot: "#6B7180", input: "url", url: a => a, args: [],
      q: ["best", "1080p", "720p", "480p", "worst"] },
  ];
  const pname = p => p.name || t().direct;
  const byId = Object.fromEntries(PLATFORMS.map(p => [p.id, p]));
  const HOSTS = [
    ["twitch", ["twitch.tv"]], ["kick", ["kick.com"]], ["youtube", ["youtube.com", "youtu.be"]],
    ["dailymotion", ["dailymotion.com", "dai.ly"]], ["steamtv", ["steam.tv", "steamcommunity.com"]],
  ];

  const q = document.getElementById("q"), qual = document.getElementById("quality"), term = document.getElementById("term");
  const pills = document.getElementById("pills"), statusEl = document.getElementById("status"), statusText = document.getElementById("status-text");
  let current = "twitch";
  const chosenQuality = {};
  const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function drawPills() {
    pills.innerHTML = "";
    PLATFORMS.forEach(p => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "pill"; b.dataset.id = p.id; b.style.setProperty("--dot", p.dot);
      b.setAttribute("aria-pressed", String(p.id === current));
      b.innerHTML = `<i></i>${esc(pname(p))}`;
      b.addEventListener("click", () => { setPlatform(p.id, true); update(); q.focus(); });
      pills.appendChild(b);
    });
  }

  function setPlatform(id, manual) {
    current = id;
    root.dataset.platform = id;
    pills.querySelectorAll(".pill").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.id === id)));
    const p = byId[id];
    q.placeholder = t().ph[id];
    qual.innerHTML = p.q.map(v => `<option${v === (chosenQuality[id] || p.q[0]) ? " selected" : ""}>${v}</option>`).join("");
    if (manual) chosenQuality[id] = chosenQuality[id] || p.q[0];
  }

  /* Reconnaît un lien comme le lanceur : (plateforme, adresse) ou null. */
  function detect(text) {
    let s = text.trim();
    if (!s) return null;
    if (!/^[a-z]+:\/\//i.test(s) && /^[\w-]+(\.[\w-]+)+(\/|$)/.test(s)) s = "https://" + s;
    let u;
    try { u = new URL(s); } catch { return null; }
    if (!/^https?:$/.test(u.protocol)) return null;
    const host = u.hostname.replace(/^(www|m)\./, "");
    for (const [id, hosts] of HOSTS) {
      if (!hosts.some(h => host === h || host.endsWith("." + h))) continue;
      if (id === "steamtv" && host.endsWith("steamcommunity.com") && !u.pathname.startsWith("/broadcast/watch/")) return { id: "url", url: u.href };
      if (id === "twitch" || id === "kick") {
        const parts = u.pathname.split("/").filter(Boolean);
        const ch = parts[0] === "popout" ? parts[1] : parts[0];
        if (!ch) return { id, url: null };
        return { id, url: byId[id].url(ch.toLowerCase()), name: ch.toLowerCase() };
      }
      return { id, url: u.href };
    }
    return { id: "url", url: u.href };
  }

  function resolve() {
    const raw = q.value.trim();
    const found = detect(raw);
    if (found) return found;
    const p = byId[current];
    if (!raw) return p.input === "none" ? { id: current, url: p.url("") } : { id: current, error: t().e_empty };
    if (p.input === "channel") {
      if (!/^[A-Za-z0-9_]{2,25}$/.test(raw)) return { id: current, error: t().e_chan };
      return { id: current, url: p.url(raw.toLowerCase()), name: raw.toLowerCase() };
    }
    if (p.input === "youtube") {
      if (!/^[\w-]{11}$/.test(raw)) return { id: current, error: t().e_yt };
      return { id: current, url: p.url(raw) };
    }
    if (p.input === "video") {
      if (!/^[\w]{5,12}$/.test(raw)) return { id: current, error: t().e_vid };
      return { id: current, url: p.url(raw) };
    }
    if (p.input === "none") return { id: current, url: p.url("") };
    return { id: current, error: t().e_url };
  }

  function update() {
    const r = resolve();
    if (r.id !== current) setPlatform(r.id, false);
    const p = byId[current];
    const quality = qual.value || p.q[0];
    if (r.error || !r.url) {
      term.innerHTML = `<span class="pr">$ </span><span class="err">${esc(r.error || t().e_noch)}</span>`;
      return null;
    }
    const args = p.args.map(a => ` <span class="opt">${a}</span>`).join("");
    term.innerHTML = `<span class="cm">${esc(t().cmd(pname(p)))}</span>\n<span class="l2"><span class="pr">$ </span>streamlink${args} <span class="url">${esc(r.url)}</span> <span class="q">${esc(quality)}</span></span>`;
    return { ...r, quality };
  }

  let running = [];
  function drawStatus() {
    if (!running.length) { statusEl.classList.remove("running"); statusText.textContent = t().idle; return; }
    statusEl.classList.add("running");
    statusText.innerHTML = `<strong>${t().run(running.length)}</strong> · ${running.map(esc).join(", ")} <span class="demo-note">${t().demo}</span>`;
  }
  function launch() {
    const r = update();
    if (!r) { q.focus(); return; }
    const label = r.name || (byId[r.id].input === "none" ? "Steam TV" : r.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 42));
    running = [label, ...running.filter(x => x !== label)].slice(0, 3);
    drawStatus();
  }

  q.addEventListener("input", update);
  q.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); launch(); } });
  qual.addEventListener("change", () => { chosenQuality[current] = qual.value; update(); });
  document.getElementById("go").addEventListener("click", launch);
  document.querySelectorAll("[data-ex]").forEach(b => b.addEventListener("click", () => { q.value = b.dataset.ex; update(); q.focus(); }));

  /* ---------- captures du lanceur ---------- */
  const shot = document.getElementById("shot");
  let shotKey = "l_main";
  function drawShots() {
    shot.src = IMG[lang][shotKey]; shot.alt = t().alt[shotKey];
    document.querySelectorAll("[data-img]").forEach(img => { img.src = IMG[lang][img.dataset.img]; });
  }
  document.querySelectorAll("[data-shot]").forEach(b => b.addEventListener("click", () => {
    shotKey = b.dataset.shot; drawShots();
    document.querySelectorAll("[data-shot]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  }));

  /* ---------- raccourci du mode mini ---------- */
  const keys = [...document.querySelectorAll("#keys kbd")];
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  /* les animations et la démo du chat ne tournent que si on les voit (onglet affiché, élément à l'écran) */
  const seen = new Set();
  const visible = el => seen.has(el) && !document.hidden;
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => es.forEach(e => (e.isIntersecting ? seen.add(e.target) : seen.delete(e.target))), { rootMargin: "200px 0px" });
    [document.getElementById("keys"), document.getElementById("chatbox")].forEach(el => el && io.observe(el));
  } else { [document.getElementById("keys"), document.getElementById("chatbox")].forEach(el => el && seen.add(el)); }
  const keysBox = document.getElementById("keys");
  if (!reduce) {
    setInterval(() => {
      if (!visible(keysBox)) return;
      keys.forEach((k, i) => setTimeout(() => k.classList.add("press"), i * 140));
      setTimeout(() => keys.forEach(k => k.classList.remove("press")), 900);
    }, 4200);
  }

  /* ---------- démo du chat ---------- */
  const BADGE = { mod: ["#00AD03", "✓"], vip: ["#E005B9", "◆"], sub: ["#8205B4", "★"], broad: ["#E91916", "●"], og: ["#53FC18", "♦"] };
  const NAMES = {
    twitch: [["Okayeg", "#FF7F50", ["mod", "sub"]], ["Marie_Lune", "#2ECC71", []], ["zywoo_fan", "#DAA520", ["sub"]], ["dark_knight", "#8A7BFF", ["vip"]],
      ["NightBot", "#7B68EE", ["mod"]], ["kraken_92", "#1E90FF", []], ["poulpe_rose", "#FF69B4", ["sub"]], ["Tonio", "#00CED1", []], ["lea_gg", "#9ACD32", ["sub"]]],
    kick: [["KickUser42", "#53FC18", ["og"]], ["salty_sam", "#F7A440", []], ["mr_clip", "#FF6B6B", ["sub"]], ["nova", "#4FC3F7", []], ["zedd_23", "#C792EA", ["vip"]], ["lucky7", "#FFD54F", []]],
    steamtv: [["Gabe_N_Friends", "#8FB8DE", []], ["hat_collector", "#C7D5E0", []], ["pudge_main", "#A3CF6E", []], ["roshan", "#E0A458", []], ["lina_inverse", "#F08A8A", []]],
  };
  const CHANNELS = [
    { p: "twitch", name: "eslcs", color: "#9146FF", on: "#FFFFFF", write: true },
    { p: "kick", name: "xqc", color: "#53FC18", on: "#0B0D0A", write: false },
    { p: "steamtv", name: "steamtv", color: "#2A475E", on: "#C7D5E0", write: false },
  ];
  const chatbox = document.getElementById("chatbox"), log = document.getElementById("log"), tabsEl = document.getElementById("tabs");
  const say = document.getElementById("say"), send = document.getElementById("send"), pausedBtn = document.getElementById("paused");
  let store = { twitch: [], kick: [], steamtv: [] };
  const unread = { twitch: 0, kick: 6, steamtv: 0 };
  let active = "twitch", hover = false, follow = true, minute = 20 * 60 + 41;
  const rnd = a => a[Math.floor(Math.random() * a.length)];

  function clock() { minute = (minute + (Math.random() < .35 ? 1 : 0)) % 1440; return `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`; }
  function render(text) {
    return esc(text)
      .replace(/https?:\/\/\S+/g, m => `<a href="${m}" target="_blank" rel="noopener" class="lnk">${m}</a>`)
      .replace(/@(\w+)/g, '<b>@$1</b>')
      .replace(/\[e\]/g, '<svg class="emo" aria-label="emote"><use href="#emo"/></svg>')
      .replace(/\[e2\]/g, '<svg class="emo" aria-label="emote"><use href="#emo2"/></svg>');
  }
  function makeMsg(p) {
    const r = Math.random();
    const ev = t().ev[p];
    if (ev && r < .07) return { kind: "event", text: ev(rnd(NAMES[p])[0], 2 + Math.floor(Math.random() * 30)) };
    const [name, color, badges] = rnd(NAMES[p]);
    const text = rnd(t().lines[p]);
    return { name, color, badges, text, mention: /@chris/.test(text), first: r > .93, t: clock() };
  }
  function node(m) {
    const d = document.createElement("div");
    d.className = "msg" + (m.kind === "event" ? " event" : "") + (m.mention ? " mention" : "") + (m.first ? " first" : "") + (m.deleted ? " deleted" : "");
    if (m.kind === "event") { d.innerHTML = `<time>${m.t || clock()}</time>${esc(m.text)}`; return d; }
    const bd = m.badges.map(b => `<span class="bd" style="background:${BADGE[b][0]}">${BADGE[b][1]}</span>`).join("");
    d.innerHTML = `<time>${m.t}</time>${bd}<span class="u" style="color:${m.color}">${esc(m.name)}</span>: ${render(m.text)}`;
    return d;
  }
  function atBottom() { return log.scrollHeight - log.scrollTop - log.clientHeight < 24; }
  function push(p, m, animate) {
    store[p].push(m); if (store[p].length > 80) store[p].shift();
    if (p !== active) { unread[p]++; drawBadge(p); return; }
    const stick = follow && !hover;
    const n = node(m); if (animate) n.classList.add("new");
    log.appendChild(n);
    while (log.children.length > 80) log.firstChild.remove();
    if (stick) log.scrollTop = log.scrollHeight; else pausedBtn.hidden = false;
  }
  function drawTabs() {
    tabsEl.innerHTML = "";
    CHANNELS.forEach(c => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "tab"; b.dataset.p = c.p; b.setAttribute("role", "tab"); b.setAttribute("aria-selected", String(c.p === active));
      b.style.setProperty("--tc", c.color); b.style.setProperty("--ton", c.on);
      b.innerHTML = `<i></i>${c.name}${unread[c.p] && c.p !== active ? `<span class="n">${Math.min(unread[c.p], 99)}</span>` : ""}`;
      b.addEventListener("click", () => openChannel(c.p));
      tabsEl.appendChild(b);
    });
  }
  function drawBadge(p) {
    const b = tabsEl.querySelector(`[data-p="${p}"]`);
    if (!b) return;
    let n = b.querySelector(".n");
    if (!n) { n = document.createElement("span"); n.className = "n"; b.appendChild(n); }
    n.textContent = Math.min(unread[p], 99);
  }
  function openChannel(p) {
    active = p; unread[p] = 0;
    const c = CHANNELS.find(x => x.p === p);
    chatbox.dataset.p = p;
    document.getElementById("cname").textContent = c.name;
    document.getElementById("cstate").textContent = t().ch[p][0];
    say.disabled = send.disabled = !c.write; say.value = ""; say.placeholder = t().ch[p][1];
    log.innerHTML = ""; store[p].forEach(m => log.appendChild(node(m)));
    log.scrollTop = log.scrollHeight; pausedBtn.hidden = true; follow = true;
    drawTabs();
  }
  /* historique de départ, refait dans la langue choisie (tes propres messages sont gardés) */
  function seed() {
    const mine = store.twitch.filter(m => m.own);
    store = { twitch: [], kick: [], steamtv: [] };
    CHANNELS.forEach(c => { for (let i = 0; i < 16; i++) store[c.p].push(makeMsg(c.p)); });
    store.twitch.splice(9, 0, { name: "spammer", color: "#888", badges: [], text: t().spam, t: "20:44", deleted: true });
    store.twitch.push(...mine);
  }

  const RATE = { twitch: 1300, kick: 1700, steamtv: 3600 };
  Object.keys(RATE).forEach(p => {
    const tick = () => { if (visible(chatbox)) push(p, makeMsg(p), !reduce); setTimeout(tick, RATE[p] * (reduce ? 2.5 : (.5 + Math.random()))); };
    setTimeout(tick, 900 + Math.random() * 900);
  });
  log.addEventListener("mouseenter", () => { hover = true; });
  log.addEventListener("mouseleave", () => { hover = false; if (follow) { log.scrollTop = log.scrollHeight; pausedBtn.hidden = true; } });
  log.addEventListener("scroll", () => { follow = atBottom(); if (follow) pausedBtn.hidden = true; });
  pausedBtn.addEventListener("click", () => { follow = true; log.scrollTop = log.scrollHeight; pausedBtn.hidden = true; });

  const sent = []; let recall = -1;
  function sendMsg() {
    const text = say.value.trim();
    if (!text || say.disabled) return;
    push("twitch", { name: "chris", color: "#5DADE2", badges: ["sub"], text, t: clock(), own: true }, !reduce);
    sent.unshift(text); recall = -1; say.value = "";
    follow = true; log.scrollTop = log.scrollHeight; pausedBtn.hidden = true;
  }
  send.addEventListener("click", sendMsg);
  say.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); sendMsg(); }
    else if (e.key === "ArrowUp" && sent.length) { e.preventDefault(); recall = Math.min(recall + 1, sent.length - 1); say.value = sent[recall]; }
    else if (e.key === "ArrowDown" && recall >= 0) { e.preventDefault(); recall--; say.value = recall >= 0 ? sent[recall] : ""; }
    else if (e.key === "Tab") {
      const m = say.value.match(/(@?)(\w+)$/);
      if (!m) return;
      const hit = [...new Set(store.twitch.map(x => x.name).filter(Boolean))].find(n => n.toLowerCase().startsWith(m[2].toLowerCase()));
      if (!hit) return;
      e.preventDefault();
      say.value = say.value.slice(0, m.index) + m[1] + hit + " ";
    }
  });

  /* ---------- copier ---------- */
  document.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", () => {
    const done = () => { b.textContent = t().copied; setTimeout(() => { b.textContent = t().copy; }, 1600); };
    const fallback = () => { const r = document.createRange(); r.selectNodeContents(b.previousElementSibling); const s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = "Ctrl+C"; };
    try { navigator.clipboard.writeText(b.dataset.copy).then(done, fallback); } catch { fallback(); }
  }));

  /* ---------- thème clair / sombre ---------- */
  const THEME_KEY = "slSiteTheme";
  const themeBtn = document.getElementById("theme"), themeLabel = document.getElementById("themeLabel");
  const THEME_TXT = { fr: { light: "Mode clair", dark: "Mode sombre" }, en: { light: "Light mode", dark: "Dark mode" },
    es: { light: "Modo claro", dark: "Modo oscuro" }, de: { light: "Heller Modus", dark: "Dunkler Modus" },
    it: { light: "Modalità chiara", dark: "Modalità scura" } };
  const darkMQ = matchMedia("(prefers-color-scheme: dark)");
  function isDark() { return root.dataset.theme ? root.dataset.theme === "dark" : darkMQ.matches; }
  function drawTheme() {
    const target = isDark() ? "light" : "dark", txt = THEME_TXT[lang][target];
    themeLabel.textContent = txt; themeBtn.setAttribute("aria-label", txt); themeBtn.title = txt;
    themeBtn.querySelector("use").setAttribute("href", target === "dark" ? "#i-moon" : "#i-sun");
  }
  try { const s = localStorage.getItem(THEME_KEY); if (s === "light" || s === "dark") root.dataset.theme = s; } catch {}
  themeBtn.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch {}
    drawTheme();
  });
  darkMQ.addEventListener("change", drawTheme);

  /* ---------- onglet Docs : deux vues dans la même page, choisies par l'ancre ---------- */
  const homeView = document.getElementById("top"), docsView = document.getElementById("docs"), navDocs = document.getElementById("nav-docs");
  const TITLES = { home: "Streamlink Launcher & Chat", docs: { fr: "Docs · Streamlink Launcher & Chat", en: "Docs · Streamlink Launcher & Chat", es: "Documentación · Streamlink Launcher & Chat", de: "Dokumentation · Streamlink Launcher & Chat", it: "Documentazione · Streamlink Launcher & Chat" } };
  let view = null;
  const hashId = () => { try { return decodeURIComponent(location.hash.slice(1)); } catch { return ""; } };
  function viewFor(id) {
    if (id === "docs") return "docs";
    const el = id && document.getElementById(id);
    return el && docsView.contains(el) ? "docs" : "home";
  }
  function setTitle() { document.title = view === "docs" ? TITLES.docs[lang] : TITLES.home; }
  function route() {
    const id = hashId(), v = viewFor(id), changed = v !== view;
    view = v;
    homeView.hidden = v !== "home"; docsView.hidden = v !== "docs";
    if (v === "docs") navDocs.setAttribute("aria-current", "page"); else navDocs.removeAttribute("aria-current");
    setTitle();
    if (!changed) return;
    const el = id && id !== "docs" && id !== "top" ? document.getElementById(id) : null;
    if (el) el.scrollIntoView({ behavior: "instant" }); else scrollTo({ top: 0, behavior: "instant" });
    if (v === "docs") SLDocs.refresh();
  }
  addEventListener("hashchange", route);

  /* ---------- langue ---------- */
  const sel = document.getElementById("lang");
  function apply(l, live) {
    lang = l;
    if (live) root.classList.add("static");   // pas de nouvelle animation du titre quand on change de langue
    root.lang = l; sel.value = l;
    const d = DICT[l];
    document.querySelectorAll("[data-i18n]").forEach(el => { const v = d[el.dataset.i18n]; if (v != null && el.innerHTML !== v) el.innerHTML = v; });
    document.querySelectorAll("[data-i18n-aria]").forEach(el => { const v = d[el.dataset.i18nAria]; if (v != null) el.setAttribute("aria-label", v); });
    document.querySelectorAll("[data-i18n-alt]").forEach(el => { const v = d[el.dataset.i18nAlt]; if (v != null) el.setAttribute("alt", v); });
    document.querySelectorAll("[data-copy]").forEach(b => { b.textContent = t().copy; });
    drawPills(); setPlatform(current, false); update(); drawStatus(); drawShots();
    seed(); openChannel(active); drawTheme();
    SLDocs.setLang(l, live); setTitle();
  }
  sel.addEventListener("change", () => {
    try { localStorage.setItem(KEY, sel.value); } catch {}
    apply(sel.value, true);
  });
  function startLang() {
    const p = new URLSearchParams(location.search).get("lang");
    if (p in DICT) return p;
    const byAnchor = SLDocs.langFor(hashId()); if (byAnchor) return byAnchor;
    try { const s = localStorage.getItem(KEY); if (s in DICT) return s; } catch {}
    const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "fr";
    const code = nav.slice(0, 2).toLowerCase();
    return code in DICT ? code : "en";
  }
  apply(startLang(), false);
  route();

  /* ---------- chargement : zapping des plateformes, puis retour sur Twitch ---------- */
  const boot = document.getElementById("boot");
  if (reduce || view === "docs") { boot.remove(); root.classList.add("nointro", "static"); }
  else {
    term.classList.add("typing");
    setTimeout(() => boot.remove(), 1400);
    setTimeout(() => term.classList.remove("typing"), 3600);
    const surf = ["kick", "youtube", "dailymotion", "steamtv", "url", "kick", "twitch"];
    setTimeout(() => {
      root.classList.add("surfing");
      surf.forEach((id, i) => setTimeout(() => {
        root.dataset.platform = id;
        if (i === surf.length - 1) setTimeout(() => { root.classList.remove("surfing"); setPlatform(current, false); }, 160);
      }, i * 115));
    }, 1500);
  }
})();
