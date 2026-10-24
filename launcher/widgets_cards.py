"""Cartes et lignes : favoris, récents, listes, streams en cours, barre du tiroir, cartes d'état.

Cards and rows: favorites, recents, lists, running streams, drawer bar, status cards."""

from .theme import fit_text, mix
from .widgets_base import Widget


class Card(Widget):
    """Carte de favori, ou carte « Ajouter » (add=True).

    media : None = carte compacte. Sinon, carte avec une zone d'aperçu en haut. Chaque carte demande la
    hauteur qui donne un aperçu 16:9 ; la grille les étire toutes à la plus haute (sticky="nsew"), si bien
    que les aperçus d'une même rangée ont exactement la même hauteur. Contenu : {"live": True/False/None, "viewers": int ou None, "stream_title": str, "image": f(l, h)
    -> PhotoImage ou None}. Un dict vide sert à la carte « Ajouter » pour qu'elle garde la même hauteur.

    Favorite card, or "Add" card (add=True).

    media: None = compact card. Otherwise, a card with a preview area at the top. Each card requests the
    height that gives a 16:9 preview; the grid stretches them all to the tallest one (sticky="nsew"), so
    that the previews of the same row have exactly the same height. Content: {"live": True/False/None, "viewers": int or None, "stream_title": str, "image": f(w, h)
    -> PhotoImage or None}. An empty dict is used for the "Add" card so that it keeps the same height.
    """

    INSET, TEXT_H = 6, 72          # marge autour de l'aperçu, hauteur de la partie texte (px logiques)
                                   # margin around the preview, height of the text part (logical px)
    LIVE_RED, BADGE_BG = "#E91916", "#0E0E10"

    def __init__(self, parent, app, title="", subtitle="", dot=None, command=None, add=False, on_menu=None,
                 height=86, status=None, media=None, accent=None):
        self.title, self.subtitle, self.dot, self.add = title, subtitle, dot, add
        self.accent = accent  # couleur de la plateforme : teinte le fond et le contour (None = carte neutre)
                              # platform color: tints the background and the outline (None = neutral card)
        self.status = status  # None (inconnu) ou (texte, en_direct: bool)
                              # None (unknown) or (text, is_live: bool)
        self.media = media
        self._image = None    # référence de l'aperçu affiché (sinon Tk l'efface)
                              # reference to the displayed preview (otherwise Tk clears it)
        super().__init__(parent, app, width=app.px(120), height=app.px(height), command=command)
        if on_menu:
            self.bind("<Button-3>", on_menu)

    def thumb_size(self, w, h=None):
        """Taille de l'aperçu : toute la largeur (moins les marges) ; hauteur 16:9, ou ce que laisse la carte.

        Size of the preview: the full width (minus the margins); 16:9 height, or what the card leaves."""
        tw = max(16, w - 2 * self.px(self.INSET))
        th = round(tw * 9 / 16) if h is None else h - self.px(self.INSET) - self.px(self.TEXT_H)
        return tw, max(16, th)

    def _on_configure(self, e):
        if self.media is not None and e.width > 1:
            want = self.px(self.INSET) + self.thumb_size(e.width)[1] + self.px(self.TEXT_H)
            if int(self.cget("height")) != want:
                self.configure(height=want)
        super()._on_configure(e)

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        r = px(12)
        if self.add:
            if self.hover:
                self.P.round_rect(self, 0, 0, w, h, r, c.hover(bg), c.hover(bg), bg)
            self.P.dashed_round_rect(self, 0, 0, w, h, r, c.border_strong if self.hover else c.border)
            fg = c.text if self.hover else c.muted
            self.icon("add", w / 2, h / 2 - px(11), px(17), fg)
            self.create_text(w / 2, h / 2 + px(14), text=fit_text(self.app.fonts.small, self.title, w - px(16)),
                             font=self.app.fonts.small, fill=fg)
            return
        live = bool(self.status and self.status[1]) or bool(self.media and self.media.get("live"))
        fill = c.surface_hover if self.hover else c.surface
        outline = (self.dot or c.border_strong) if self.hover else (c.border_strong if live else c.border)
        if self.accent:   # accent de la plateforme : fond légèrement teinté, contour coloré (plein en direct)
                          # platform accent: slightly tinted background, colored outline (solid when live)
            fill = mix(fill, self.accent, 0.13 if self.hover else 0.07)
            outline = self.accent if (self.hover or live) else mix(c.border, self.accent, 0.5)
        self.P.round_rect(self, 0, 0, w, h, r, fill, outline, bg)
        f = self.app.fonts
        top = px(14)
        if self.media is not None:
            top = self._draw_media(w, h, fill) + px(10)
        title_w = w - px(28) - (px(22) if self.hover else 0)
        self.create_text(px(14), top, text=fit_text(f.card_title, self.title, title_w), font=f.card_title,
                         fill=c.text, anchor="nw")
        if self.hover:
            self.icon("play_fill", w - px(20), top + px(10), px(12), self.dot or c.text)
        if self.media and self.media.get("live") and self.media.get("stream_title"):
            self.create_text(px(14), top + px(24), text=fit_text(f.tiny, self.media["stream_title"], w - px(28)),
                             font=f.tiny, fill=c.muted, anchor="nw")
        y = h - px(20) if self.media is None else h - px(17)
        right = w - px(14)
        if self.status:
            text, on = self.status
            color = c.ok if on else c.faint
            tw = f.tiny.measure(text)
            self.create_text(right, y, text=text, font=f.tiny, fill=color, anchor="e")
            cx = right - tw - px(9)
            if on:
                self.P.circle(self, cx, y, px(7), color, bg=fill)
            else:
                self.P.circle(self, cx, y, px(7), fill, bg=fill, outline=color)
            right = cx - px(12)
        if self.dot:
            self.P.circle(self, px(14) + px(3.5), y, px(7), self.dot, bg=fill)
        self.create_text(px(27), y, text=fit_text(f.tiny, self.subtitle, right - px(27)), font=f.tiny, fill=c.muted,
                         anchor="w")

    def _draw_media(self, w, h, fill):
        """Zone d'aperçu : image du stream (ou fond de remplacement), badge EN DIRECT, spectateurs.
        Renvoie le bas de la zone.

        Preview area: stream image (or placeholder background), LIVE badge, viewers.
        Returns the bottom of the area."""
        c, f, px, m, t = self.c, self.app.fonts, self.px, self.media, self.app.t
        i = px(self.INSET)
        tw, th = self.thumb_size(w, h)
        live = m.get("live")
        image = m["image"](tw, th) if live and m.get("image") else None
        self._image = image
        if image is not None:
            self.create_image(i, i, image=image, anchor="nw")
        else:
            tint = mix(fill, self.dot or c.border_strong, 0.14 if live else 0.06)
            self.P.round_rect(self, i, i, i + tw, i + th, px(8), tint, tint, fill)
            if live is False:
                self.create_text(i + tw / 2, i + th / 2, text=t("live_off"), font=f.small, fill=c.faint)
            elif live:  # en direct sans image (Kick, ou aperçu pas encore chargé)
                        # live without an image (Kick, or preview not loaded yet)
                self.icon("play_fill", i + tw / 2, i + th / 2, px(22), self.dot or c.muted)
        if live:
            badge = t("live_on").upper()
            bx = by = i + px(8)
            bw, bh = f.caps.measure(badge) + px(10), px(18)
            self.create_rectangle(bx, by, bx + bw, by + bh, fill=self.LIVE_RED, width=0)
            self.create_text(bx + bw / 2, by + bh / 2, text=badge, font=f.caps, fill="#FFFFFF")
            viewers = m.get("viewers")
            if isinstance(viewers, int):
                text = t.viewers(viewers)
                if f.tiny.measure(text) > tw - px(26):
                    text = t.format_number(viewers)
                vw, vh = f.tiny.measure(text) + px(10), px(20)
                vy = i + th - px(8) - vh
                self.create_rectangle(bx, vy, bx + vw, vy + vh, fill=self.BADGE_BG, width=0)
                self.create_text(bx + px(5), vy + vh / 2, text=text, font=f.tiny, fill="#FFFFFF", anchor="w")
        return i + th


