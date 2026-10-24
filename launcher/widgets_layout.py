"""Mise en page : barre de défilement fine, zone défilante, notifications (Toast).

Layout: thin scrollbar, scrolling area, notifications (Toast)."""
import tkinter as tk

from .theme import readable_on
from .widgets_base import log


class ThinScrollbar(tk.Canvas):
    """Barre de défilement fine, cachée quand tout le contenu est visible.

    Thin scrollbar, hidden when all the content is visible."""

    def __init__(self, parent, app, target):
        super().__init__(parent, width=app.px(10), bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.app, self.target = app, target
        self.first, self.last = 0.0, 1.0
        self._drag = None
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self.draw()

    def draw(self):
        self.delete("all")
        if self.last - self.first >= 0.999:
            return
        h = self.winfo_height()
        px = self.app.px
        y0 = self.first * h
        y1 = max(y0 + px(24), self.last * h)
        self.app.painter.round_rect(self, px(3), y0 + px(2), px(8), y1 - px(2), px(3), self.app.c.scroll,
                                    self.app.c.scroll, self.cget("bg"))

    def _press(self, e):
        h = max(1, self.winfo_height())
        pos = e.y / h
        if not (self.first <= pos <= self.last):
            self.target.yview_moveto(max(0.0, pos - (self.last - self.first) / 2))
        self._drag = (e.y, self.first)

    def _move(self, e):
        if self._drag:
            h = max(1, self.winfo_height())
            y, first = self._drag
            self.target.yview_moveto(first + (e.y - y) / h)


class ScrollArea(tk.Frame):
    def __init__(self, parent, app, bg):
        super().__init__(parent, bg=bg)
        self.app = app
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ThinScrollbar(self, app, self.canvas)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self._region_job = None
        self.body.bind("<Configure>", self._body_changed)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _body_changed(self, e):
        # Une seule mise à jour de la zone de défilement par passage, pas une par ligne ajoutée
        # A single update of the scroll region per pass, not one per added row
        if self._region_job is None:
            self._region_job = self.after_idle(self._update_region)

    def _update_region(self):
        self._region_job = None
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def destroy(self):
        if self._region_job is not None:
            self.after_cancel(self._region_job)
            self._region_job = None
        super().destroy()

    def _bind_wheel(self, e):
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", lambda ev: self._scroll(-1))
        self.bind_all("<Button-5>", lambda ev: self._scroll(1))

    def _unbind_wheel(self, e):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)

    def _scroll(self, d):
        if self.bar.last - self.bar.first < 0.999:
            self.canvas.yview_scroll(d * 3, "units")


class Toast(tk.Canvas):
    """Notification non bloquante, en bas de la fenêtre.

    Non-blocking notification, at the bottom of the window."""

    def __init__(self, app, text, kind="ok", action=None, duration=2800, bottom=60):
        c, f, px = app.c, app.fonts, app.px
        self.app, self.action, self.kind = app, action, kind
        bg_ = c.text
        fg = c.bg
        tw = f.small_semi.measure(text)
        aw = f.small_semi.measure(action[0]) + px(20) if action else 0
        w = px(16) + px(18) + tw + aw + px(16)
        h = px(40)
        super().__init__(app, width=w, height=h, bg=c.bg, highlightthickness=0, bd=0)
        app.painter.round_rect(self, 0, 0, w, h, px(10), bg_, bg_, c.bg)
        dot = {"ok": c.ok, "warn": c.warn, "error": c.error}.get(kind, c.ok)
        if not c.dark:
            dot = {"ok": "#3DD68C", "warn": "#F5A524", "error": "#F87171"}.get(kind, "#3DD68C")
        app.painter.circle(self, px(16) + px(4), h / 2, px(8), dot, bg=bg_)
        self.create_text(px(34), h / 2, text=text, font=f.small_semi, fill=fg, anchor="w")
        if action:
            ax = px(34) + tw + px(16)
            color = readable_on(bg_, app.accent[0])
            self.create_text(ax, h / 2, text=action[0], font=f.small_semi, fill=color, anchor="w", tags="action")
            self.tag_bind("action", "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind("action", "<Leave>", lambda e: self.configure(cursor=""))
            self.tag_bind("action", "<ButtonRelease-1>", self._act)
        self.place(relx=0.5, rely=1.0, y=-bottom, anchor="s")
        tk.Misc.lift(self)
        self._job = self.after(duration, self.dismiss)

    def _act(self, e):
        cb = self.action[1]
        self.dismiss()
        cb()

    def dismiss(self):
        try:
            self.after_cancel(self._job)
        except Exception:
            log.debug("erreur ignorée", exc_info=True)
        try:
            self.destroy()
        except tk.TclError:
            pass
