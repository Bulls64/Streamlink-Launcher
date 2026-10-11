"""Fenêtre principale : écran de lancement, tiroir du journal, panneaux latéraux."""
import os
import re
import sys
import queue
import threading
import subprocess
import tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox, simpledialog

from . import core
from . import winnotify
from . import wintray
from .mini import MiniBar
from .gfx import Painter
from .theme import palette, resolve_theme, Fonts, apply_window_chrome
from .widgets import (Button, IconButton, Pill, Card, RecentRow, Field, Select, Segmented, Switch, Popover,
                      ScrollArea, ListRow, StreamRow, DrawerBar, StatusCard, Toast, _is_inside)

LOG_LIMIT = 500
RECENTS = 3
FAV_SLOTS = 3
APP_COLOR = "#7C4DFF"
GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
if not os.path.isfile(ICON_FILE):
    ICON_FILE = str(core.RES_DIR / "launcher" / "app.ico")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
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
        self._balloon_fav = None
        self.sl_update = None        # dernier résultat de vérification de mise à jour
        self._update_busy = False
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
        self._live_job = None
        self._live_busy = False
        self._live_first = True     # pas de notification Windows pour ce qui est déjà en direct au démarrage
        pid = self.cfg.get("last_platform")
        self.target = ("platform", pid if self.platform_by_id(pid) else self.platforms[0]["id"])

        self.title("Streamlink Launcher")
        self._icons = [self.painter.app_icon(s, APP_COLOR) for s in (16, 32)]
        self.iconphoto(True, *self._icons)
        if os.name == "nt" and os.path.isfile(ICON_FILE):
            try:
                self.iconbitmap(default=ICON_FILE)  # icône nette dans la barre des tâches
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
        if self.cfg.get("autostart"):
            # Réécrit l'entrée de démarrage : elle pointe toujours vers la version lancée (.py ou .exe)
            wintray.set_autostart(True, os.path.join(str(core.BASE_DIR), "slink_launcher.py"), sys.executable)
        if not ("--tray" in sys.argv and self.tray_active):  # --tray : démarrage réduit (avec Windows)
            self.deiconify()
        self.after(300, self._startup_checks)
        if self.cfg.get("update_check"):
            self.after(4000, lambda: self.check_streamlink_update(manual=False))
        self.schedule_live(2500)

    # =====================================================
    # Outils
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
        """('platform', dict) ou ('script', nom) pour une entrée d'historique/favori."""
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
        """Exécute 'work' hors de l'interface, puis 'done(résultat)' dans l'interface."""
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
            w, h, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
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
        tk.Label(bar, text=title.upper(), font=self.fonts.caps, bg=c.bg, fg=c.muted).pack(side="left")
        btn = Button(bar, self, text=link, kind="link", command=command, height=24, font=self.fonts.tiny, pad=6)
        btn.pack(side="right")
        return btn

    # --- pastilles
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
            kind = p["input"]
            self.field.set_placeholder(t("ph_" + kind if kind in ("channel", "youtube", "video", "none", "url")
                                         else "ph_channel", name=self.platform_name(p)))
            self.field.set_disabled(kind == "none")
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
            if not core.QUALITY_RE.match(value):
                self.toast(self.t("err_quality"), "warn")
                self.refresh_target()
                return
        self.cfg["qualities"][p["id"]] = value
        core.save_config(self.cfg)
        self.refresh_target()

    # --- favoris
    def _fav_link_text(self):
        n = len(self.store.favorites)
        return self.t("link_manage_count", count=n) if n > FAV_SLOTS else self.t("link_manage")

    def build_favorites(self):
        c, px, t = self.c, self.px, self.t
        for w in self.fav_grid.winfo_children():
            w.destroy()
        for i in range(4):
            self.fav_grid.columnconfigure(i, weight=1, uniform="fav")
        # Les favoris en direct passent devant (l'ordre est conservé sinon)
        favs = sorted(self.store.favorites, key=lambda e: not (self.live_info(e) or {}).get("live"))[:FAV_SLOTS]

        def pad(col):
            return (0 if col == 0 else px(5), 0 if col == 3 else px(5))

        for col, fav in enumerate(favs):
            name, color = self.target_label(self.entry_target(fav))
            info = self.live_info(fav)
            status = None
            if info is not None:
                status = (t("live_on"), True) if info.get("live") else (t("live_off"), False)
            card = Card(self.fav_grid, self, title=fav.get("channel", "?"), subtitle=name, dot=color,
                        command=lambda e=fav: self.launch_favorite(e), status=status,
                        on_menu=lambda ev, e=fav: self.favorite_menu(ev, e))
            card.grid(row=0, column=col, sticky="ew", padx=pad(col))
        col = len(favs)
        Card(self.fav_grid, self, title=t("card_add_favorite"), add=True,
             command=self.add_current_to_favorites).grid(row=0, column=col, sticky="ew", padx=pad(col))
        if not favs:
            tk.Label(self.fav_grid, text=t("hint_no_favorites"), font=self.fonts.small, bg=c.bg, fg=c.faint,
                     anchor="w", justify="left").grid(row=0, column=1, columnspan=3, sticky="w", padx=px(14))
        if hasattr(self, "fav_link"):
            self.fav_link.set_text(self._fav_link_text())

    def launch_favorite(self, fav):
        if self.entry_target(fav):
            return self.launch_entry(fav)
        # Anciens favoris sans plateforme : Twitch
        p = self.platform_by_id("twitch") or self.platforms[0]
        return self.launch_platform(p, fav.get("channel", ""))

    def favorite_menu(self, event, fav):
        c, t = self.c, self.t
        menu = tk.Menu(self, tearoff=0, bg=c.popover, fg=c.text, activebackground=c.popover_hover,
                       activeforeground=c.text, bd=0, font=self.fonts.small)
        menu.add_command(label=t("menu_launch"), command=lambda: self.launch_favorite(fav))
        menu.add_command(label=t("menu_fill"), command=lambda: self.fill_from_entry(fav))
        menu.add_separator()
        menu.add_command(label=t("menu_remove_favorite"), command=lambda: self.remove_favorite(fav))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def add_current_to_favorites(self):
        t = self.t
        kind, value = self.target
        if kind == "platform":
            p = self.platform_by_id(value)
            if p["input"] == "none":
                self.toast(t("info_no_channel", name=self.platform_name(p)), "warn")
                return
            try:
                _, channel = core.resolve_target(p, self.query.get())
            except core.InputError as e:
                self.toast(t("toast_fav_need_channel") if e.key == "err_empty" else
                           t(e.key, name=self.platform_name(p)), "warn")
                self.field.focus()
                return
            entry = {"channel": channel, "platform": p["id"]}
        else:
            channel = self.query.get().strip()
            if not channel:
                self.toast(t("toast_fav_need_channel"), "warn")
                return
            entry = {"channel": channel, "script": value}
        added = self.store.add_favorite(entry)
        if not added:
            self.toast(t("info_already_favorite"), "warn")
            return
        self.build_favorites()
        self._refresh_panel("favorites")
        self.toast(t("toast_fav_added", name=channel), "ok",
                   action=(t("action_undo"), lambda: self.remove_favorite(added, notify=False)))
        self.schedule_live(1500)

    def remove_favorite(self, fav, notify=True):
        index = self.store.remove_favorite(fav)
        if index is None:
            return
        self.build_favorites()
        self._refresh_panel("favorites")
        if notify:
            def undo():
                self.store.restore_favorite(fav, index)
                self.build_favorites()
                self._refresh_panel("favorites")
            self.toast(self.t("toast_fav_removed", name=fav.get("channel", "")), "ok",
                       action=(self.t("action_undo"), undo))

    # --- en direct
    def live_key(self, entry):
        """Clé de vérification d'un favori, ou None si sa plateforme ne se vérifie pas."""
        target = self.entry_target(entry)
        if not target or target[0] != "platform" or not entry.get("channel"):
            return None
        if core.live_method(target[1]) == "none":
            return None
        return entry["channel"].lower(), target[1]["id"]

    def live_info(self, entry):
        key = self.live_key(entry)
        return self.live.get(key) if key else None

    def live_entries(self):
        keys = []
        for fav in self.store.favorites:
            key = self.live_key(fav)
            if key and key not in keys:
                keys.append(key)
        return keys

    def schedule_live(self, delay_ms=None):
        """Programme la prochaine vérification (aucune minuterie si rien à vérifier)."""
        if self._live_job:
            self.after_cancel(self._live_job)
            self._live_job = None
        if not self.cfg.get("live_check") or not self.live_entries():
            return
        if delay_ms is None:
            delay_ms = int(self.cfg["live_interval"]) * 60_000
        self._live_job = self.after(delay_ms, self._run_live)

    def _run_live(self):
        self._live_job = None
        entries = self.live_entries()
        if self._live_busy or not entries or not self.cfg.get("live_check"):
            return
        self._live_busy = True
        platforms, streamlink_path = list(self.platforms), self.cfg["streamlink_path"]
        self.run_in_thread(lambda: core.check_live(entries, platforms, streamlink_path), self._live_done)

    def _live_done(self, results):
        self._live_busy = False
        if isinstance(results, Exception):
            results = {}
        first = self._live_first
        self._live_first = False
        started = []
        for key, info in results.items():
            if info is None:
                continue  # état inconnu (réseau, plugin absent) : on garde le précédent
            before = self.live.get(key)
            if info.get("live") and before is not None and not before.get("live"):
                started.append(key)
            self.live[key] = info
        self.build_favorites()
        if self.panel_kind == "favorites":
            self.open_favorites()
        if first:
            count = sum(1 for k in self.live_entries() if (self.live.get(k) or {}).get("live"))
            if count:
                self.toast(self.t("toast_live_summary_one") if count == 1 else
                           self.t("toast_live_summary", count=count), "ok", low_priority=True)
        for key in started:
            self.notify_live(key)
        self.update_tray_tooltip()
        self.schedule_live()

    def notify_live(self, key):
        t = self.t
        fav = next((f for f in self.store.favorites if self.live_key(f) == key), None)
        if fav is None:
            return
        info = self.live.get(key) or {}
        name, _ = self.target_label(self.entry_target(fav))
        channel = fav.get("channel", "")
        self.toast(t("toast_live_started", name=channel, platform=name), "ok",
                   action=(t("btn_launch"), lambda: self.launch_favorite(fav)), duration=8000)
        self.log(t("log_live_started", name=channel, platform=name))
        if self.cfg.get("live_notify"):
            body = " · ".join(x for x in (info.get("game"), info.get("title")) if x) or name
            title = t("notif_live_title", name=channel)
            # Avec l'icône de notification : bulle cliquable (un clic lance le stream). Sinon, toast PowerShell.
            if self.tray_active and self.tray.notify(title, body + "\n" + t("notif_click_to_watch")):
                self._balloon_fav = fav
            else:
                winnotify.toast(title, body)
        try:
            if self.focus_displayof() is None:
                winnotify.flash_taskbar(self)
        except (KeyError, tk.TclError):
            pass

    # --- zone de notification, raccourci global, fermeture
    @property
    def tray_active(self):
        return self.tray is not None and self.tray.icon_shown

    def setup_tray(self):
        """Crée la fenêtre Windows cachée (icône + raccourci) puis applique les réglages."""
        if os.name != "nt":
            return
        if self.tray is None:
            # IMPORTANT : la fenêtre Windows de l'icône reçoit ses messages PENDANT que Tkinter traite les siens.
            # Appeler Tkinter à ce moment-là (même un simple after()) casse l'état interne de Python et fait
            # planter l'application (« PyEval_RestoreThread: … GIL is released »). On se contente donc de
            # déposer l'événement dans une file (sans Tk), relue ci-dessous depuis la boucle de Tkinter.
            tray = wintray.Tray(self._tray_events.append, icon_path=ICON_FILE)
            if not tray.start():
                self.log(self.t("log_tray_failed"), "err")
                return
            self.tray = tray
            self.after(100, self._poll_tray)
        self.apply_tray_settings(startup=True)

    def apply_tray_settings(self, startup=False):
        if self.tray is None:
            return
        if self.cfg.get("tray"):
            self.tray.show_icon()
        else:
            self.tray.hide_icon()
        if self.cfg.get("hotkey"):
            key = wintray.hotkey_label(self.cfg.get("hotkey_combo"))
            if self.tray.register_hotkey(self.cfg.get("hotkey_combo")):
                self.log(self.t("log_hotkey_ok", key=key), "dim")
            else:
                self.log(self.t("log_hotkey_failed", key=key, code=self.tray.hotkey_error), "warn")
                message = (self.t("toast_hotkey_taken", key=key), "warn",
                           (self.t("action_settings"), self.open_settings))
                if startup:  # après les vérifications de démarrage, pour ne pas être recouvert
                    self.after(1500, lambda: self.toast(message[0], message[1], action=message[2], duration=7000))
                else:
                    self.toast(message[0], message[1], action=message[2], duration=7000)
        else:
            self.tray.unregister_hotkey()
        self.update_tray_tooltip()

    def _hotkey_status(self):
        """(texte, couleur) de l'état du raccourci pour les Paramètres, ou None."""
        if os.name != "nt" or not self.cfg.get("hotkey"):
            return None
        key = wintray.hotkey_label(self.cfg.get("hotkey_combo"))
        if self.tray is None:
            return self.t("hotkey_unavailable"), self.c.warn
        if self.tray.hotkey:
            return self.t("hotkey_ok", key=key), self.c.ok
        return self.t("hotkey_failed", key=key), self.c.warn

    def update_tray_tooltip(self):
        if not self.tray_active:
            return
        count = sum(1 for k in self.live_entries() if (self.live.get(k) or {}).get("live"))
        text = "Streamlink Launcher"
        if count:
            text += " — " + (self.t("toast_live_summary_one") if count == 1 else
                              self.t("toast_live_summary", count=count))
        self.tray.set_tooltip(text)

    def _poll_tray(self):
        """Traite les clics sur l'icône et le raccourci global (file remplie par wintray)."""
        while self._tray_events:
            try:
                self._tray_event(self._tray_events.popleft())
            except Exception as e:  # une erreur ici ne doit jamais arrêter la surveillance
                self.log(self.t("log_error", error=e), "err")
        if self.tray is not None:
            self.after(100, self._poll_tray)

    def _tray_event(self, event):
        if event == "open":
            self.show_main()
        elif event == "menu":
            self.tray_menu()
        elif event == "balloon":
            fav, self._balloon_fav = self._balloon_fav, None
            if fav is not None:
                self.launch_favorite(fav)
            else:
                self.show_main()
        elif event == "hotkey":
            self.log(self.t("log_hotkey_received", key=wintray.hotkey_label(self.cfg.get("hotkey_combo"))), "dim")
            self.mini.toggle()

    def show_main(self):
        self.mini.hide()
        self.deiconify()
        if self.state() == "iconic":
            self.state("normal")
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass
        self.apply_chrome()

    def tray_menu(self):
        t = self.t
        items = [(1, t("tray_open"), True),
                 (2, t("tray_mini", key=wintray.hotkey_label(self.cfg.get("hotkey_combo"))), False), None]
        live = []
        for fav in self.store.favorites:
            if (self.live_info(fav) or {}).get("live"):
                live.append(fav)
        for i, fav in enumerate(live[:8]):
            name, _ = self.target_label(self.entry_target(fav))
            items.append((100 + i, t("tray_watch", name=fav.get("channel", ""), platform=name), False))
        if live:
            items.append(None)
        items.append((3, t("tray_quit"), False))
        chosen = self.tray.show_menu(items) if self.tray else 0
        if chosen == 1:
            self.show_main()
        elif chosen == 2:
            self.mini.show()
        elif chosen == 3:
            self.on_quit()
        elif chosen >= 100 and chosen - 100 < len(live):
            self.launch_favorite(live[chosen - 100])

    def on_close(self):
        """Bouton ✕ : réduit dans la zone de notification si elle est active, sinon quitte."""
        if not self.tray_active:
            self.on_quit()
            return
        self.popover.close()
        self._save_window_state()
        self.withdraw()
        if not self.cfg.get("tray_hint_shown"):
            self.tray.notify(self.t("tray_hint_title"), self.t("tray_hint_body"))
            self.cfg["tray_hint_shown"] = True
            core.save_config(self.cfg)

    # --- récents
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
        self._suppress_suggest = True
        self.query.set(text)
        self._suppress_suggest = False
        self.field.focus()

    # =====================================================
    # Saisie et suggestions
    # =====================================================
    def _on_query(self, *args):
        if self._suppress_suggest:
            return
        text = self.query.get()
        if self.target[0] == "platform" and text:
            detected = core.detect_platform_in_text(self.platforms, text)
            if detected and detected != self.target[1]:
                self.select_platform(detected)
        self.update_suggestions()

    def update_suggestions(self):
        if not hasattr(self, "field") or not self.field.has_focus():
            return
        text = self.query.get().strip()
        items = []
        for source, e in self.store.suggestions(text):
            name, color = self.target_label(self.entry_target(e))
            channel = e.get("channel", "")
            fav = source == "favorite"
            right = name if fav else f"{name} · {self.t.format_date(e.get('date', ''))}"
            items.append({"label": channel, "value": e, "icon": "star_fill" if fav else "history",
                          "icon_color": "#F5C451" if fav else None, "right": right, "right_dot": color,
                          "bold": len(text) if channel.lower().startswith(text.lower()) else 0, "query": text})
        if items:
            self.popover.show(self.field, items, self._pick_suggestion, width=self.field.winfo_width())
        elif self.popover.is_open_for(self.field):
            self.popover.close()

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
        if e.widget is not self or self.cfg["theme"] != "auto":
            return
        if resolve_theme("auto") != self.mode:
            self.build(reopen="settings" if self.panel_kind == "settings" else None)

    # =====================================================
    # Lancement
    # =====================================================
    def launch(self):
        kind, value = self.target
        if kind == "platform":
            return self.launch_platform(self.platform_by_id(value), self.query.get(), self.quality_select.value)
        return self.launch_script(value, self.query.get())

    def launch_entry(self, entry, report=None):
        """report : où afficher les erreurs (par défaut les notifications de la fenêtre)."""
        report = report or self.toast
        target = self.entry_target(entry)
        if not target:
            report(self.t("err_unknown_target", name=entry.get("platform") or entry.get("script") or "?"),
                       "error")
            return False
        if target[0] == "platform":
            return self.launch_platform(target[1], entry.get("channel", ""), report=report)
        return self.launch_script(target[1], entry.get("channel", ""), report=report)

    def launch_platform(self, p, raw, quality=None, report=None):
        t = self.t
        quiet = report is not None  # lancé depuis le mode mini : erreurs affichées dans la barre
        report = report or self.toast
        streamlink = core.find_streamlink(self.cfg["streamlink_path"])
        if not streamlink:
            report(t("toast_no_streamlink"), "error", action=(t("action_settings"), self.open_settings))
            self.log(t("log_no_streamlink", url=core.STREAMLINK_INSTALL_URL), "err")
            return False
        try:
            url, display = core.resolve_target(p, raw)
        except core.InputError as e:
            report(t(e.key, name=self.platform_name(p)), "warn")
            if not quiet:
                self.field.focus()
            return False
        quality = quality if quality and quality not in ("—", "__custom__") else self.quality_for(p)
        if not core.QUALITY_RE.match(quality):
            report(t("err_quality"), "warn")
            return False
        opts, missing = core.player_options(self.cfg)
        if missing:
            self.log(t("log_player_not_found", player=core.PLAYER_NAMES.get(missing, missing)), "warn")
        player = self.cfg["player"]
        player_label = None
        if player in core.PLAYER_NAMES and not missing:
            player_label = core.PLAYER_NAMES[player]
        elif player == "custom" and not missing:
            player_label = t("player_custom")
        pname = self.platform_name(p)
        name = display if p["input"] != "none" else pname
        detail = " · ".join(x for x in (pname if p["input"] != "none" else None, quality, player_label) if x)
        command = [streamlink, *p["args"], *opts, url, quality]
        try:
            self.streams.start(command, {"name": name, "detail": detail, "color": p["color"], "label": name})
        except Exception as e:
            report(t("toast_launch_failed"), "error", action=(t("action_show_log"), self.show_log))
            self.log(t("log_error", error=e), "err")
            return False
        self.log(t("log_launching", label=f"{pname} / {name}", quality=quality))
        self.store.add_history({"channel": display, "platform": p["id"]})
        self.toast(t("toast_launching", name=name, platform=pname), "ok")
        self.build_recents()
        self._refresh_panel("history")
        self.refresh_drawer()
        self.start_polling()
        return True

    def launch_script(self, script_name, raw, report=None):
        t = self.t
        report = report or self.toast
        full_path = os.path.join(self.cfg["scripts_folder"], script_name)
        if not os.path.exists(full_path):
            report(t("err_script_not_found", path=script_name), "error")
            return False
        arg = (raw or "").strip()
        if arg and not core.SCRIPT_ARG_RE.match(arg):
            report(t("err_script_arg"), "warn")
            return False
        try:
            command = core.build_script_command(full_path, arg)
            if command is None:
                os.startfile(full_path)
            else:
                flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                subprocess.Popen(command, cwd=os.path.dirname(full_path), creationflags=flags)
        except Exception as e:
            report(t("toast_launch_failed"), "error")
            self.log(t("log_error", error=e), "err")
            return False
        self.log(t("log_launching", label=script_name + (f" / {arg}" if arg else ""), quality="-"))
        self.store.add_history({"channel": arg, "script": script_name})
        self.toast(t("toast_launching", name=arg or script_name, platform=t("pill_scripts")), "ok")
        self.build_recents()
        return True

    def stop_stream(self, stream):
        stream["stopped"] = True
        self.streams.stop(stream)
        self.toast(self.t("toast_stopped", name=stream["name"]), "ok")

    # --- suivi des streams (uniquement quand il y en a)
    def start_polling(self):
        if not self._polling:
            self._polling = True
            self.after(120, self._poll)

    def _poll(self):
        t = self.t
        for kind, stream, value in self.streams.poll():
            if kind == "line":
                self.log(f"[{stream['label']}] {value}")
            else:
                failed = value not in (0, None) and not stream.get("stopped")
                if stream.get("stopped"):
                    self.log(t("log_stream_stopped", label=stream["label"]), "dim")
                else:
                    self.log(t("log_stream_ended", label=stream["label"], code=value), "err" if failed else "dim")
                if failed:
                    self.toast(t("toast_stream_failed", name=stream["name"]), "error",
                               action=(t("action_show_log"), self.show_log), duration=5000)
                self.refresh_drawer()
        if self.streams.busy():
            self.after(150, self._poll)
        else:
            self._polling = False

    # =====================================================
    # Tiroir du journal
    # =====================================================
    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        if self.drawer_open:
            self._build_drawer_body()
        elif self.drawer_body is not None:
            self.drawer_body.destroy()
            self.drawer_body = self.log_text = None
        self.refresh_drawer()

    def show_log(self):
        if not self.drawer_open:
            self.toggle_drawer()

    def _build_drawer_body(self):
        c, px, f = self.c, self.px, self.fonts
        body = self.drawer_body = tk.Frame(self.drawer, bg=c.title)
        body.pack(fill="x", padx=(px(32), px(20)), pady=(0, px(14)))
        self.stream_rows = tk.Frame(body, bg=c.title)
        self.stream_rows.pack(fill="x")
        border = tk.Frame(body, bg=c.border)
        border.pack(fill="x", pady=(px(4), 0))
        self.log_text = tk.Text(border, height=6, bg=c.log_bg, fg=c.muted, font=f.mono, relief="flat", bd=0,
                                highlightthickness=0, wrap="word", padx=px(12), pady=px(8), cursor="",
                                insertwidth=0, selectbackground=c.border_strong, spacing1=px(1), spacing3=px(1))
        self.log_text.pack(fill="x", padx=1, pady=1)
        self.log_text.tag_configure("err", foreground=c.error)
        self.log_text.tag_configure("warn", foreground=c.warn)
        self.log_text.tag_configure("dim", foreground=c.faint)
        if not self.log_lines:
            self.log_text.insert("end", self.t("log_empty") + "\n", "dim")
        for msg, tag in self.log_lines:
            self.log_text.insert("end", msg + "\n", tag or ())
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self._fill_stream_rows()

    def _fill_stream_rows(self):
        for w in self.stream_rows.winfo_children():
            w.destroy()
        for s in self.streams.streams:
            StreamRow(self.stream_rows, self, s["name"], s["detail"], s["color"], self.t("btn_stop"),
                      lambda s=s: self.stop_stream(s)).pack(fill="x", pady=(0, self.px(6)))

    def refresh_drawer(self):
        t = self.t
        n = len(self.streams.streams)
        text = t("drawer_none") if n == 0 else (t("drawer_running_one") if n == 1 else t("drawer_running", count=n))
        self.drawer_bar.set_state(text, t("drawer_log"), self.drawer_open, n > 0)
        if self.drawer_open and self.drawer_body is not None:
            self._fill_stream_rows()

    def log(self, msg, tag=None):
        if tag is None:
            low = msg.lower()
            if "error" in low or "erreur" in low:
                tag = "err"
            elif "warning" in low:
                tag = "warn"
        if not self.log_lines and self.log_text is not None:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        self.log_lines.append((msg, tag))
        if self.log_text is not None:
            lt = self.log_text
            lt.configure(state="normal")
            lt.insert("end", msg + "\n", tag or ())
            lines = int(lt.index("end-1c").split(".")[0])
            if lines > LOG_LIMIT:
                lt.delete("1.0", f"{lines - LOG_LIMIT}.0")
            lt.configure(state="disabled")
            lt.see("end")

    # =====================================================
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
            old.dismiss()
        bottom = self.drawer.winfo_height() + self.px(16) if self.drawer.winfo_ismapped() else self.px(60)
        self.toast_widget = Toast(self, text, kind, action, duration, bottom=bottom)

    # =====================================================
    # Panneaux latéraux
    # =====================================================
    def open_panel(self, kind, title, body_builder, footer_builder=None):
        self.close_panel()
        self.popover.close()
        c, px = self.c, self.px
        panel = tk.Frame(self, bg=c.panel)
        panel.place(relx=1.0, rely=0, anchor="ne", relheight=1.0, width=px(392))
        tk.Frame(panel, bg=c.border, width=1).pack(side="left", fill="y")
        inner = tk.Frame(panel, bg=c.panel)
        inner.pack(side="left", fill="both", expand=True)
        head = tk.Frame(inner, bg=c.panel)
        head.pack(fill="x", padx=(px(24), px(14)), pady=(px(16), px(8)))
        tk.Label(head, text=title, font=self.fonts.panel_title, bg=c.panel, fg=c.text).pack(side="left")
        IconButton(head, self, "close", command=self.close_panel, size=36, icon_size=13).pack(side="right")
        if footer_builder:
            foot = tk.Frame(inner, bg=c.panel)
            foot.pack(side="bottom", fill="x")
            tk.Frame(foot, bg=c.border, height=1).pack(fill="x")
            fbody = tk.Frame(foot, bg=c.panel)
            fbody.pack(fill="x", padx=px(24), pady=px(12))
            footer_builder(fbody)
        area = ScrollArea(inner, self, c.panel)
        area.pack(fill="both", expand=True, padx=(px(24), px(6)), pady=(0, px(8)))
        body = tk.Frame(area.body, bg=c.panel)
        body.pack(fill="both", expand=True, padx=(0, px(12)))
        body_builder(body)
        panel.lift()
        self.panel, self.panel_kind = panel, kind

    def close_panel(self):
        if self.panel is not None:
            self.panel.destroy()
        self.panel = self.panel_kind = None
        self.popover.close()

    def _refresh_panel(self, kind):
        if self.panel_kind == kind:
            {"history": self.open_history, "favorites": self.open_favorites}[kind]()

    def _section(self, parent, title, first=False):
        c, px = self.c, self.px
        f = tk.Frame(parent, bg=c.panel)
        f.pack(fill="x", pady=(0 if first else px(22), 0))
        tk.Label(f, text=title.upper(), font=self.fonts.caps, bg=c.panel, fg=c.muted).pack(anchor="w",
                                                                                          pady=(0, px(6)))
        return f

    def _label(self, parent, text):
        tk.Label(parent, text=text, font=self.fonts.small, bg=self.c.panel, fg=self.c.muted).pack(
            anchor="w", pady=(self.px(8), self.px(6)))

    def _hint(self, parent, text):
        tk.Label(parent, text=text, font=self.fonts.tiny, bg=self.c.panel, fg=self.c.faint, justify="left",
                 wraplength=self.px(330), anchor="w").pack(anchor="w", pady=(self.px(6), 0))

    def _setting_row(self, parent, label, widget_factory):
        row = tk.Frame(parent, bg=self.c.panel)
        row.pack(fill="x", pady=self.px(4))
        tk.Label(row, text=label, font=self.fonts.body, bg=self.c.panel, fg=self.c.text).pack(side="left")
        widget_factory(row).pack(side="right")

    def _switch_row(self, parent, title, sub, value, on_change):
        c, px = self.c, self.px
        row = tk.Frame(parent, bg=c.panel)
        row.pack(fill="x", pady=px(4))
        Switch(row, self, value, on_change, accent=self.accent).pack(side="right")
        left = tk.Frame(row, bg=c.panel)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, font=self.fonts.body, bg=c.panel, fg=c.text, anchor="w").pack(anchor="w")
        tk.Label(left, text=sub, font=self.fonts.tiny, bg=c.panel, fg=c.faint, anchor="w", justify="left",
                 wraplength=px(270)).pack(anchor="w")

    def _empty(self, parent, text):
        tk.Label(parent, text=text, font=self.fonts.small, bg=self.c.panel, fg=self.c.faint, justify="left",
                 wraplength=self.px(320)).pack(anchor="w", pady=self.px(8))

    # --- Paramètres
    def open_settings(self):
        t, c = self.t, self.c
        if self.panel_kind == "settings":
            return
        s = self.settings_state = {k: self.cfg[k] for k in ("language", "theme", "player", "show_scripts",
                                                             "live_check", "live_interval", "live_notify",
                                                             "tray", "hotkey", "autostart", "update_check",
                                                             "hotkey_combo")}
        self.v_player_path = tk.StringVar(value=self.cfg["player_path"])
        self.v_player_args = tk.StringVar(value=self.cfg["player_args"])
        self.v_streamlink = tk.StringVar(value=self.cfg["streamlink_path"])
        self.v_folder = tk.StringVar(value=self.cfg["scripts_folder"])
        langs = core.available_languages()

        def player_badge():
            path = self.v_player_path.get().strip()
            if not path:
                return None
            if os.path.isfile(path) or core.shutil.which(path):
                return t("badge_found"), c.ok, "check"
            return t("badge_not_found"), c.warn, "warning"

        def on_player(v):
            s["player"] = v
            if v in core.PLAYER_CANDIDATES:
                self.v_player_path.set(core.find_player(v) or "")
            elif v == "default":
                self.v_player_path.set("")

        def body(b):
            sec = self._section(b, t("settings_general"), first=True)
            self._setting_row(sec, t("label_language"), lambda p: Segmented(
                p, self, list(langs.items()), s["language"], lambda v: s.update(language=v)))
            self._setting_row(sec, t("label_theme"), lambda p: Segmented(
                p, self, [("auto", t("theme_auto")), ("light", t("theme_light")), ("dark", t("theme_dark"))],
                s["theme"], lambda v: s.update(theme=v)))
            self._hint(sec, t("hint_theme_auto"))

            sec = self._section(b, t("settings_live"))
            self._switch_row(sec, t("label_live_check"), t("hint_live_check"), s["live_check"],
                             lambda v: s.update(live_check=v))
            self._setting_row(sec, t("label_live_interval"), lambda p: Select(
                p, self, [(m, t("minutes", count=m)) for m in core.LIVE_INTERVALS], s["live_interval"],
                lambda v: s.update(live_interval=v), height=36, width=120, font=self.fonts.small))
            self._switch_row(sec, t("label_live_notify"), t("hint_live_notify"), s["live_notify"],
                             lambda v: s.update(live_notify=v))

            sec = self._section(b, t("settings_window"))
            self._switch_row(sec, t("label_tray"), t("hint_tray"), s["tray"], lambda v: s.update(tray=v))
            self._switch_row(sec, t("label_hotkey"), t("hint_hotkey"), s["hotkey"], lambda v: s.update(hotkey=v))
            self._setting_row(sec, t("label_hotkey_combo"), lambda p: Select(
                p, self, [(k, v[2]) for k, v in wintray.HOTKEYS.items()], s["hotkey_combo"],
                lambda v: s.update(hotkey_combo=v), height=36, width=170, font=self.fonts.small, popup_width=190))
            status = self._hotkey_status()
            if status:
                text, color = status
                tk.Label(sec, text=text, font=self.fonts.tiny, bg=self.c.panel, fg=color, justify="left",
                         wraplength=self.px(330), anchor="w").pack(anchor="w", pady=(self.px(2), 0))
            self._switch_row(sec, t("label_autostart"), t("hint_autostart"), s["autostart"],
                             lambda v: s.update(autostart=v))
            if os.name != "nt":
                self._hint(sec, t("hint_windows_only"))

            sec = self._section(b, t("settings_player"))
            self._label(sec, t("label_player"))
            options = [(p, core.PLAYER_NAMES.get(p) or t("player_" + p)) for p in core.PLAYERS]
            Select(sec, self, options, s["player"], on_player, height=40, popup_width=300).pack(fill="x")
            self._label(sec, t("label_player_path"))
            Field(sec, self, self.v_player_path, placeholder=t("ph_player_path"), height=40, font=self.fonts.small,
                  action_icon="folder", action_command=lambda: self._browse_file(self.v_player_path),
                  badge=player_badge).pack(fill="x")
            self._label(sec, t("label_player_args"))
            Field(sec, self, self.v_player_args, placeholder=t("ph_player_args"), height=40, mono=True).pack(fill="x")

            sec = self._section(b, "Streamlink")
            self.sl_card = StatusCard(sec, self, False, "", "", t("btn_check"), self._sl_card_action)
            self.sl_card.pack(fill="x")
            self._update_sl_card(busy=self._update_busy)
            self._switch_row(sec, t("label_update_check"), t("hint_update_check"), s["update_check"],
                             lambda v: s.update(update_check=v))
            self._label(sec, t("label_streamlink_path"))
            Field(sec, self, self.v_streamlink, placeholder=t("ph_auto_detect"), height=40, font=self.fonts.small,
                  action_icon="folder", action_command=lambda: self._browse_file(self.v_streamlink)).pack(fill="x")

            sec = self._section(b, t("settings_advanced"))
            self._switch_row(sec, t("label_show_scripts"), t("hint_show_scripts"), s["show_scripts"],
                             lambda v: s.update(show_scripts=v))
            self._label(sec, t("label_folder"))
            Field(sec, self, self.v_folder, height=40, font=self.fonts.small, action_icon="folder",
                  action_command=self._browse_folder).pack(fill="x")

        def footer(fb):
            Button(fb, self, text=t("btn_edit_platforms"), kind="link", font=self.fonts.small, pad=0, height=40,
                   command=lambda: self.open_path(str(core.PLATFORMS_FILE))).pack(side="left")
            Button(fb, self, text=t("btn_save"), kind="primary", accent=self.accent, height=40,
                   font=self.fonts.body_semi, command=self.save_settings, radius=9).pack(side="right")

        self.open_panel("settings", t("title_settings"), body, footer)

    # --- Streamlink : version et mises à jour
    def _update_sl_card(self, busy=False):
        t = self.t
        try:
            if not hasattr(self, "sl_card") or not self.sl_card.winfo_exists():
                return
        except tk.TclError:
            return
        path = core.find_streamlink(self.v_streamlink.get().strip())
        card = self.sl_card
        if busy:
            card.set_state(True, t("sl_checking"), path or "", button=t("btn_check"), level="busy")
            return
        if not path:
            card.set_state(False, t("sl_missing"), t("sl_missing_detail"), button=t("btn_install"))
            return
        r = self.sl_update if self.sl_update and self.sl_update.get("path") == path else None
        if r and r.get("update"):
            card.set_state(False, t("sl_update_title", latest=r["latest"]),
                           t("sl_update_detail", installed=r["installed"], path=path),
                           button=t("btn_update"), level="update", primary=True)
        elif r and r.get("update") is False:
            card.set_state(True, t("sl_up_to_date", version=r["installed"]), path, button=t("btn_check"))
        elif r and r.get("installed"):
            card.set_state(True, t("sl_version", version=r["installed"]), t("sl_check_failed"),
                           button=t("btn_check"))
        else:
            card.set_state(True, t("sl_found"), path, button=t("btn_check"))

    def _sl_card_action(self):
        path = core.find_streamlink(self.v_streamlink.get().strip())
        r = self.sl_update
        if not path:
            self.open_url(core.STREAMLINK_INSTALL_URL)
        elif r and r.get("path") == path and r.get("update"):
            self.open_update()
        else:
            self.check_streamlink_update(manual=True)

    def check_streamlink_update(self, manual=False):
        """Compare la version installée à la dernière publiée, hors de l'interface (thread)."""
        if self._update_busy:
            return
        in_settings = self.panel_kind == "settings" and hasattr(self, "v_streamlink")
        path_setting = self.v_streamlink.get().strip() if in_settings else self.cfg["streamlink_path"]
        self._update_busy = True
        if in_settings:
            self._update_sl_card(busy=True)
        self.run_in_thread(lambda: core.check_streamlink_update(path_setting),
                           lambda result: self._update_checked(result, manual))

    def _update_checked(self, result, manual):
        t = self.t
        self._update_busy = False
        if isinstance(result, Exception):
            result = {"path": None, "installed": None, "latest": None, "update": None, "kind": "pip",
                      "error": "network"}
        self.sl_update = result
        self._update_sl_card()
        self._refresh_update_badge()
        if result.get("update"):
            self.log(t("log_update_available", installed=result["installed"], latest=result["latest"]), "warn")
            self.toast(t("toast_update_available", latest=result["latest"]), "warn",
                       action=(t("btn_update"), self.open_update), duration=8000, low_priority=not manual)
            if not manual and self.tray_active and self.state() == "withdrawn":
                self.tray.notify(t("toast_update_available", latest=result["latest"]), t("notif_update_body"))
        elif result.get("update") is False:
            self.log(t("log_up_to_date", version=result["installed"], latest=result["latest"]), "dim")
            if manual:
                self.toast(t("toast_up_to_date", version=result["installed"]), "ok")
        elif manual:
            error = result.get("error")
            if error == "missing":
                self.toast(t("toast_no_streamlink"), "warn",
                           action=(t("btn_install"), lambda: self.open_url(core.STREAMLINK_INSTALL_URL)))
            elif error == "version":
                self.toast(t("toast_version_unknown"), "warn")
            else:
                self.toast(t("toast_update_check_failed"), "warn")

    def _refresh_update_badge(self):
        if hasattr(self, "settings_btn"):
            try:
                self.settings_btn.set_badge(self.c.warn if (self.sl_update or {}).get("update") else None)
            except tk.TclError:
                pass

    def open_update(self):
        """Installateur Windows : page de téléchargement. Installation pip : commande copiée."""
        t = self.t
        r = self.sl_update or {}
        if r.get("kind") == "windows":
            self.open_url(core.WINDOWS_BUILDS_URL)
            self.toast(t("toast_update_page_opened"), "ok")
        else:
            self.clipboard_clear()
            self.clipboard_append(core.PIP_UPGRADE_CMD)
            self.toast(t("toast_pip_copied", cmd=core.PIP_UPGRADE_CMD), "ok", duration=6000)
            self.log(t("log_pip_command", cmd=core.PIP_UPGRADE_CMD))

    def open_url(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            self.toast(self.t("log_error", error=e), "error")

    def save_settings(self):
        s = self.settings_state
        old_lang = self.cfg["language"]
        self.cfg.update(language=s["language"], theme=s["theme"], player=s["player"],
                        player_path=self.v_player_path.get().strip(), player_args=self.v_player_args.get().strip(),
                        streamlink_path=self.v_streamlink.get().strip(), show_scripts=bool(s["show_scripts"]),
                        scripts_folder=self.v_folder.get().strip() or str(core.DEFAULT_FOLDER),
                        live_check=bool(s["live_check"]), live_interval=int(s["live_interval"]),
                        live_notify=bool(s["live_notify"]), tray=bool(s["tray"]), hotkey=bool(s["hotkey"]),
                        update_check=bool(s["update_check"]), hotkey_combo=s["hotkey_combo"])
        if self.sl_update and self.sl_update.get("path") != core.find_streamlink(self.cfg["streamlink_path"]):
            self.sl_update = None  # autre Streamlink choisi : l'ancien résultat ne vaut plus
        autostart_error = False
        if bool(s["autostart"]) != bool(self.cfg.get("autostart")):
            script = os.path.join(str(core.BASE_DIR), "slink_launcher.py")
            if wintray.set_autostart(bool(s["autostart"]), script, sys.executable) or os.name != "nt":
                self.cfg["autostart"] = bool(s["autostart"])
            else:
                autostart_error = True
        if self.target[0] == "script" and not self.cfg["show_scripts"]:
            self.target = ("platform", self.platforms[0]["id"])
        core.save_config(self.cfg)
        self.platforms, error = core.load_platforms()
        if self.target[0] == "platform" and not self.platform_by_id(self.target[1]):
            self.target = ("platform", self.platforms[0]["id"])
        if self.cfg["language"] != old_lang:
            self.t.set(self.cfg["language"])
        if not self.cfg["live_check"]:
            self.live.clear()
        self.apply_tray_settings(startup=True)  # avant la reconstruction : l'état affiché est à jour
        self.build(reopen="settings")
        self.schedule_live(1500)
        if error:
            self.log(self.t("log_platforms_error", error=error), "err")
            self.toast(self.t("toast_platforms_error"), "error", action=(self.t("action_show_log"), self.show_log))
        elif autostart_error:
            self.toast(self.t("toast_autostart_failed"), "error")
        else:
            self.toast(self.t("toast_settings_saved"), "ok")

    def _browse_file(self, var):
        filetypes = [(self.t("filetype_exe"), "*.exe"), ("*", "*")] if os.name == "nt" else [("*", "*")]
        path = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if path:
            var.set(os.path.normpath(path))

    def _browse_folder(self):
        path = filedialog.askdirectory(parent=self, initialdir=self.v_folder.get() or str(core.DEFAULT_FOLDER))
        if path:
            self.v_folder.set(os.path.normpath(path))

    def open_path(self, path):
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.toast(self.t("log_error", error=e), "error")

    # --- Historique
    def open_history(self):
        t = self.t

        def body(b):
            if not self.store.history:
                self._empty(b, t("hint_no_recents"))
                return
            for e in self.store.history:
                name, color = self.target_label(self.entry_target(e))
                row = ListRow(b, self, e.get("channel") or name, f"{name} · {t.format_date(e.get('date', ''))}",
                              color, [], on_click=lambda e=e: (self.fill_from_entry(e), self.close_panel()))
                row.actions = [("play", lambda e=e: self.launch_entry(e)),
                               ("delete", lambda e=e, r=row: self._delete_history(e, r))]
                row.pack(fill="x")

        def footer(fb):
            if self.store.history:
                Button(fb, self, text=t("btn_clear_history"), kind="link", color=self.c.error, font=self.fonts.small,
                       pad=0, height=32, command=self._clear_history).pack(side="left")
            tk.Label(fb, text=t("history_count", count=len(self.store.history)), font=self.fonts.tiny,
                     bg=self.c.panel, fg=self.c.faint).pack(side="right")

        self.open_panel("history", t("title_history"), body, footer)

    def _delete_history(self, entry, row):
        self.store.remove_history(entry)
        row.destroy()
        self.build_recents()

    def _clear_history(self):
        if messagebox.askyesno(self.t("title_confirm"), self.t("confirm_clear_history"), parent=self):
            self.store.clear_history()
            self.build_recents()
            self.open_history()

    # --- Favoris
    def open_favorites(self):
        t = self.t

        def body(b):
            if not self.store.favorites:
                self._empty(b, t("hint_no_favorites"))
                return
            for fav in self.store.favorites:
                name, color = self.target_label(self.entry_target(fav))
                info = self.live_info(fav)
                if info and info.get("live"):
                    detail = " · ".join(x for x in (t("live_on"), info.get("game"), info.get("title")) if x)
                else:
                    detail = f"{t('added_on')} {t.format_date(fav.get('added', ''))}"
                ListRow(b, self, fav.get("channel", "?"), f"{name} · {detail}",
                        color, [("play", lambda e=fav: self.launch_favorite(e)),
                                ("delete", lambda e=fav: self.remove_favorite(e))],
                        on_click=lambda e=fav: (self.fill_from_entry(e), self.close_panel())).pack(fill="x")

        def footer(fb):
            tk.Label(fb, text=t("hint_favorites_panel"), font=self.fonts.tiny, bg=self.c.panel, fg=self.c.faint,
                     justify="left", wraplength=self.px(330)).pack(anchor="w")

        self.open_panel("favorites", t("title_favorites"), body, footer)

    # =====================================================
    # Démarrage et fermeture
    # =====================================================
    def _startup_checks(self):
        t = self.t
        if self.platforms_error:
            self.log(t("log_platforms_error", error=self.platforms_error), "err")
            self.toast(t("toast_platforms_error"), "error", action=(t("action_show_log"), self.show_log))
        elif not core.find_streamlink(self.cfg["streamlink_path"]):
            self.log(t("log_no_streamlink", url=core.STREAMLINK_INSTALL_URL), "err")
            self.toast(t("toast_no_streamlink"), "error", action=(t("action_settings"), self.open_settings),
                       duration=6000)

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
        if running and not messagebox.askyesno(self.t("title_confirm"),
                                               self.t("confirm_quit_running", count=len(running)), parent=self):
            return
        self.streams.stop_all()
        if self._live_job:
            self.after_cancel(self._live_job)
        self.mini.hide()
        if self.tray is not None:
            self.tray.stop()
        self._save_window_state()
        self.destroy()


def main():
    from .theme import enable_dpi_awareness, set_app_id
    if not wintray.acquire_single_instance():
        return  # déjà ouvert : sa fenêtre vient d'être affichée
    enable_dpi_awareness()
    set_app_id()
    App().mainloop()