class RecentRow(Widget):
    """Ligne « récents » : un clic remplit le champ, le bouton ▶ relance directement.

    "Recent" row: a click fills the field, the ▶ button starts it again directly."""

    def __init__(self, parent, app, name, platform, dot, date, on_fill, on_launch, last=False):
        self.name, self.platform, self.dot, self.date = name, platform, dot, date
        self.on_fill, self.on_launch, self.last = on_fill, on_launch, last
        super().__init__(parent, app, width=app.px(400), height=app.px(44), command=on_fill)

    def zone_at(self, x, y):
        return "play" if x >= self.winfo_width() - self.px(40) else "row"

    def on_click(self, e):
        if self.zone_at(e.x, e.y) == "play":
            self.on_launch()
        else:
            self.on_fill()

    def draw(self, w, h):
        c, f, px = self.c, self.app.fonts, self.px
        bg = self.cget("bg")
        col_date = w - px(36) - px(150)
        col_plat = col_date - px(150)
        name_color = c.text
        self.create_text(0, h / 2, text=fit_text(f.body, self.name, col_plat - px(16)), font=f.body, fill=name_color,
                         anchor="w")
        self.P.circle(self, col_plat + px(3.5), h / 2, px(7), self.dot, bg=bg)
        self.create_text(col_plat + px(14), h / 2, text=fit_text(f.small, self.platform, px(130)), font=f.small,
                         fill=c.muted, anchor="w")
        self.create_text(col_date, h / 2, text=self.date, font=f.small, fill=c.faint, anchor="w")
        bx = w - px(18)
        if self.zone == "play":
            self.P.round_rect(self, bx - px(16), h / 2 - px(16), bx + px(16), h / 2 + px(16), px(8),
                              c.hover(bg), c.hover(bg), bg)
        play_color = self.dot if self.hover else c.muted
        self.icon("play", bx, h / 2, px(13), play_color)
        if not self.last:
            self.create_rectangle(0, h - 1, w, h, fill=c.border, width=0)


