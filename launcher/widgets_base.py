"""Base des composants dessinés : classe Widget (taille, survol, clic, clavier, focus) et redessins groupés.

Base of the drawn components: the Widget class (size, hover, click, keyboard, focus) and grouped redraws."""
import logging
import tkinter as tk

from .gfx import draw_icon

log = logging.getLogger("streamlink_launcher")


def _schedule_redraw(widget):
    """Regroupe les redessins dus aux changements de taille : un seul passage, à la fin du calcul de la mise
    en page. Sans cela, chaque composant était dessiné une fois à sa taille demandée puis une fois à sa taille
    réelle (deux fois plus de travail à chaque ouverture de panneau).

    Groups the redraws caused by size changes: a single pass, at the end of the layout
    computation. Without it, each component was drawn once at its requested size, then once at its real
    size (twice as much work each time a panel opens)."""
    app = widget.app
    pending = app.__dict__.setdefault("_redraw_pending", {})
    pending[str(widget)] = widget
    if not app.__dict__.get("_redraw_job"):
        app._redraw_job = app.after_idle(_flush_redraws, app)


def _flush_redraws(app):
    app._redraw_job = None
    pending, app._redraw_pending = app._redraw_pending, {}
    for w in pending.values():
        try:
            if w.winfo_exists() and w._size() != w._drawn:
                w.redraw()
        except tk.TclError:
            pass


class Widget(tk.Canvas):
    """Base : redessine à la taille réelle, gère survol, clic, clavier et focus.

    Zones : un composant à plusieurs parties cliquables redéfinit zone_at(x, y) ; la zone survolée est
    alors suivie dans self.zone (et redessinée quand elle change). zone_cursor : main uniquement
    au-dessus d'une zone, flèche ailleurs.

    Base: redraws at the real size, handles hover, click, keyboard and focus.

    Zones: a component with several clickable parts redefines zone_at(x, y); the hovered zone is
    then tracked in self.zone (and redrawn when it changes). zone_cursor: hand only
    over a zone, arrow elsewhere.
    """

    zone_cursor = False

    def __init__(self, parent, app, width=1, height=1, command=None, bg=None, focusable=None):
        self.app = app
        self.command = command
        self.zone = None
        self.hover = False
        self.focused = False
        self.disabled = False
        bg = bg or parent.cget("bg")
        focus = (command is not None) if focusable is None else focusable
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0,
                         takefocus=1 if focus else 0, cursor="hand2" if command else "")
        self._drawn = None  # taille du dernier dessin
                            # size of the last drawing
        self.bind("<Configure>", self._on_configure)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Motion>", self._motion)
        if focus:
            self.bind("<KeyPress-Return>", lambda e: self.activate())
            self.bind("<KeyPress-space>", lambda e: self.activate())
            self.bind("<FocusIn>", lambda e: self._set_focus(True))
            self.bind("<FocusOut>", lambda e: self._set_focus(False))

    # --- état
    # --- state
    def _enter(self, e):
        self.hover = True
        self.redraw()

    def _leave(self, e):
        self.hover = False
        self._set_zone(None)
        self.redraw()

    def _set_focus(self, value):
        self.focused = value
        self.redraw()

    def zone_at(self, x, y):
        return None

    def _set_zone(self, zone):
        if zone == self.zone:
            return False
        self.zone = zone
        if self.zone_cursor:
            self.configure(cursor="hand2" if zone is not None else "")
        return True

    def _motion(self, e):
        if self._set_zone(self.zone_at(e.x, e.y)):
            self.redraw()

    def _release(self, e):
        if self.disabled:
            return
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.on_click(e)

    def on_click(self, e):
        self.activate()

    def activate(self):
        if self.command and not self.disabled:
            self.command()

    def set_disabled(self, value):
        self.disabled = value
        self.configure(cursor="" if value or not self.command else "hand2")
        self.redraw()

    # --- dessin
    # --- drawing
    @property
    def c(self):
        return self.app.c

    @property
    def P(self):
        return self.app.painter

    @property
    def px(self):
        return self.app.px

    def icon(self, name, x, y, size, color):
        draw_icon(self, self.app.fonts, name, x, y, size, color)

    def _on_configure(self, e):
        if (e.width, e.height) != self._drawn:
            _schedule_redraw(self)

    def _size(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w = int(self.cget("width"))
        if h <= 1:
            h = int(self.cget("height"))
        return w, h

    def redraw(self):
        try:
            w, h = self._size()
        except tk.TclError:
            return
        self._drawn = (w, h)
        self.delete("all")
        self.draw(w, h)
        if self.focused:
            self.create_rectangle(1, 1, w - 1, h - 1, outline=self.c.focus, width=2)

    def draw(self, w, h):
        pass


def _is_inside(widget, container):
    try:
        while widget is not None:
            if widget is container:
                return True
            widget = widget.master
    except AttributeError:
        pass
    return False
