"""Intégration au bureau : zone de notification, raccourci global, fermeture, presse-papiers intelligent, glisser-déposer.

Desktop integration: notification area, global shortcut, closing, smart clipboard, drag and drop.

Mixin de App (voir app.py) : ces méthodes utilisent self comme la fenêtre principale.
Mixin of App (see app.py): these methods use self as the main window."""
import os
import tkinter as tk

from . import core, inputs, windrop, wintray
from .app_common import ICON_FILE


class DesktopMixin:
    # --- zone de notification, raccourci global, fermeture
    # --- notification area, global shortcut, closing
    @property
    def tray_active(self):
        return self.tray is not None and self.tray.icon_shown

    def setup_tray(self):
        """Crée la fenêtre Windows cachée (icône + raccourci) puis applique les réglages.

        Creates the hidden Windows window (icon + shortcut), then applies the settings."""
        if os.name != "nt":
            return
        if self.tray is None:
            # IMPORTANT : la fenêtre Windows de l'icône reçoit ses messages PENDANT que Tkinter traite les siens.
            # Appeler Tkinter à ce moment-là (même un simple after()) casse l'état interne de Python et fait
            # planter l'application (« PyEval_RestoreThread: … GIL is released »). On se contente donc de
            # déposer l'événement dans une file (sans Tk), relue ci-dessous depuis la boucle de Tkinter.
            # IMPORTANT: the icon's Windows window receives its messages WHILE Tkinter is processing its own.
            # Calling Tkinter at that moment (even a simple after()) breaks Python's internal state and crashes
            # the application ("PyEval_RestoreThread: … GIL is released"). So we only drop the event into a
            # queue (without Tk), read back below from the Tkinter loop.
            tray = wintray.Tray(self._tray_events.append, icon_path=ICON_FILE)
            if not tray.start():
                self.log(self.t("log_tray_failed"), "err")
                return
            self.tray = tray
            self._start_win_events()
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
                             # after the start-up checks, so as not to be covered
                    self.after(1500, lambda: self.toast(message[0], message[1], action=message[2], duration=7000))
                else:
                    self.toast(message[0], message[1], action=message[2], duration=7000)
        else:
            self.tray.unregister_hotkey()
        self.update_tray_tooltip()

    def _hotkey_status(self):
        """(texte, couleur) de l'état du raccourci pour les Paramètres, ou None.

        (text, color) of the shortcut state for the Settings, or None."""
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

    def _start_win_events(self):
        """Une seule boucle (10 fois par seconde) relit les files de l'icône, du raccourci et du
        glisser-déposer : deux fois moins de réveils de l'application au repos qu'avec une boucle chacun.

        A single loop (10 times per second) reads the icon, shortcut and drag-and-drop queues:
        half as many wake-ups of the idle application as with one loop each."""
        if not self._win_events_running:
            self._win_events_running = True
            self.after(100, self._poll_win_events)

    def _poll_win_events(self):
        """Traite les clics sur l'icône, le raccourci global (file remplie par wintray) et les dépôts (windrop).

        Handles clicks on the icon, the global shortcut (queue filled by wintray) and drops (windrop)."""
        for queue_, handler in ((self._tray_events, self._tray_event), (self._drop_events, self.handle_drop)):
            while queue_:
                try:
                    handler(queue_.popleft())
                except Exception as e:  # une erreur ici ne doit jamais arrêter la surveillance
                                        # an error here must never stop the polling
                    self.log(self.t("log_error", error=e), "err")
        if self.tray is not None or self.drop_target is not None:
            self.after(100, self._poll_win_events)
        else:
            self._win_events_running = False

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
            viewers = (self.live_info(fav) or {}).get("viewers")
            if isinstance(viewers, int):
                name = f"{name} · {t.viewers(viewers)}"
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
        """Bouton ✕ : réduit dans la zone de notification si elle est active, sinon quitte.

        ✕ button: minimizes to the notification area if it is enabled, otherwise quits."""
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

    # =====================================================
    # Presse-papiers intelligent
    # Smart clipboard
    # =====================================================
    def _clip_key(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:  # vide, ou contenu qui n'est pas du texte (image, fichiers…)
                             # empty, or content that is not text (image, files…)
            return None, ""
        return (inputs.clipboard_sequence(), text), text

    def clipboard_offer(self):
        """Lien de stream copié et jamais proposé -> (id de plateforme, lien), sinon None.

        Un même contenu n'est proposé qu'une fois (numéro de séquence Windows : recopier le même
        lien le repropose), et jamais s'il est déjà dans la zone de saisie.

        Stream link copied and never offered -> (platform id, link), otherwise None.

        The same content is offered only once (Windows sequence number: copying the same
        link again offers it again), and never if it is already in the input field.
        """
        if not self.cfg.get("clipboard_watch"):
            return None
        key, text = self._clip_key()
        if key is None or key == self._clip_seen:
            return None
        self._clip_seen = key
        hit = inputs.link_in_text(self.platforms, text)
        if not hit or hit[1] == self.query.get().strip():
            return None
        return hit

    def offer_clipboard(self):
        """Fenêtre principale : propose de lancer le lien copié (bouton dans la notification).

        Main window: offers to start the copied link (button in the notification)."""
        if self.state() != "normal":
            return
        offer = self.clipboard_offer()
        if not offer:
            return
        pid, link = offer
        name = self.platform_name(self.platform_by_id(pid))
        self.toast(self.t("toast_clip_found", platform=name), "info",
                   action=(self.t("btn_launch"), lambda: self.use_link(pid, link, launch=True)),
                   duration=7000, low_priority=True)

    def use_link(self, pid, link, launch=False):
        """Met un lien dans la zone de saisie (plateforme sélectionnée) et le lance si demandé.

        Puts a link in the input field (selected platform) and starts it if asked."""
        self.select_platform(pid)
        self.set_query(link)
        if launch:
            self.launch()
        else:
            self.field.focus()

    # =====================================================
    # Glisser-déposer
    # Drag and drop
    # =====================================================
    def setup_drop(self):
        if os.name != "nt":
            return
        try:
            target = windrop.DropTarget(windrop.toplevel_hwnd(self), self._drop_events.append)
        except Exception as e:  # ne jamais empêcher le démarrage pour cette fonction
                                # never prevent start-up because of this feature
            core.log.warning("glisser-déposer indisponible : %s", e)
            return
        if target.register():
            self.drop_target = target
            self._start_win_events()
        else:
            self.log(self.t("log_drop_failed"), "warn")

    def handle_drop(self, event):
        kind = event[0]
        if kind == "enter":
            self.show_drop_overlay()
            return
        self.hide_drop_overlay()
        if kind == "leave":
            return
        hit = (inputs.link_in_text(self.platforms, event[1]) if kind == "text"
               else inputs.links_from_paths(self.platforms, event[1]))
        if not hit:
            self.toast(self.t("toast_drop_unknown"), "warn")
            return
        pid, link = hit
        self._clip_seen = self._clip_key()[0]  # ce qui vient d'être déposé n'est pas à reproposer
                                               # what has just been dropped must not be offered again
        if self.state() in ("iconic", "withdrawn"):
            self.show_main()
        self.use_link(pid, link)
        name = self.platform_name(self.platform_by_id(pid))
        self.toast(self.t("toast_drop_ok", platform=name), "ok",
                   action=(self.t("btn_launch"), self.launch), duration=6000)

    def show_drop_overlay(self):
        self.hide_drop_overlay()
        c = self.c
        cv = tk.Canvas(self, bg=c.bg, highlightthickness=0, bd=0)
        cv.place(x=0, y=0, relwidth=1, relheight=1)
        cv.update_idletasks()
        w, h, m = max(cv.winfo_width(), 2), max(cv.winfo_height(), 2), self.px(24)
        self.painter.dashed_round_rect(cv, m, m, w - m, h - m, self.px(18), c.focus)
        cv.create_text(w // 2, h // 2 - self.px(12), text=self.t("drop_title"), fill=c.text,
                       font=self.fonts.panel_title)
        cv.create_text(w // 2, h // 2 + self.px(18), text=self.t("drop_sub"), fill=c.muted, font=self.fonts.small)
        tk.Misc.lift(cv)  # Canvas.lift() est tag_raise()
                          # Canvas.lift() is tag_raise()
        self._drop_overlay = cv

    def hide_drop_overlay(self):
        cv, self._drop_overlay = self._drop_overlay, None
        if cv is not None:
            try:
                cv.destroy()
            except tk.TclError:
                pass