class ListRow(Widget):
    """Ligne des panneaux Historique / Favoris : titre, sous-titre, actions à droite.

    Row of the History / Favorites panels: title, subtitle, actions on the right."""

    def __init__(self, parent, app, title, subtitle, dot, actions, on_click=None):
        self.title, self.subtitle, self.dot, self.actions = title, subtitle, dot, actions
        self.on_row = on_click
        super().__init__(parent, app, width=app.px(300), height=app.px(54), command=on_click or (lambda: None))

    def _zones(self, w):
        px = self.px
        return [(w - px(22) - k * px(38), name) for k, (name, _cb) in enumerate(self.actions)]

    def zone_at(self, x, y):
        for cx, name in self._zones(self.winfo_width()):
            if abs(x - cx) <= self.px(17):
                return name
        return "row"

    def on_click(self, e):
        z = self.zone_at(e.x, e.y)
        for name, cb in self.actions:
            if name == z:
                cb()
                return
        if self.on_row:
            self.on_row()

    def draw(self, w, h):
        c, f, px, bg = self.c, self.app.fonts, self.px, self.cget("bg")
        fill = c.panel_hover if self.hover else bg
        if self.hover:
            self.P.round_rect(self, 0, px(2), w, h - px(2), px(8), fill, fill, bg)
        actions_w = len(self.actions) * px(38) + px(8)
        self.create_text(px(12), h / 2 - px(9), text=fit_text(f.body_semi, self.title, w - actions_w - px(16)),
                         font=f.body_semi, fill=c.text, anchor="w")
        self.P.circle(self, px(12) + px(3.5), h / 2 + px(10), px(7), self.dot, bg=fill)
        self.create_text(px(25), h / 2 + px(10), text=fit_text(f.tiny, self.subtitle, w - actions_w - px(30)),
                         font=f.tiny, fill=c.muted, anchor="w")
        for cx, name in self._zones(w):
            if self.zone == name:
                hov = mix(fill, "#808080", 0.18)
                self.P.round_rect(self, cx - px(16), h / 2 - px(16), cx + px(16), h / 2 + px(16), px(8), hov, hov,
                                  fill)
            color = c.text if self.zone == name else c.muted
            if name == "delete" and self.zone == name:
                color = c.error
            self.icon(name, cx, h / 2, px(14), color)


