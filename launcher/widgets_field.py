"""Champ de saisie, menus contextuels (Popover) et liste de suggestions.

Input field, context menus (Popover) and suggestion list."""
import tkinter as tk

from .gfx import draw_icon
from .theme import accent_ring, fit_text, mix
from .widgets_base import _is_inside


class Field(tk.Frame):
    """Champ arrondi avec icône, raccourci clavier, badge, bouton d'action et texte indicatif.

    Rounded field with an icon, keyboard shortcut, badge, action button and hint text."""

    def __init__(self, parent, app, variable, placeholder="", icon=None, kbd=None, ring=False, mono=False,
                 height=40, font=None, radius=8, accent=None, action_icon=None, action_command=None,
                 badge=None, bg_key="field", plain=False):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.plain = plain  # sans cadre (barre du mode mini)
                            # frameless (mini mode bar)
        self.app, self.var = app, variable
        self.icon_name, self.kbd, self.ring, self.radius = icon, kbd, ring, app.px(radius)
        self.accent = accent
        self.action_icon, self.action_command, self.badge = action_icon, action_command, badge
        self.bg_key = bg_key
        self.disabled = False
        c = app.c
        self.font = font or (app.fonts.mono_field if mono else app.fonts.body)
        fbg = c[bg_key]
        # Petite largeur demandée : le champ s'étire, sans écraser ses voisins
        # Small requested width: the field stretches, without crushing its neighbors
        self.cv = tk.Canvas(self, width=app.px(120), height=app.px(height), bg=bg, highlightthickness=0, bd=0,
                            cursor="xterm")
        self.cv.pack(fill="x")
        self.entry = tk.Entry(self.cv, textvariable=variable, relief="flat", bd=0, highlightthickness=0, bg=fbg,
                              fg=c.text, insertbackground=c.text, font=self.font, disabledbackground=fbg,
                              disabledforeground=c.faint, selectbackground=mix(fbg, accent[0] if accent else c.muted, 0.45),
                              selectforeground=c.text, insertwidth=max(1, app.px(1.5)))
        self.ph = tk.Label(self.cv, text=placeholder, bg=fbg, fg=c.faint, font=self.font, anchor="w", bd=0,
                           cursor="xterm", padx=0, pady=0)
        self.ph.bind("<Button-1>", lambda e: self.focus())
        self._win = self._phwin = None
        self._action_x = None
        self._trace = variable.trace_add("write", self._sync)
        self.bind("<Destroy>", self._cleanup)
        self.entry.bind("<FocusIn>", lambda e: self.redraw(), add="+")
        self.entry.bind("<FocusOut>", lambda e: self.redraw(), add="+")
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self.cv.bind("<ButtonRelease-1>", self._click)
        self.cv.bind("<Motion>", self._motion)

    def _cleanup(self, e):
        if e.widget is self and self._trace:
            try:
                self.var.trace_remove("write", self._trace)
            except tk.TclError:
                pass
            self._trace = None

    def focus(self):
        if not self.disabled:
            self.entry.focus_set()
            self.entry.icursor("end")

    def has_focus(self):
        try:
            return self.app.focus_get() is self.entry
        except (KeyError, tk.TclError):
            return False

    def set_accent(self, accent):
        self.accent = accent
        self.entry.configure(selectbackground=mix(self.app.c[self.bg_key], accent[0], 0.45))
        self.redraw()

    def set_placeholder(self, text):
        self.ph.configure(text=text)

    def set_disabled(self, value):
        self.disabled = value
        self.entry.configure(state="disabled" if value else "normal")
        self.cv.configure(cursor="" if value else "xterm")
        self.redraw()

    def _action_zone(self, x):
        return self.action_icon and self._action_x and self._action_x[0] <= x <= self._action_x[1]

    def _motion(self, e):
        self.cv.configure(cursor="hand2" if self._action_zone(e.x) else ("" if self.disabled else "xterm"))

    def _click(self, e):
        if self._action_zone(e.x):
            if self.action_command:
                self.action_command()
        else:
            self.focus()

    def _sync(self, *args):
        """Appelé quand le texte change : texte indicatif et badge.

        Called when the text changes: hint text and badge."""
        if self.badge:
            self.redraw()
        else:
            self._update_placeholder()

    def _update_placeholder(self):
        if self._phwin is None:
            return
        try:
            self.cv.itemconfigure(self._phwin, state="hidden" if self.var.get() else "normal")
        except tk.TclError:
            pass

    def redraw(self):
        app, c, px, P, cv = self.app, self.app.c, self.app.px, self.app.painter, self.cv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("deco")
        bg, fbg = self.cget("bg"), c[self.bg_key]
        focused = self.has_focus() and not self.disabled
        inset = px(3) if self.ring else 0
        corner_bg = bg
        accent = self.accent[0] if self.accent else c.focus
        if self.plain:
            cv.create_rectangle(0, 0, w, h, fill=fbg, width=0, tags="deco")
        else:
            if self.ring and focused:
                ring = accent_ring(accent, bg)
                P.round_rect(cv, 0, 0, w, h, self.radius + inset, ring, ring, bg, tags="deco")
                corner_bg = ring
            outline = accent if focused else c.border
            P.round_rect(cv, inset, inset, w - inset, h - inset, self.radius, fbg, outline, corner_bg, tags="deco")
        x = inset + px(14)
        if self.icon_name:
            draw_icon(cv, app.fonts, self.icon_name, x + px(8), h / 2, px(17), c.muted, tags="deco")
            x += px(28)
        right = w - inset - px(12)
        self._action_x = None
        if self.kbd:
            tw = app.fonts.tiny.measure(self.kbd)
            kx0 = right - tw - px(14)
            P.round_rect(cv, kx0, h / 2 - px(11), right, h / 2 + px(11), px(6), fbg, c.border, fbg, tags="deco")
            cv.create_text((kx0 + right) / 2, h / 2, text=self.kbd, font=app.fonts.tiny, fill=c.faint, tags="deco")
            right = kx0 - px(10)
        if self.action_icon:
            ax = right - px(10)
            draw_icon(cv, app.fonts, self.action_icon, ax, h / 2, px(15), c.muted, tags="deco")
            self._action_x = (ax - px(16), ax + px(16))
            right = ax - px(20)
        if self.badge:
            info = self.badge()
            if info:
                text, color, icon = (tuple(info) + ("check",))[:3]
                tw = app.fonts.tiny.measure(text)
                cv.create_text(right, h / 2, text=text, font=app.fonts.tiny, fill=color, anchor="e", tags="deco")
                draw_icon(cv, app.fonts, icon, right - tw - px(9), h / 2, px(12), color, tags="deco")
                right -= tw + px(26)
        eh = self.font.metrics("linespace") + px(2)
        width = max(px(20), right - x)
        if self._win is None:
            self._win = cv.create_window(x, h / 2, anchor="w", window=self.entry, width=width, height=eh)
            self._phwin = cv.create_window(x + px(2), h / 2, anchor="w", window=self.ph, width=width - px(2),
                                           height=eh)
        else:
            cv.coords(self._win, x, h / 2)
            cv.itemconfigure(self._win, width=width)
            cv.coords(self._phwin, x + px(2), h / 2)
            cv.itemconfigure(self._phwin, width=width - px(2))
        cv.tag_lower("deco")
        self._update_placeholder()


