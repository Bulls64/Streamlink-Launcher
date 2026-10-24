"""Favoris de l'écran principal, aperçus des lives et statut en direct.

Favorites on the main screen, live previews and live status.

Mixin de App (voir app.py) : ces méthodes utilisent self comme la fenêtre principale.
Mixin of App (see app.py): these methods use self as the main window."""
import base64
import tkinter as tk

from . import inputs, live, thumb, winnotify
from .app_common import FAV_SLOTS
from .widgets import (
    Card,
)


class FavoritesMixin:
    # --- favoris
    # --- favorites
    def _fav_link_text(self, shown=None):
        n = len(self.store.favorites)
        shown = len(self.shown_favorites()) if shown is None else shown
        return self.t("link_manage_count", count=n) if n > shown else self.t("link_manage")

    def favorite_matches(self, fav, target=None):
        """Le favori appartient-il à la plateforme (ou au script) choisie ?

        Does the favorite belong to the selected platform (or script)?"""
        kind, value = target or self.target
        et = self.entry_target(fav)
        if et is None:  # anciens favoris sans plateforme : lancés sur Twitch
                        # old favorites without a platform: started on Twitch
            return kind == "platform" and value == "twitch" and not fav.get("platform") and not fav.get("script")
        if et[0] == "platform":
            return kind == "platform" and et[1]["id"] == value
        return kind == "script" and et[1] == value

    def favorites_filter_name(self):
        kind, value = self.target
        if kind == "platform":
            p = self.platform_by_id(value)
            return self.platform_name(p) if p else value
        return value

    def build_favorites(self):
        c, px, t = self.c, self.px, self.t
        for w in self.fav_grid.winfo_children():
            w.destroy()
        for i in range(4):
            self.fav_grid.columnconfigure(i, weight=1, uniform="fav")
        favs = self.shown_favorites()
        # Avec l'aperçu activé et au moins un favori affiché en direct : cartes avec image (toutes la même hauteur)
        # With previews on and at least one displayed favorite live: cards with an image (all the same height)
        with_media = bool(self.cfg.get("live_previews")) and any((self.live_info(f) or {}).get("live") for f in favs)

        def pad(col):
            return (0 if col == 0 else px(5), 0 if col == 3 else px(5))

        for col, fav in enumerate(favs):
            name, color = self.target_label(self.entry_target(fav))
            info = self.live_info(fav)
            live = info.get("live") if info is not None else None
            subtitle = " · ".join(x for x in (name, with_media and live and info.get("game")) if x)
            status = media = None
            if with_media:
                key = self.live_key(fav)
                media = {"live": live, "viewers": info.get("viewers") if live else None,
                         "stream_title": (info.get("title") or "") if live else "",
                         "image": (lambda w, h, k=key: self.preview_image(k, w, h)) if key else None}
            elif info is not None:
                viewers = info.get("viewers") if live else None
                status = ((t.viewers(viewers) if isinstance(viewers, int) else t("live_on"), True) if live
                          else (t("live_off"), False))
            card = Card(self.fav_grid, self, title=fav.get("channel", "?"), subtitle=subtitle, dot=color,
                        command=lambda e=fav: self.launch_favorite(e), status=status, media=media,
                        accent=color if self.cfg.get("platform_colors") else None,
                        on_menu=lambda ev, e=fav: self.favorite_menu(ev, e))
            card.grid(row=0, column=col, sticky="nsew", padx=pad(col))
        col = len(favs)
        Card(self.fav_grid, self, title=t("card_add_favorite"), add=True, media={} if with_media else None,
             command=self.add_current_to_favorites).grid(row=0, column=col, sticky="nsew", padx=pad(col))
        if not favs:
            hint = (t("hint_no_favorites_platform", platform=self.favorites_filter_name()) if self.store.favorites
                    else t("hint_no_favorites"))
            tk.Label(self.fav_grid, text=hint, font=self.fonts.small, bg=c.bg, fg=c.faint,
                     anchor="w", justify="left").grid(row=0, column=1, columnspan=3, sticky="w", padx=px(14))
        if hasattr(self, "fav_link"):
            self.fav_link.set_text(self._fav_link_text(len(favs)))
            self.fav_link.title_label.configure(
                text=f"{t('section_favorites')} · {self.favorites_filter_name()}".upper())

    def shown_favorites(self):
        """Favoris des cartes de l'écran principal : ceux de la plateforme choisie, en direct d'abord
        (l'ordre est conservé sinon).

        Favorites of the main screen's cards: those of the selected platform, live ones first
        (the order is kept otherwise)."""
        favs = [f for f in self.store.favorites if self.favorite_matches(f)]
        return sorted(favs, key=lambda e: not (self.live_info(e) or {}).get("live"))[:FAV_SLOTS]

    # --- aperçus des lives
    # --- live previews
    def preview_image(self, key, w, h):
        """Image d'aperçu à la taille demandée, ou None (la carte affiche alors un fond de remplacement).
        La mise à l'échelle se fait hors de l'interface ; la carte est redessinée quand elle est prête.

        Preview image at the requested size, or None (the card then shows a placeholder background).
        Scaling happens outside the interface; the card is redrawn when it is ready."""
        p = self.previews.get(key)
        if not p or not p.get("data"):
            return None
        same_size = p.get("size") == (w, h)
        if (not same_size or p.get("stale")) and p.get("failed") != (w, h):
            pending = self._preview_render.get(key)
            self._preview_render[key] = (w, h)
            if pending is None:  # pendant un redimensionnement, seule la dernière taille est calculée
                                 # during a resize, only the last size is computed
                self.after(150, lambda: self._render_preview(key))
        return p.get("img") if same_size else None

    def _render_preview(self, key):
        size = self._preview_render.pop(key, None)
        p = self.previews.get(key)
        if size is None or not p or not p.get("data"):
            return
        data, (w, h), radius = p["data"], size, self.px(8)
        self.run_in_thread(lambda: thumb.render(data, w, h, radius),
                           lambda png: self._preview_rendered(key, data, size, png))

    def _preview_rendered(self, key, data, size, png):
        p = self.previews.get(key)
        if not p or p.get("data") is not data:
            return  # image remplacée entre-temps
                    # image replaced in the meantime
        p["stale"] = False
        try:
            if isinstance(png, Exception) or not png:
                raise tk.TclError(png)
            p["img"] = tk.PhotoImage(master=self, data=base64.b64encode(png))
        except tk.TclError:
            p["failed"] = size  # on garde l'image précédente s'il y en a une
                                # the previous image is kept if there is one
            return
        p["size"] = size
        self._redraw_favorite_cards()

    def _redraw_favorite_cards(self):
        for w in self.fav_grid.winfo_children():
            if isinstance(w, Card) and w.media:
                w.redraw()

    def refresh_previews(self, only_missing=False):
        """Télécharge l'aperçu des favoris affichés qui sont en direct : tous après une vérification,
        seulement ceux qui manquent quand on change de plateforme.

        Downloads the preview of the displayed favorites that are live: all of them after a check,
        only the missing ones when the platform changes."""
        if not self.cfg.get("live_previews") or not self.cfg.get("live_check"):
            self.previews.clear()
            return
        for key in list(self.previews):  # on garde les images des autres plateformes tant qu'elles sont en direct
                                         # images of the other platforms are kept as long as they are live
            if not (self.live.get(key) or {}).get("live"):
                del self.previews[key]
        urls = {}
        for fav in self.shown_favorites():
            key = self.live_key(fav)
            info = self.live.get(key) if key else None
            url = live.preview_url((info or {}).get("preview")) if info and info.get("live") else None
            if url and not (only_missing and key in self.previews):
                urls[key] = url
        if urls:
            self.run_in_thread(lambda: live.fetch_previews(urls), self._previews_fetched)

    def _previews_fetched(self, results):
        if isinstance(results, Exception):
            return
        changed = False
        for key, data in results.items():
            if not data:
                continue  # échec : on garde l'image précédente s'il y en a une
                          # failure: the previous image is kept if there is one
            old = self.previews.get(key)
            if old and old.get("data") == data:
                continue
            # La nouvelle image remplace l'ancienne dès qu'elle est prête (pas de clignotement)
            # The new image replaces the old one as soon as it is ready (no flicker)
            self.previews[key] = {"data": data, "img": (old or {}).get("img"), "size": (old or {}).get("size"),
                                  "stale": True}
            changed = True
        if changed:
            self._redraw_favorite_cards()

    def launch_favorite(self, fav):
        if self.entry_target(fav):
            return self.launch_entry(fav)
        # Anciens favoris sans plateforme : Twitch
        # Old favorites without a platform: Twitch
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
                _, channel = inputs.resolve_target(p, self.query.get())
            except inputs.InputError as e:
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
    # --- live
    def live_key(self, entry):
        """Clé de vérification d'un favori, ou None si sa plateforme ne se vérifie pas.

        Check key of a favorite, or None if its platform cannot be checked."""
        target = self.entry_target(entry)
        if not target or target[0] != "platform" or not entry.get("channel"):
            return None
        if live.live_method(target[1]) == "none":
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
        """Programme la prochaine vérification (aucune minuterie si rien à vérifier).

        Schedules the next check (no timer if there is nothing to check)."""
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
        self.run_in_thread(lambda: live.check_live(entries, platforms, streamlink_path), self._live_done)

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
                          # unknown state (network, missing plugin): the previous one is kept
            before = self.live.get(key)
            if info.get("live") and before is not None and not before.get("live"):
                started.append(key)
            self.live[key] = info
        self.build_favorites()
        self.refresh_previews()
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
            # With the notification-area icon: clickable balloon (a click starts the stream). Otherwise, PowerShell toast.
            if self.tray_active and self.tray.notify(title, body + "\n" + t("notif_click_to_watch")):
                self._balloon_fav = fav
            else:
                winnotify.toast(title, body)
        try:
            if self.focus_displayof() is None:
                winnotify.flash_taskbar(self)
        except (KeyError, tk.TclError):
            pass
