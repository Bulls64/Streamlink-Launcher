"""Commandes : boutons, pastilles, listes déroulantes, choix segmentés, interrupteurs.

Controls: buttons, pills, drop-down lists, segmented choices, switches."""

from .theme import fit_text, mix
from .widgets_base import Widget


class Button(Widget):
    """kind : primary (couleur d'accent), secondary (contour), ghost (fond au survol), link (texte).

    kind: primary (accent color), secondary (outline), ghost (background on hover), link (text)."""

    def __init__(self, parent, app, text="", icon=None, command=None, kind="secondary", height=40, font=None,
                 accent=None, width=None, pad=16, icon_size=14, radius=10, bg=None, color=None):
        self.app = app
        self.text, self.icon_name, self.kind = text, icon, kind
        self.font = font or app.fonts.body_semi
        self.accent = accent
        self.fg_color = color
        self.icon_size = app.px(icon_size)
        self.pad = app.px(pad)
        self.radius = app.px(radius)
        h = app.px(height)
        w = app.px(width) if width else self._natural_width(h)
        super().__init__(parent, app, width=w, height=h, command=command, bg=bg)

    def _natural_width(self, h):
        if not self.text:
            return h
        icon = self.icon_size + self.app.px(8) if self.icon_name else 0
        return self.font.measure(self.text) + icon + 2 * self.pad

    def set_accent(self, accent):
        self.accent = accent
        self.redraw()

    def set_text(self, text):
        self.text = text
        self.configure(width=self._natural_width(int(self.cget("height"))))
        self.redraw()

    def draw(self, w, h):
        c, bg = self.c, self.cget("bg")
        fill = outline = None
        if self.kind == "primary":
            col, on = self.accent or (c.text, c.bg)
            fill = mix(col, "#000000" if c.dark else "#FFFFFF", 0.12) if self.hover and not self.disabled else col
            if self.disabled:
                fill = mix(col, bg, 0.55)
            fg = on
        elif self.kind == "secondary":
            fill = c.hover(bg) if self.hover else bg
            outline = c.border_strong if self.hover else c.border
            fg = c.text
        elif self.kind == "ghost":
            fill = c.hover(bg) if self.hover else None
            fg = c.text if self.hover else (self.fg_color or c.muted)
        else:  # link
            fg = self.fg_color or (c.text if self.hover else c.muted)
            if self.fg_color and self.hover:
                fg = mix(self.fg_color, c.text, 0.3)
        if self.disabled and self.kind != "primary":
            fg = c.faint
        if fill or outline:
            self.P.round_rect(self, 0, 0, w, h, self.radius, fill, outline, bg)
        gap = self.px(8)
        tw = self.font.measure(self.text) if self.text else 0
        iw = self.icon_size if self.icon_name else 0
        total = tw + iw + (gap if tw and iw else 0)
        x = (w - total) / 2
        if self.icon_name:
            self.icon(self.icon_name, x + iw / 2, h / 2, self.icon_size, fg)
            x += iw + (gap if tw else 0)
        if self.text:
            self.create_text(x, h / 2, text=self.text, font=self.font, fill=fg, anchor="w")
        badge = getattr(self, "badge", None)
        if badge:  # petite pastille (ex. mise à jour disponible)
                   # small badge (e.g. update available)
            self.P.circle(self, w - self.px(10), self.px(10), self.px(8), badge, bg=fill or bg)

    def set_badge(self, color):
        self.badge = color
        self.redraw()


class IconButton(Button):
    def __init__(self, parent, app, icon, command=None, size=40, icon_size=18, bg=None, color=None):
        super().__init__(parent, app, icon=icon, command=command, kind="ghost", height=size, width=size,
                         icon_size=icon_size, radius=10, bg=bg, color=color)


class Pill(Widget):
    def __init__(self, parent, app, text, dot=None, command=None, selected=False, accent=None, dashed=False,
                 icon=None):
        self.text, self.dot, self.selected, self.accent = text, dot, selected, accent
        self.dashed, self.icon_name = dashed, icon
        self.font = app.fonts.small_semi if selected else app.fonts.small
        super().__init__(parent, app, width=self._width(app), height=app.px(34), command=command)

    def _width(self, app):
        lead = app.px(16) if (self.dot or self.icon_name) else 0
        return app.px(12) + lead + app.fonts.small_semi.measure(self.text) + app.px(14)

    def set_state(self, selected=None, accent=None, text=None):
        if selected is not None:
            self.selected = selected
        if accent is not None:
            self.accent = accent
        if text is not None:
            self.text = text
        self.configure(width=self._width(self.app))
        self.redraw()

    def draw(self, w, h):
        c, bg = self.c, self.cget("bg")
        r = h // 2
        if self.dashed and not self.selected:
            if self.hover:
                self.P.round_rect(self, 0, 0, w, h, r, c.hover(bg), c.hover(bg), bg)
            self.P.dashed_round_rect(self, 0, 0, w, h, r, c.border_strong if self.hover else c.border)
            fill, fg, dot = c.hover(bg) if self.hover else bg, c.muted, None
        elif self.selected:
            col, on = self.accent
            self.P.round_rect(self, 0, 0, w, h, r, col, col, bg)
            fill, fg, dot = col, on, (on if self.dot else None)
        else:
            fill = c.hover(bg) if self.hover else bg
            self.P.round_rect(self, 0, 0, w, h, r, fill, c.border_strong if self.hover else c.border, bg)
            fg, dot = c.text, self.dot
        x = self.px(12)
        if self.icon_name:
            self.icon(self.icon_name, x + self.px(5), h / 2, self.px(14), fg)
            x += self.px(16)
        elif dot:
            self.P.circle(self, x + self.px(4), h / 2, self.px(8), dot, bg=fill)
            x += self.px(16)
        font = self.app.fonts.small_semi if self.selected else self.app.fonts.small
        self.create_text(x, h / 2, text=self.text, font=font, fill=fg, anchor="w")