class StreamRow(Widget):
    """Stream en cours dans le tiroir : nom, détails, bouton Arrêter.

    Running stream in the drawer: name, details, Stop button."""

    zone_cursor = True

    def __init__(self, parent, app, name, detail, dot, stop_label, on_stop):
        self.name, self.detail, self.dot, self.stop_label, self.on_stop = name, detail, dot, stop_label, on_stop
        super().__init__(parent, app, width=app.px(300), height=app.px(38), command=None, focusable=False)

    def _stop_box(self, w, h):
        tw = self.app.fonts.tiny.measure(self.stop_label)
        x1 = w - self.px(6)
        return x1 - tw - self.px(36), self.px(5), x1, h - self.px(5)

    def zone_at(self, x, y):
        x0, _y0, x1, _y1 = self._stop_box(self.winfo_width(), self.winfo_height())
        return "stop" if x0 <= x <= x1 else None

    def on_click(self, e):
        if self.zone_at(e.x, e.y) == "stop":
            self.on_stop()

    def draw(self, w, h):
        c, f, px, bg = self.c, self.app.fonts, self.px, self.cget("bg")
        self.P.round_rect(self, 0, 0, w, h, px(8), c.surface, c.border, bg)
        self.P.circle(self, px(12) + px(3.5), h / 2, px(7), self.dot, bg=c.surface)
        self.create_text(px(26), h / 2, text=self.name, font=f.small_semi, fill=c.text, anchor="w")
        x = px(26) + f.small_semi.measure(self.name) + px(12)
        x0, y0, x1, y1 = self._stop_box(w, h)
        self.create_text(x, h / 2, text=fit_text(f.small, self.detail, x0 - x - px(10)), font=f.small, fill=c.muted,
                         anchor="w")
        fill = c.hover(c.surface) if self.zone == "stop" else c.surface
        self.P.round_rect(self, x0, y0, x1, y1, px(6), fill, c.border_strong if self.zone else c.border, c.surface)
        self.icon("stop", x0 + px(14), h / 2, px(9), c.text)
        self.create_text(x0 + px(26), h / 2, text=self.stop_label, font=f.tiny, fill=c.text, anchor="w")


class DrawerBar(Widget):
    def __init__(self, parent, app, command):
        self.text, self.label, self.open, self.active = "", "", False, False
        super().__init__(parent, app, width=app.px(400), height=app.px(44), command=command)

    def set_state(self, text, label, open_, active):
        self.text, self.label, self.open, self.active = text, label, open_, active
        self.redraw()

    def draw(self, w, h):
        c, f, px, bg = self.c, self.app.fonts, self.px, self.cget("bg")
        if self.hover:
            self.create_rectangle(0, 0, w, h, fill=c.hover(bg), width=0)
        fill = c.hover(bg) if self.hover else bg
        dot = c.ok if self.active else c.faint
        if self.active:
            self.P.circle(self, px(36), h / 2, px(14), mix(fill, dot, 0.25), bg=fill)
        self.P.circle(self, px(36), h / 2, px(8), dot, bg=mix(fill, dot, 0.25) if self.active else fill)
        self.create_text(px(50), h / 2, text=self.text, font=f.small, fill=c.text, anchor="w")
        self.icon("chevron_down" if self.open else "chevron_up", w - px(30), h / 2, px(11), c.muted)
        self.create_text(w - px(44), h / 2, text=self.label, font=f.small, fill=c.muted, anchor="e")


