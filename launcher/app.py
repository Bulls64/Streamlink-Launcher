"""Fenêtre principale : construction de l'écran de lancement, saisie et suggestions, récents, démarrage et fermeture.
Le reste vient des mixins : app_favorites, app_launch (lancement, journal), app_panels (panneaux latéraux),
app_updates (mises à jour) et app_desktop (zone de notification, presse-papiers, glisser-déposer).

Main window: building the launch screen, input and suggestions, recents, start-up and closing.
The rest comes from the mixins: app_favorites, app_launch (launching, log), app_panels (side panels),
app_updates (updates) and app_desktop (notification area, clipboard, drag and drop)."""
import os
import queue
import sys
import threading
import tkinter as tk
from collections import deque
from tkinter import messagebox, simpledialog

from . import core, inputs, updater, wintray
from .app_common import APP_COLOR, GEOMETRY_RE, ICON_FILE, LOG_LIMIT, RECENTS
from .app_desktop import DesktopMixin
from .app_favorites import FavoritesMixin
from .app_launch import LaunchMixin
from .app_panels import PanelsMixin
from .app_updates import UpdatesMixin
from .gfx import Painter
from .mini import MiniBar
from .theme import Fonts, apply_window_chrome, palette, resolve_theme
from .widgets import (
    Button,
    DrawerBar,
    Field,
    IconButton,
    Pill,
    Popover,
    RecentRow,
    Select,
    Toast,
    _is_inside,
)


