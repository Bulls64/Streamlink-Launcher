"""Panneaux latéraux : paramètres, sauvegarde (export / import), historique, favoris.

Side panels: settings, backup (export / import), history, favorites.

Mixin de App (voir app.py) : ces méthodes utilisent self comme la fenêtre principale.
Mixin of App (see app.py): these methods use self as the main window."""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from . import core, wintray
from .widgets import (
    Button,
    Field,
    IconButton,
    ListRow,
    ScrollArea,
    Segmented,
    Select,
    StatusCard,
    Switch,
)


class PanelsMixin:
    # =====================================================
    # Panneaux latéraux
    # Side panels
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
        # Calcule la largeur du panneau AVANT d'y créer les lignes : chacune est ainsi dessinée une seule fois,
        # directement à la bonne taille (au lieu d'une fois à sa taille demandée puis une fois à la vraie).
        # Computes the panel width BEFORE creating its rows: each one is thus drawn only once,
        # directly at the right size (instead of once at its requested size, then once at the real one).
        panel.update_idletasks()
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
    # --- Settings
    def open_settings(self):
        t, c = self.t, self.c
        if self.panel_kind == "settings":
            return
        s = self.settings_state = {k: self.cfg[k] for k in ("language", "theme", "player", "show_scripts",
                                                             "live_check", "live_interval", "live_notify",
                                                             "live_previews", "platform_colors",
                                                             "tray", "hotkey", "autostart", "update_check",
                                                             "clipboard_watch", "hotkey_combo", "auto_update")}
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
            if len(langs) <= 3:
                make_lang = lambda p: Segmented(
                    p, self, list(langs.items()), s["language"], lambda v: s.update(language=v))
            else:  # 5 langues ne tiennent plus côte à côte dans le panneau : liste déroulante
                   # 5 languages no longer fit side by side in the panel: drop-down list
                make_lang = lambda p: Select(
                    p, self, list(langs.items()), s["language"], lambda v: s.update(language=v),
                    height=36, width=130, font=self.fonts.small, popup_width=180)
            self._setting_row(sec, t("label_language"), make_lang)
            self._setting_row(sec, t("label_theme"), lambda p: Segmented(
                p, self, [("auto", t("theme_auto")), ("light", t("theme_light")), ("dark", t("theme_dark"))],
                s["theme"], lambda v: s.update(theme=v)))
            self._hint(sec, t("hint_theme_auto"))
            self._switch_row(sec, t("label_platform_colors"), t("hint_platform_colors"), s["platform_colors"],
                             lambda v: s.update(platform_colors=v))

            sec = self._section(b, t("settings_live"))
            self._switch_row(sec, t("label_live_check"), t("hint_live_check"), s["live_check"],
                             lambda v: s.update(live_check=v))
            self._setting_row(sec, t("label_live_interval"), lambda p: Select(
                p, self, [(m, t("minutes", count=m)) for m in core.LIVE_INTERVALS], s["live_interval"],
                lambda v: s.update(live_interval=v), height=36, width=120, font=self.fonts.small))
            self._switch_row(sec, t("label_live_notify"), t("hint_live_notify"), s["live_notify"],
                             lambda v: s.update(live_notify=v))
            self._switch_row(sec, t("label_live_previews"), t("hint_live_previews"), s["live_previews"],
                             lambda v: s.update(live_previews=v))

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
            self._switch_row(sec, t("label_clipboard"), t("hint_clipboard"), s["clipboard_watch"],
                             lambda v: s.update(clipboard_watch=v))
            self._label(sec, t("label_streamlink_path"))
            Field(sec, self, self.v_streamlink, placeholder=t("ph_auto_detect"), height=40, font=self.fonts.small,
                  action_icon="folder", action_command=lambda: self._browse_file(self.v_streamlink)).pack(fill="x")

            sec = self._section(b, t("settings_advanced"))
            self._switch_row(sec, t("label_show_scripts"), t("hint_show_scripts"), s["show_scripts"],
                             lambda v: s.update(show_scripts=v))
            self._label(sec, t("label_folder"))
            Field(sec, self, self.v_folder, height=40, font=self.fonts.small, action_icon="folder",
                  action_command=self._browse_folder).pack(fill="x")

            sec = self._section(b, t("settings_backup"))
            self._hint(sec, t("hint_backup"))
            row = tk.Frame(sec, bg=self.c.panel)
            row.pack(anchor="w", pady=(self.px(4), 0))
            Button(row, self, text=t("btn_export"), kind="secondary", font=self.fonts.small, height=36,
                   command=self.export_data).pack(side="left", padx=(0, self.px(8)))
            Button(row, self, text=t("btn_import"), kind="secondary", font=self.fonts.small, height=36,
                   command=self.import_data).pack(side="left")

            sec = self._section(b, t("settings_about"))
            self.app_card = StatusCard(sec, self, True, "", "", t("btn_check"), self._app_card_action)
            self.app_card.pack(fill="x")
            self._update_app_card()
            links = tk.Frame(sec, bg=self.c.panel)
            links.pack(anchor="w", pady=(self.px(2), 0))
            Button(links, self, text=t("link_release_notes"), kind="link", font=self.fonts.small, pad=0, height=32,
                   command=self._open_release_notes).pack(side="left", padx=(0, self.px(16)))
            Button(links, self, text=t("link_repo"), kind="link", font=self.fonts.small, pad=0, height=32,
                   command=lambda: self.open_url(core.REPO_URL)).pack(side="left")
            self._switch_row(sec, t("label_auto_update"), t("hint_auto_update"), s["auto_update"],
                             lambda v: s.update(auto_update=v))
            self._hint(sec, t("about_data", path=core.DATA_ROOT))
            Button(sec, self, text=t("btn_open_data"), kind="link", font=self.fonts.small, pad=0, height=32,
                   command=lambda: self.open_path(str(core.DATA_ROOT))).pack(anchor="w")

        def footer(fb):
            Button(fb, self, text=t("btn_edit_platforms"), kind="link", font=self.fonts.small, pad=0, height=40,
                   command=lambda: self.open_path(str(core.PLATFORMS_FILE))).pack(side="left")
            Button(fb, self, text=t("btn_save"), kind="primary", accent=self.accent, height=40,
                   font=self.fonts.body_semi, command=self.save_settings, radius=9).pack(side="right")

        self.open_panel("settings", t("title_settings"), body, footer)

    def save_settings(self):
        s = self.settings_state
        old_lang = self.cfg["language"]
        self.cfg.update(language=s["language"], theme=s["theme"], player=s["player"],
                        player_path=self.v_player_path.get().strip(), player_args=self.v_player_args.get().strip(),
                        streamlink_path=self.v_streamlink.get().strip(), show_scripts=bool(s["show_scripts"]),
                        scripts_folder=self.v_folder.get().strip() or str(core.DEFAULT_FOLDER),
                        live_check=bool(s["live_check"]), live_interval=int(s["live_interval"]),
                        live_notify=bool(s["live_notify"]), live_previews=bool(s["live_previews"]),
                        platform_colors=bool(s["platform_colors"]),
                        tray=bool(s["tray"]), hotkey=bool(s["hotkey"]),
                        update_check=bool(s["update_check"]), auto_update=bool(s["auto_update"]),
                        clipboard_watch=bool(s["clipboard_watch"]),
                        hotkey_combo=s["hotkey_combo"])
        if self.sl_update and self.sl_update.get("path") != core.find_streamlink(self.cfg["streamlink_path"]):
            self.sl_update = None  # autre Streamlink choisi : l'ancien résultat ne vaut plus
                                   # another Streamlink chosen: the old result no longer applies
        autostart_error = not self._apply_autostart(bool(s["autostart"]))
        core.save_config(self.cfg)
        self.platforms, error = core.load_platforms()
        if self.target[0] == "platform" and not self.platform_by_id(self.target[1]):
            self.target = ("platform", self.platforms[0]["id"])
        self._settings_changed(old_lang, clear_live=not self.cfg["live_check"])
        if error:
            self.log(self.t("log_platforms_error", error=error), "err")
            self.toast(self.t("toast_platforms_error"), "error", action=(self.t("action_show_log"), self.show_log))
        elif autostart_error:
            self.toast(self.t("toast_autostart_failed"), "error")
        else:
            self.toast(self.t("toast_settings_saved"), "ok")

    def _apply_autostart(self, wanted):
        """Active ou désactive le lancement avec Windows ; False si Windows a refusé.

        Enables or disables start-up with Windows; False if Windows refused."""
        if wanted == bool(self.cfg.get("autostart")):
            return True
        script = os.path.join(str(core.BASE_DIR), "slink_launcher.py")
        if wintray.set_autostart(wanted, script, sys.executable) or os.name != "nt":
            self.cfg["autostart"] = wanted
            return True
        return False

    # =====================================================
    # Sauvegarde : export / import des réglages et des favoris
    # Backup: export / import of the settings and favorites
    # =====================================================
    def export_data(self):
        from . import __version__
        t = self.t
        name = f"streamlink-launcher-{core.now_str()[:10]}.json"
        path = filedialog.asksaveasfilename(parent=self, title=t("btn_export"), defaultextension=".json",
                                            initialfile=name, filetypes=[(t("filetype_json"), "*.json")])
        if not path:
            return False
        backup = core.make_backup(self.cfg, self.store.favorites, __version__)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)
        except OSError as e:
            core.log.error("Export impossible vers %s : %s", path, e)
            self.toast(t("toast_export_failed"), "error")
            return False
        self.log(t("log_export_ok", path=path), "dim")
        self.toast(t("toast_export_ok", file=os.path.basename(path)), "ok")
        return True

    def import_data(self, path=None):
        t = self.t
        path = path or filedialog.askopenfilename(parent=self, title=t("btn_import"),
                                                  filetypes=[(t("filetype_json"), "*.json"), ("*", "*")])
        if not path:
            return False
        try:
            settings, favorites = core.read_backup(path, core.available_languages(), wintray.HOTKEYS)
        except core.BackupError as e:
            self.toast(t(e.key), "error")
            return False
        n, m = len(settings), len(favorites)
        if favorites:
            answer = messagebox.askyesnocancel(
                t("title_confirm"), t("confirm_import", settings=n, favorites=m), parent=self)
            if answer is None:
                return False
            replace = answer is False
        else:
            if not messagebox.askokcancel(t("title_confirm"), t("confirm_import_settings", settings=n), parent=self):
                return False
            replace = False
        old_lang = self.cfg["language"]
        autostart = settings.pop("autostart", None)  # appliqué à Windows ci-dessous, pas seulement noté
                                                     # applied to Windows below, not only recorded
        self.cfg.update(settings)
        self.cfg["qualities"] = dict(self.cfg.get("qualities") or {})
        autostart_ok = autostart is None or self._apply_autostart(autostart)
        core.save_config(self.cfg)
        if favorites:
            if replace:
                self.store.favorites = favorites
            else:
                self.store.favorites, m = core.merge_favorites(self.store.favorites, favorites)
            self.store.save_favorites()
        self._settings_changed(old_lang, clear_live=True)  # favoris peut-être changés : statuts à revérifier
                                                           # favorites may have changed: statuses to check again
        self.log(self.t("log_import_ok", settings=n, favorites=m), "dim")
        self.toast(self.t("toast_import_ok", settings=n, favorites=m) if autostart_ok
                   else self.t("toast_autostart_failed"), "ok" if autostart_ok else "error")
        return True

    def _settings_changed(self, old_lang, clear_live):
        """Après « Enregistrer » ou un import : langue, cible, statuts en direct, icône et raccourci, affichage.

        After "Save" or an import: language, target, live statuses, icon and shortcut, display."""
        if self.cfg["language"] != old_lang:
            self.t.set(self.cfg["language"])
        if self.target[0] == "script" and not self.cfg["show_scripts"]:
            self.target = ("platform", self.platforms[0]["id"])
        if clear_live:
            self.live.clear()
        self.apply_tray_settings(startup=True)  # avant la reconstruction : l'état affiché est à jour
                                                # before the rebuild: the displayed state is up to date
        self.build(reopen="settings")
        self.refresh_previews()
        self.schedule_live(1500)

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
    # --- History
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
    # --- Favorites
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
                    viewers = info.get("viewers")
                    detail = " · ".join(x for x in (t("live_on"), isinstance(viewers, int) and t.viewers(viewers),
                                                    info.get("game"), info.get("title")) if x)
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