class StatusCard(Widget):
    """Carte d'état (Streamlink trouvé / introuvable) avec un bouton à droite.

    Status card (Streamlink found / not found) with a button on the right."""

    LEVELS = {"ok": ("check", "ok"), "warn": ("warning", "warn"), "update": ("arrow_up", "warn"),
              "busy": ("sync", "muted")}
    zone_cursor = True

    def __init__(self, parent, app, ok, title, detail, button, on_button):
        self.level = "ok" if ok else "warn"
        self.title, self.detail, self.button, self.on_button = title, detail, button, on_button
        self.primary = False
        super().__init__(parent, app, width=app.px(300), height=app.px(60), command=None, focusable=False)

    @property
    def ok(self):
        return self.level == "ok"

    def set_state(self, ok, title, detail, button=None, level=None, primary=False):
        """level : ok, warn, update (mise à jour disponible) ou busy (vérification en cours).

        level: ok, warn, update (update available) or busy (check in progress)."""
        self.level = level or ("ok" if ok else "warn")
        self.title, self.detail, self.primary = title, detail, primary
        if button is not None:
            self.button = button
        self.redraw()

    def _btn(self, w, h):
        if not self.button:  # pas de bouton (opération en cours)
                             # no button (operation in progress)
            return w - self.px(12), h / 2, w - self.px(12), h / 2
        tw = self.app.fonts.small.measure(self.button)
        return w - self.px(12) - tw - self.px(24), h / 2 - self.px(16), w - self.px(12), h / 2 + self.px(16)

    def zone_at(self, x, y):
        if not self.button:
            return None
        x0, y0, x1, y1 = self._btn(self.winfo_width(), self.winfo_height())
        return "btn" if x0 <= x <= x1 and y0 <= y <= y1 else None

    def on_click(self, e):
        if self.zone_at(e.x, e.y) == "btn":
            self.on_button()

    def draw(self, w, h):
        c, f, px, bg = self.c, self.app.fonts, self.px, self.cget("bg")
        self.P.round_rect(self, 0, 0, w, h, px(10), c.field, c.border, bg)
        icon, color_key = self.LEVELS.get(self.level, self.LEVELS["warn"])
        color = c[color_key]
        box = mix(c.field, color, 0.16)
        self.P.round_rect(self, px(12), h / 2 - px(16), px(44), h / 2 + px(16), px(8), box, box, c.field)
        self.icon(icon, px(28), h / 2, px(15), color)
        x0, y0, x1, y1 = self._btn(w, h)
        avail = x0 - px(56) - px(10)
        self.create_text(px(56), h / 2 - px(9), text=fit_text(f.body_semi, self.title, avail), font=f.body_semi,
                         fill=c.text, anchor="w")
        self.create_text(px(56), h / 2 + px(10), text=fit_text(f.tiny, self.detail, avail), font=f.tiny,
                         fill=c.faint, anchor="w")
        if not self.button:
            return
        if self.primary:
            col, on = self.app.accent
            fill = mix(col, "#000000" if c.dark else "#FFFFFF", 0.12) if self.zone else col
            self.P.round_rect(self, x0, y0, x1, y1, px(7), fill, fill, c.field)
            self.create_text((x0 + x1) / 2, h / 2, text=self.button, font=f.small_semi, fill=on)
        else:
            fill = c.hover(c.field) if self.zone else c.field
            self.P.round_rect(self, x0, y0, x1, y1, px(7), fill, c.border_strong if self.zone else c.border, c.field)
            self.create_text((x0 + x1) / 2, h / 2, text=self.button, font=f.small, fill=c.text)