class Popover:
    """Petit menu flottant (liste de choix, suggestions). Un seul ouvert à la fois.

    Small floating menu (list of choices, suggestions). Only one open at a time."""

    ROWS = 8

    def __init__(self, app):
        self.app = app
        self.cv = None
        self.anchor = None
        self.items = []
        self.hi = None
        self.offset = 0
        self.on_pick = None

    @property
    def is_open(self):
        return self.cv is not None

    def is_open_for(self, anchor):
        return self.cv is not None and self.anchor is anchor

    def show(self, anchor, items, on_pick, width=None, highlight=None):
        self.close()
        if not items:
            return
        app, px = self.app, self.app.px
        self.anchor, self.items, self.on_pick, self.hi, self.offset = anchor, items, on_pick, highlight, 0
        self.row_h, self.pad = px(40), px(6)
        n = min(len(items), self.ROWS)
        h = n * self.row_h + 2 * self.pad
        w = int(width or anchor.winfo_width())
        rx, ry = app.winfo_rootx(), app.winfo_rooty()
        x = anchor.winfo_rootx() - rx
        y = anchor.winfo_rooty() - ry + anchor.winfo_height() + px(6)
        if y + h > app.winfo_height() - px(8):
            y = max(px(8), anchor.winfo_rooty() - ry - h - px(6))
        x = max(px(8), min(x, app.winfo_width() - w - px(8)))
        self.cv = tk.Canvas(app, width=w, height=h, bg=app.c.bg, highlightthickness=0, bd=0, cursor="hand2")
        self.cv.place(x=x, y=y)
        tk.Misc.lift(self.cv)  # Canvas.lift() agit sur les éléments dessinés, pas sur le widget
                               # Canvas.lift() acts on the drawn items, not on the widget
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._click)
        self.cv.bind("<MouseWheel>", self._wheel)
        self.cv.bind("<Button-4>", lambda e: self._scroll(-1))
        self.cv.bind("<Button-5>", lambda e: self._scroll(1))
        self.draw()

    def close(self):
        if self.cv is not None:
            try:
                self.cv.destroy()
            except tk.TclError:
                pass
        self.cv = None
        self.anchor = None

    def contains(self, widget):
        return self.cv is not None and _is_inside(widget, self.cv)

    def _index_at(self, y):
        i = int((y - self.pad) // self.row_h)
        k = i + self.offset
        return k if 0 <= i < self.ROWS and 0 <= k < len(self.items) else None

    def _motion(self, e):
        i = self._index_at(e.y)
        if i != self.hi:
            self.hi = i
            self.draw()

    def _click(self, e):
        i = self._index_at(e.y)
        if i is not None:
            self.pick(i)

    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)

    def _scroll(self, d):
        self.offset = max(0, min(self.offset + d, len(self.items) - self.ROWS))
        self.draw()

    def move(self, d):
        if not self.items:
            return
        self.hi = 0 if self.hi is None else max(0, min(len(self.items) - 1, self.hi + d))
        if self.hi < self.offset:
            self.offset = self.hi
        elif self.hi >= self.offset + self.ROWS:
            self.offset = self.hi - self.ROWS + 1
        self.draw()

    def pick(self, index=None):
        index = self.hi if index is None else index
        if index is None or not (0 <= index < len(self.items)):
            return False
        item, cb = self.items[index], self.on_pick
        self.close()
        if cb:
            cb(item)
        return True

    def draw(self):
        if self.cv is None:
            return
        app, c, px, P, cv = self.app, self.app.c, self.app.px, self.app.painter, self.cv
        cv.delete("all")
        w, h = int(cv.cget("width")), int(cv.cget("height"))
        P.round_rect(cv, 0, 0, w, h, px(10), c.popover, c.border_strong, c.bg)
        draw_rows(cv, app, self.items, self.hi, self.offset, self.ROWS, self.pad, self.row_h, w, c.popover)