class App(FavoritesMixin, DesktopMixin, LaunchMixin, PanelsMixin, UpdatesMixin, tk.Tk):
    def __init__(self):
        super().__init__(className="StreamlinkLauncher")  # WM_CLASS sous Linux (fichier .desktop de l'AppImage)
                                                          # WM_CLASS on Linux (the AppImage's .desktop file)
        self.withdraw()
        self.scale = max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        self.cfg = core.load_config()
        if not self.cfg.get("language"):
            self.cfg["language"] = core.detect_system_language()
        self.t = core.I18n(self.cfg["language"])
        self.platforms, self.platforms_error = core.load_platforms()
        self.store = core.Store()
        self.streams = core.StreamManager()
        self.painter = Painter(self)
        self.fonts = Fonts(self, self.px)
        self.popover = Popover(self)
        self.mini = MiniBar(self)
        self.tray = None
        self._tray_events = deque()  # événements Windows → interface (thread-safe, sans Tk)
                                     # Windows events → interface (thread-safe, without Tk)
        self._balloon_fav = None
        self._drop_events = deque()  # glisser-déposer OLE → interface (même règle : jamais de Tk dans les rappels)
                                     # OLE drag and drop → interface (same rule: never any Tk in the callbacks)
        self.drop_target = None
        self._drop_overlay = None
        self._win_events_running = False
        self._clip_seen = None       # (n° de séquence, texte) du presse-papiers déjà examiné
                                     # (sequence number, text) of the clipboard already examined
        self.sl_update = None        # dernier résultat de vérification de mise à jour
                                     # latest update check result
        self._update_busy = False
        self.app_update = None       # idem pour le lanceur lui-même (updater.check_app_update)
                                     # same for the launcher itself (updater.check_app_update)
        self._app_state = "idle"     # idle, checking, downloading, verifying, error, restart
        self._app_error = None       # clé de traduction du message d'erreur affiché
                                     # translation key of the error message shown
        self._app_dl = (0, 0)        # octets reçus, taille totale
                                     # bytes received, total size
        self._app_cancel = threading.Event()
        self._updated_from = updater.arg_value("--updated-from")  # version précédente, après une mise à jour
                                                               # previous version, after an update
        self.query = tk.StringVar()
        self.query.trace_add("write", self._on_query)
        self.log_lines = deque(maxlen=LOG_LIMIT)
        self.drawer_open = False
        self.drawer_body = self.log_text = None
        self.panel = self.panel_kind = None
        self._polling = False
        self._suppress_suggest = False
        self._ui_queue = queue.Queue()
        self._ui_jobs = 0
        self.live = {}              # {(chaîne en minuscules, id plateforme): info}
                                    # {(lowercase channel, platform id): info}
        self._live_job = None
        self._live_busy = False
        self._live_first = True     # pas de notification Windows pour ce qui est déjà en direct au démarrage
                                    # no Windows notification for what is already live at start-up
        self.previews = {}          # {clé de live: {"data": octets JPEG, "img": PhotoImage, "size": (l, h)}}
                                    # {live key: {"data": JPEG bytes, "img": PhotoImage, "size": (w, h)}}
        self._preview_render = {}   # {clé: (l, h)} mises à l'échelle en attente (regroupées pendant un redimensionnement)
                                    # {key: (w, h)} pending rescales (grouped during a resize)
        pid = self.cfg.get("last_platform")
        self.target = ("platform", pid if self.platform_by_id(pid) else self.platforms[0]["id"])

        self.title("Streamlink Launcher")
        self._icons = [self.painter.app_icon(s, APP_COLOR) for s in (16, 32)]
        self.iconphoto(True, *self._icons)
        if os.name == "nt" and os.path.isfile(ICON_FILE):
            try:
                self.iconbitmap(default=ICON_FILE)  # icône nette dans la barre des tâches
                                                    # sharp icon in the taskbar
            except tk.TclError:
                pass
        self.minsize(self.px(820), self.px(600))
        self._restore_geometry()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<ButtonPress-1>", self._global_click, add="+")
        self.bind("<Escape>", self._escape)
        self.bind("<Control-comma>", lambda e: self.open_settings())
        self.bind("<FocusIn>", self._on_focus_in)

        self.build()
        self.update_idletasks()
        self.apply_chrome()
        self.setup_tray()
        self.setup_drop()
        if self.cfg.get("autostart"):
            # Réécrit l'entrée de démarrage : elle pointe toujours vers la version lancée (.py ou .exe)
            # Rewrites the start-up entry: it always points to the version that was started (.py or .exe)
            wintray.set_autostart(True, os.path.join(str(core.BASE_DIR), "slink_launcher.py"), sys.executable)
        if not ("--tray" in sys.argv and self.tray_active):  # --tray : démarrage réduit (avec Windows)
                                                             # --tray: minimized start (with Windows)
            self.deiconify()
        self.after(300, self._startup_checks)
        if core.FROZEN:  # restes d'une mise à jour précédente (ancien exécutable, téléchargement interrompu)
                         # leftovers of a previous update (old executable, interrupted download)
            threading.Thread(target=updater.cleanup_update_leftovers, daemon=True).start()
        if self._updated_from:
            from . import __version__
            self.log(self.t("log_app_updated", old=self._updated_from, new=__version__))
            self.after(900, lambda: self.toast(self.t("toast_updated", old=self._updated_from, new=__version__),
                                               "ok", duration=6000))
        if self.cfg.get("update_check"):
            self.after(4000, lambda: self.check_streamlink_update(manual=False))
            self.after(7000, lambda: self.check_app_update(manual=False))
        self.schedule_live(2500)

    # =====================================================
    # Outils
    # Tools
    # =====================================================
    def px(self, v):
        return int(round(v * self.scale))

    def platform_by_id(self, pid):
        return next((p for p in self.platforms if p["id"] == pid), None)

    def platform_name(self, p):
        key = p.get("name_key")
        return self.t(key) if key and self.t.get(key) else p["name"]

    @property
    def accent(self):
        if self.target[0] == "platform":
            p = self.platform_by_id(self.target[1])
            if p:
                return p["color"], p["text_color"]
        return core.NEUTRAL_STYLE["color"], core.NEUTRAL_STYLE["text_color"]

    def quality_for(self, p):
        return self.cfg["qualities"].get(p["id"]) or p["default_quality"]

    def entry_target(self, entry):
        """('platform', dict) ou ('script', nom) pour une entrée d'historique/favori.

        ('platform', dict) or ('script', name) for a history/favorite entry."""
        if entry.get("platform"):
            p = self.platform_by_id(entry["platform"])
            return ("platform", p) if p else None
        script = entry.get("script")
        if script:
            p = self.platform_by_id(core.platform_from_script(script))
            return ("platform", p) if p else ("script", script)
        return None

    def target_label(self, target):
        if not target:
            return self.t("platform_undefined"), self.c.faint
        if target[0] == "platform":
            return self.platform_name(target[1]), target[1]["color"]
        return target[1], core.NEUTRAL_STYLE["color"]

    def run_in_thread(self, work, done):
        """Exécute 'work' hors de l'interface, puis 'done(résultat)' dans l'interface.

        Runs 'work' outside the interface, then 'done(result)' in the interface."""
        def runner():
            try:
                result = work()
            except Exception as e:
                result = e
            self._ui_queue.put((done, result))
        self._ui_jobs += 1
        threading.Thread(target=runner, daemon=True).start()
        if self._ui_jobs == 1:
            self.after(100, self._poll_ui)

    def _poll_ui(self):
        try:
            while True:
                done, result = self._ui_queue.get_nowait()
                self._ui_jobs -= 1
                try:
                    done(result)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        if self._ui_jobs > 0:
            self.after(100, self._poll_ui)

    def _restore_geometry(self):
        m = GEOMETRY_RE.match(self.cfg.get("geometry") or "")
        if m:
            x, y = int(m.group(3)), int(m.group(4))
            if 0 <= x < self.winfo_screenwidth() - 100 and 0 <= y < self.winfo_screenheight() - 100:
                self.geometry(self.cfg["geometry"])
                return
        self.geometry(f"{self.px(900)}x{self.px(660)}")

    def apply_chrome(self):
        apply_window_chrome(self, self.c.dark, border=self.accent[0], caption=self.c.title, text=self.c.text)

    # =====================================================
    # Construction
    # =====================================================
    def build(self, reopen=None):
        self.popover.close()
        self.mini.hide()
        for w in self.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()
        self.panel = self.panel_kind = None
        self.drawer_body = self.log_text = None
        self.mode = resolve_theme(self.cfg["theme"])
        self.c = c = palette(self.mode)
        t, px, f = self.t, self.px, self.fonts
        self.configure(bg=c.bg)

        # Tiroir du journal (en bas)
        # Log drawer (at the bottom)
        self.drawer = tk.Frame(self, bg=c.title)
        self.drawer.pack(side="bottom", fill="x")
        tk.Frame(self.drawer, bg=c.border, height=1).pack(fill="x")
        self.drawer_bar = DrawerBar(self.drawer, self, self.toggle_drawer)
        self.drawer_bar.pack(fill="x")

        content = self.content = tk.Frame(self, bg=c.bg)
        content.pack(fill="both", expand=True, padx=px(32), pady=(px(22), 0))

        head = tk.Frame(content, bg=c.bg)
        head.pack(fill="x", pady=(0, px(14)))
        tk.Label(head, text=t("title_main"), font=f.title, bg=c.bg, fg=c.text).pack(side="left")
        self.settings_btn = IconButton(head, self, "settings", command=self.open_settings)
        self.settings_btn.pack(side="right")
        IconButton(head, self, "history", command=self.open_history).pack(side="right", padx=(0, px(4)))

        row = tk.Frame(content, bg=c.bg)
        row.pack(fill="x")
        self.launch_btn = Button(row, self, text=t("btn_launch"), icon="play_fill", command=self.launch,
                                 kind="primary", height=52, font=f.button, accent=self.accent, pad=22, icon_size=15)
        self.launch_btn.pack(side="right")
        self.quality_select = Select(row, self, [], "", self.on_quality, height=52, popup_width=180,
                                     bg_key="surface")
        self.quality_select.pack(side="right", padx=(px(10), px(10)))
        self.field = Field(row, self, self.query, icon="search", kbd=t("kbd_enter"), ring=True, height=58,
                           font=f.field, radius=10, accent=self.accent, bg_key="surface")
        self.field.pack(side="left", fill="x", expand=True)
        e = self.field.entry
        e.bind("<Return>", self._on_enter)
        e.bind("<KP_Enter>", self._on_enter)
        e.bind("<Down>", lambda ev: self._nav(1))
        e.bind("<Up>", lambda ev: self._nav(-1))
        e.bind("<FocusOut>", lambda ev: self.after(120, self._maybe_close_suggestions), add="+")

        self.pills_row = tk.Frame(content, bg=c.bg, height=px(34))
        self.pills_row.pack(fill="x", pady=(px(12), 0))
        self.pills_row.bind("<Configure>", lambda ev: self._flow_pills())
        self.build_pills()

        self.fav_link = self._section_header(content, t("section_favorites"), self._fav_link_text(),
                                             self.open_favorites, top=26)
        self.fav_grid = tk.Frame(content, bg=c.bg)
        self.fav_grid.pack(fill="x", pady=(px(8), 0))
        self.build_favorites()

        self._section_header(content, t("section_recents"), t("link_full_history"), self.open_history, top=24)
        self.recent_box = tk.Frame(content, bg=c.bg)
        self.recent_box.pack(fill="x", pady=(px(2), 0))
        self.build_recents()

        self._fav_filter = self.target
        self.refresh_target()
        self.refresh_drawer()
        if self.drawer_open:
            self._build_drawer_body()
        if self.winfo_ismapped():
            self.apply_chrome()
        self._refresh_update_badge()
        if reopen == "settings":
            self.open_settings()

    def _section_header(self, parent, title, link, command, top):
        c, px = self.c, self.px
        bar = tk.Frame(parent, bg=c.bg)
        bar.pack(fill="x", pady=(px(top), 0))
        label = tk.Label(bar, text=title.upper(), font=self.fonts.caps, bg=c.bg, fg=c.muted)
        label.pack(side="left")
        btn = Button(bar, self, text=link, kind="link", command=command, height=24, font=self.fonts.tiny, pad=6)
        btn.pack(side="right")
        btn.title_label = label
        return btn

    # --- pastilles
    # --- chips
    def build_pills(self):
        for w in self.pills_row.winfo_children():
            w.destroy()
        self.pills, self.pill_order = {}, []
        for p in self.platforms:
            pill = Pill(self.pills_row, self, self.platform_name(p), dot=p["color"],
                        command=lambda pid=p["id"]: self.select_platform(pid),
                        selected=self.target == ("platform", p["id"]), accent=(p["color"], p["text_color"]))
            self.pills[p["id"]] = pill
            self.pill_order.append(pill)
        self.script_pill = None
        if self.cfg["show_scripts"]:
            sep = tk.Frame(self.pills_row, bg=self.c.border, width=1, height=self.px(20))
            sep.is_separator = True
            self.pill_order.append(sep)
            is_script = self.target[0] == "script"
            self.script_pill = Pill(self.pills_row, self, self.target[1] if is_script else self.t("pill_scripts"),
                                    command=self.open_scripts_menu, selected=is_script, icon="more", dashed=True,
                                    accent=(core.NEUTRAL_STYLE["color"], core.NEUTRAL_STYLE["text_color"]))
            self.pill_order.append(self.script_pill)
        self._flow_pills()

    def _flow_pills(self):
        width = self.pills_row.winfo_width()
        if width <= 1:
            return
        gap, row_h = self.px(8), self.px(34)
        x = y = 0
        for w in self.pill_order:
            sep = getattr(w, "is_separator", False)
            ww = self.px(1) if sep else w.winfo_reqwidth()
            if x and x + ww > width:
                x, y = 0, y + row_h + gap
            if sep:
                w.place(x=x + self.px(4), y=y + (row_h - self.px(20)) // 2, width=1, height=self.px(20))
                x += self.px(9) + gap
            else:
                w.place(x=x, y=y)
                x += ww + gap
        self.pills_row.configure(height=y + row_h)

    def select_platform(self, pid):
        if not self.platform_by_id(pid):
            return
        self.target = ("platform", pid)
        self.cfg["last_platform"] = pid
        self.refresh_target()

    def placeholder_for(self, p):
        """Texte d'aide du champ selon le type de saisie de la plateforme (fenêtre et mode mini).

        Hint text of the field according to the platform's input type (window and mini mode)."""
        kind = p["input"] if p["input"] in ("channel", "youtube", "video", "none", "url") else "channel"
        return self.t("ph_" + kind, name=self.platform_name(p))

    def refresh_target(self):
        t = self.t
        accent = self.accent
        for pid, pill in self.pills.items():
            pill.set_state(selected=self.target == ("platform", pid))
        if self.script_pill:
            is_script = self.target[0] == "script"
            self.script_pill.set_state(selected=is_script,
                                       text=self.target[1] if is_script else t("pill_scripts"))
            self._flow_pills()
        self.launch_btn.set_accent(accent)
        self.field.set_accent(accent)
        if self.target[0] == "platform":
            p = self.platform_by_id(self.target[1])
            self.field.set_placeholder(self.placeholder_for(p))
            self.field.set_disabled(p["input"] == "none")
            value = self.quality_for(p)
            options = [(q, q) for q in p["qualities"]]
            if value not in p["qualities"]:
                options.insert(0, (value, value))
            options.append(("__custom__", t("quality_custom")))
            self.quality_select.set_options(options, value)
            self.quality_select.set_disabled(False)
        else:
            self.field.set_placeholder(t("ph_script"))
            self.field.set_disabled(False)
            self.quality_select.set_options([], "—")
            self.quality_select.set_disabled(True)
        if getattr(self, "_fav_filter", None) != self.target and hasattr(self, "fav_grid"):
            # Les favoris affichés suivent la plateforme choisie
            # The favorites shown follow the selected platform
            self._fav_filter = self.target
            self.build_favorites()
            self.refresh_previews(only_missing=True)
        if self.winfo_ismapped():
            self.apply_chrome()

    def open_scripts_menu(self):
        if self.popover.is_open_for(self.script_pill):
            self.popover.close()
            return
        scripts = core.list_scripts(self.cfg["scripts_folder"])
        if not scripts:
            self.toast(self.t("toast_no_scripts"), "warn")
            return
        items = [{"label": s, "value": s, "selected": self.target == ("script", s)} for s in scripts]
        self.popover.show(self.script_pill, items, self._pick_script, width=self.px(240))

    def _pick_script(self, item):
        self.target = ("script", item["value"])
        self.refresh_target()

    def on_quality(self, value):
        if self.target[0] != "platform":
            return
        p = self.platform_by_id(self.target[1])
        if value == "__custom__":
            value = simpledialog.askstring(self.t("quality_custom_title"), self.t("quality_custom_prompt"),
                                           parent=self, initialvalue=self.quality_for(p))
            if value is None:
                self.refresh_target()
                return
            value = value.strip()
            if not inputs.QUALITY_RE.match(value):
                self.toast(self.t("err_quality"), "warn")
                self.refresh_target()
                return
        self.cfg["qualities"][p["id"]] = value
        core.save_config(self.cfg)
        self.refresh_target()

    # --- récents
    # --- recent
    def build_recents(self):
        c, t = self.c, self.t
        for w in self.recent_box.winfo_children():
            w.destroy()
        items = self.store.recents(RECENTS)
        if not items:
            tk.Label(self.recent_box, text=t("hint_no_recents"), font=self.fonts.small, bg=c.bg, fg=c.faint).pack(
                anchor="w", pady=self.px(12))
            return
        for i, e in enumerate(items):
            target = self.entry_target(e)
            name, color = self.target_label(target)
            title = e.get("channel") or name
            RecentRow(self.recent_box, self, title, name, color, self.t.format_date(e.get("date", "")),
                      on_fill=lambda e=e: self.fill_from_entry(e), on_launch=lambda e=e: self.launch_entry(e),
                      last=i == len(items) - 1).pack(fill="x")

    def fill_from_entry(self, entry):
        target = self.entry_target(entry)
        if target and target[0] == "platform":
            self.select_platform(target[1]["id"])
            text = "" if target[1]["input"] == "none" else entry.get("channel", "")
        elif target:
            self.target = ("script", target[1])
            self.build_pills()
            self.refresh_target()
            text = entry.get("channel", "")
        else:
            text = entry.get("channel", "")
        self.set_query(text)
        self.field.focus()

    def set_query(self, text):
        """Remplit la zone de saisie sans ouvrir les suggestions.

        Fills the input field without opening the suggestions."""
        self._suppress_suggest = True
        self.query.set(text)
        self._suppress_suggest = False

    # =====================================================
    # Saisie et suggestions
    # Input and suggestions
    # =====================================================
    def _on_query(self, *args):
        if self._suppress_suggest:
            return
        text = self.query.get()
        if self.target[0] == "platform" and text:
            detected = inputs.detect_platform_in_text(self.platforms, text)
            if detected and detected != self.target[1]:
                self.select_platform(detected)
        self.update_suggestions()

    def update_suggestions(self):
        if not hasattr(self, "field") or not self.field.has_focus():
            return
        text = self.query.get().strip()
        items = [self.suggestion_item(source, e, text) for source, e in self.store.suggestions(text)]
        if items:
            self.popover.show(self.field, items, self._pick_suggestion, width=self.field.winfo_width())
        elif self.popover.is_open_for(self.field):
            self.popover.close()

    def suggestion_item(self, source, entry, text, show_live=False):
        """Ligne de suggestion (favori ou historique) pour le menu du champ et le mode mini.

        Suggestion row (favorite or history) for the field's menu and the mini mode."""
        name, color = self.target_label(self.entry_target(entry))
        channel = entry.get("channel", "") or name
        fav = source == "favorite"
        right_color = None
        info = self.live_info(entry) if show_live else None
        if info and info.get("live"):
            viewers = info.get("viewers")
            state = self.t.viewers(viewers) if isinstance(viewers, int) else self.t("live_on")
            right, right_color = f"{name} · {state}", self.c.ok
        elif fav:
            right = name
        else:
            right = f"{name} · {self.t.format_date(entry.get('date', ''))}"
        return {"label": channel, "value": entry, "right": right, "right_dot": color, "right_color": right_color,
                "icon": "star_fill" if fav else "history", "icon_color": "#F5C451" if fav else None,
                "bold": len(text) if text and channel.lower().startswith(text.lower()) else 0, "query": text}

    def _pick_suggestion(self, item):
        self.fill_from_entry(item["value"])

    def _maybe_close_suggestions(self):
        if self.popover.is_open_for(self.field) and not self.field.has_focus():
            self.popover.close()

    def _nav(self, d):
        if self.popover.is_open_for(self.field):
            self.popover.move(d)
            return "break"
        if d > 0 and self.query.get().strip():
            self.update_suggestions()
            return "break"
        return None

    def _on_enter(self, event=None):
        if self.popover.is_open_for(self.field) and self.popover.hi is not None:
            self.popover.pick()
            return "break"
        self.popover.close()
        self.launch()
        return "break"

    def _global_click(self, e):
        if not self.popover.is_open:
            return
        w = e.widget
        if isinstance(w, str) or self.popover.contains(w):
            return
        anchor = self.popover.anchor
        if anchor is not None and _is_inside(w, anchor):
            return
        self.popover.close()

    def _escape(self, e=None):
        if self.popover.is_open:
            self.popover.close()
        elif self.panel:
            self.close_panel()

    def _on_focus_in(self, e):
        if e.widget is not self:
            return
        if self.cfg["theme"] == "auto" and resolve_theme("auto") != self.mode:
            self.build(reopen="settings" if self.panel_kind == "settings" else None)
        self.after(150, self.offer_clipboard)

    # =====================================================
    # Notifications
    # Notifications
    # =====================================================
    def toast(self, text, kind="ok", action=None, duration=2800, low_priority=False):
        old = getattr(self, "toast_widget", None)
        if old is not None:
            try:
                visible = old.winfo_exists()
            except tk.TclError:
                visible = False
            if low_priority and visible and old.kind in ("error", "warn"):
                return  # une info secondaire ne cache pas une erreur encore affichée
                        # a secondary info does not hide an error still on screen
            old.dismiss()
        bottom = self.drawer.winfo_height() + self.px(16) if self.drawer.winfo_ismapped() else self.px(60)
        self.toast_widget = Toast(self, text, kind, action, duration, bottom=bottom)

    # =====================================================
    # Démarrage et fermeture
    # Start-up and closing
    # =====================================================
    def _report_data_issues(self):
        """Affiche les problèmes de fichiers signalés par core (fichier endommagé, enregistrement impossible).

        Shows the file problems reported by core (damaged file, saving impossible)."""
        t = self.t
        while core.DATA_ISSUES:
            key, values = core.DATA_ISSUES.pop(0)
            text = t(key, **values)
            self.log(text, "err")
            self.toast(text, "error", action=(t("action_show_log"), self.show_log), duration=7000)

    def _startup_checks(self):
        t = self.t
        core.set_issue_handler(lambda: self.after(0, self._report_data_issues))
        if not core.PORTABLE and not core.APPIMAGE:  # AppImage : données dans ~/.config, c'est normal
                                                     # AppImage: data in ~/.config, this is normal
            self.log(t("log_data_folder", path=core.DATA_ROOT), "warn")
        if self.platforms_error:
            self.log(t("log_platforms_error", error=self.platforms_error), "err")
            self.toast(t("toast_platforms_error"), "error", action=(t("action_show_log"), self.show_log))
        elif not core.find_streamlink(self.cfg["streamlink_path"]):
            self.log(t("log_no_streamlink", url=core.STREAMLINK_INSTALL_URL), "err")
            self.toast(t("toast_no_streamlink"), "error", action=(t("action_settings"), self.open_settings),
                       duration=6000)
        self._report_data_issues()  # en dernier : un fichier endommagé est l'alerte la plus importante
                                    # last: a damaged file is the most important alert

    def _save_window_state(self):
        try:
            if self.state() == "normal":
                self.cfg["geometry"] = self.geometry()
        except tk.TclError:
            pass
        if self.target[0] == "platform":
            self.cfg["last_platform"] = self.target[1]
        core.save_config(self.cfg)

    def on_quit(self):
        running = self.streams.running()
        if running and self.state() == "withdrawn":
            self.show_main()  # la confirmation doit être visible
                              # the confirmation must be visible
        if running and not messagebox.askyesno(self.t("title_confirm"),
                                               self.t("confirm_quit_running", count=len(running)), parent=self):
            return
        self._shutdown()

    def _shutdown(self):
        """Arrête les streams, libère les ressources Windows, enregistre l'état et ferme la fenêtre.

        Stops the streams, frees the Windows resources, saves the state and closes the window."""
        self._app_cancel.set()
        self.streams.stop_all()
        if self._live_job:
            self.after_cancel(self._live_job)
        self.mini.hide()
        if self.drop_target is not None:
            self.drop_target.revoke()
            self.drop_target = None
        if self.tray is not None:
            self.tray.stop()
        self._save_window_state()
        self.destroy()


def main():
    from . import __version__
    from .theme import enable_dpi_awareness, set_app_id
    core.setup_logging()
    core.log.info("Démarrage de Streamlink Launcher %s (données : %s)", __version__, core.DATA_ROOT)
    waited = updater.arg_value("--wait-pid")  # relance après une mise à jour : on attend la fermeture de l'ancienne
                                           # restart after an update: wait for the old one to close
    if waited and waited.isdigit():
        wintray.wait_for_pid(int(waited), 20)
    if not wintray.acquire_single_instance():
        return  # déjà ouvert : sa fenêtre vient d'être affichée
                # already open: its window has just been shown
    enable_dpi_awareness()
    set_app_id()
    App().mainloop()