class Select(Widget):
    """Liste déroulante (ouvre un menu dessiné par l'application).

    Drop-down list (opens a menu drawn by the application)."""

    def __init__(self, parent, app, options, value, on_change, height=52, width=None, font=None, bg_key="field",
                 popup_width=None):
        self.options, self.value, self.on_change = options, value, on_change
        self.font = font or app.fonts.body
        self.bg_key = bg_key
        self.popup_width = popup_width
        w = app.px(width) if width else self._natural_width(app)
        super().__init__(parent, app, width=w, height=app.px(height), command=self.open)

    def _natural_width(self, app):
        widest = max([self.font.measure(lbl) for _, lbl in self.options] or [app.px(40)])
        return max(app.px(110), widest + app.px(14 + 38))

    def label(self):
        return next((lbl for v, lbl in self.options if v == self.value), self.value or "—")

    def set_options(self, options, value):
        self.options, self.value = options, value
        self.redraw()

    def open(self):
        if self.app.popover.is_open_for(self):
            self.app.popover.close()
            return
        items = [{"label": lbl, "value": v, "selected": v == self.value} for v, lbl in self.options]
        width = max(self.winfo_width(), self.app.px(self.popup_width or 160))
        self.app.popover.show(self, items, self._pick, width=width)

    def _pick(self, item):
        self.value = item["value"]
        self.redraw()
        if self.on_change:
            self.on_change(item["value"])

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        fbg = c[self.bg_key]
        self.P.round_rect(self, 0, 0, w, h, px(10) if h > px(44) else px(8), fbg,
                          c.border_strong if self.hover and not self.disabled else c.border, bg)
        fg = c.faint if self.disabled else c.text
        self.create_text(px(14), h / 2, text=fit_text(self.font, self.label(), w - px(46)), font=self.font, fill=fg,
                         anchor="w")
        self.icon("chevron_down", w - px(18), h / 2, px(11), c.muted)


class Segmented(Widget):
    def __init__(self, parent, app, options, value, on_change, height=36):
        self.options, self.value, self.on_change = options, value, on_change
        f = app.fonts.small_semi
        self.widths = [f.measure(lbl) + app.px(26) for _, lbl in options]
        w = sum(self.widths) + app.px(6) + app.px(2) * (len(options) - 1)
        super().__init__(parent, app, width=w, height=app.px(height), command=None, focusable=False)
        self.configure(cursor="hand2")

    def _spans(self):
        x = self.px(3)
        for i, wi in enumerate(self.widths):
            yield i, x, x + wi
            x += wi + self.px(2)

    def zone_at(self, x, y):
        """Index de l'option sous la souris (None entre deux options).

        Index of the option under the mouse (None between two options)."""
        return next((i for i, a, b in self._spans() if a <= x < b), None)

    def on_click(self, e):
        i = self.zone_at(e.x, e.y)
        if i is not None and self.options[i][0] != self.value:
            self.value = self.options[i][0]
            self.redraw()
            if self.on_change:
                self.on_change(self.value)

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        self.P.round_rect(self, 0, 0, w, h, px(9), c.raised, c.raised, bg)
        for i, a, b in self._spans():
            val, lbl = self.options[i]
            sel = val == self.value
            if sel:
                self.P.round_rect(self, a, px(3), b, h - px(3), px(7), c.seg_sel,
                                  c.border if not c.dark else c.seg_sel, c.raised)
            fg = c.text if sel or i == self.zone else c.muted
            font = self.app.fonts.small_semi if sel else self.app.fonts.small
            self.create_text((a + b) / 2, h / 2, text=lbl, font=font, fill=fg)


class Switch(Widget):
    def __init__(self, parent, app, value, on_change=None, accent=None):
        self.value, self.on_change, self.accent = bool(value), on_change, accent
        super().__init__(parent, app, width=app.px(40), height=app.px(22), command=self.toggle)

    def toggle(self):
        self.value = not self.value
        self.redraw()
        if self.on_change:
            self.on_change(self.value)

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        track = (self.accent[0] if self.accent else c.focus) if self.value else c.switch_off
        if self.hover:
            track = mix(track, c.text, 0.08)
        self.P.round_rect(self, 0, 0, w, h, h // 2, track, track, bg)
        d = h - px(6)
        x = w - px(3) - d if self.value else px(3)
        self.P.round_rect(self, x, px(3), x + d, px(3) + d, d // 2, c.knob, c.knob, track)