def draw_rows(cv, app, items, hi, offset, max_rows, pad, row_h, w, bg):
    """Lignes de choix / suggestions (partagé par le menu flottant et le mode mini).

    Choice / suggestion rows (shared by the floating menu and the mini mode)."""
    c, px, P, f = app.c, app.px, app.painter, app.fonts
    hover_bg = mix(bg, "#808080", 0.16)
    for row in range(min(max_rows, len(items) - offset)):
        k = row + offset
        item = items[k]
        y0 = pad + row * row_h
        yc = y0 + row_h / 2
        row_bg = hover_bg if k == hi else bg
        if k == hi:
            P.round_rect(cv, pad, y0, w - pad, y0 + row_h, px(7), hover_bg, hover_bg, bg)
        x = pad + px(12)
        if item.get("icon"):
            draw_icon(cv, f, item["icon"], x + px(7), yc, px(14), item.get("icon_color") or c.muted)
            x += px(26)
        right = w - pad - px(12)
        if item.get("selected"):
            draw_icon(cv, f, "check", right - px(6), yc, px(13), c.text)
            right -= px(24)
        if item.get("right"):
            rt = item["right"]
            cv.create_text(right, yc, text=rt, font=f.tiny, fill=item.get("right_color") or c.muted, anchor="e")
            if item.get("right_dot"):
                P.circle(cv, right - f.tiny.measure(rt) - px(9), yc, px(7), item["right_dot"], bg=row_bg)
                right -= px(14)
            right -= f.tiny.measure(rt) + px(12)
        label = item["label"]
        bold = item.get("bold", 0)
        avail = right - x
        if bold and label.lower().startswith(item.get("query", "").lower()):
            head, tail = label[:bold], label[bold:]
            cv.create_text(x, yc, text=head, font=f.body_semi, fill=c.text, anchor="w")
            cv.create_text(x + f.body_semi.measure(head), yc,
                           text=fit_text(f.body, tail, avail - f.body_semi.measure(head)), font=f.body,
                           fill=c.text, anchor="w")
        else:
            cv.create_text(x, yc, text=fit_text(f.body, label, avail), font=f.body, fill=c.text, anchor="w")


class SuggestionList(tk.Canvas):
    """Liste de suggestions intégrée (mode mini) : survol, clic, navigation clavier.

    Built-in suggestion list (mini mode): hover, click, keyboard navigation."""

    def __init__(self, parent, app, on_pick, max_rows=6):
        super().__init__(parent, height=1, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        self.app, self.on_pick, self.max_rows = app, on_pick, max_rows
        self.items, self.hi = [], None
        self.row_h, self.pad = app.px(44), app.px(6)
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._click)

    def set_items(self, items, highlight=None):
        self.items = items[:self.max_rows]
        self.hi = highlight if self.items else None
        n = len(self.items)
        self.configure(height=n * self.row_h + 2 * self.pad if n else 1)
        self.draw()

    def _index_at(self, y):
        i = int((y - self.pad) // self.row_h)
        return i if 0 <= i < len(self.items) else None

    def _motion(self, e):
        i = self._index_at(e.y)
        if i is not None and i != self.hi:
            self.hi = i
            self.draw()

    def _click(self, e):
        i = self._index_at(e.y)
        if i is not None:
            self.on_pick(self.items[i])

    def move(self, d):
        if self.items:
            self.hi = 0 if self.hi is None else max(0, min(len(self.items) - 1, self.hi + d))
            self.draw()

    def current(self):
        return self.items[self.hi] if self.hi is not None and self.hi < len(self.items) else None

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1 or not self.items:
            return
        draw_rows(self, self.app, self.items, self.hi, 0, self.max_rows, self.pad, self.row_h, w, self.cget("bg"))
