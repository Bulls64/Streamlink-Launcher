"""Mode mini : barre flottante façon Spotlight, ouverte avec Ctrl+Alt+S ou depuis la zone de notification.

Vide, elle propose les favoris (ceux en direct d'abord) ; Entrée lance, Tab change de plateforme,
Échap ou un clic ailleurs la ferme. Elle est recréée à chaque ouverture (toujours au bon thème).

Mini mode: Spotlight-style floating bar, opened with Ctrl+Alt+S or from the notification area.

When empty, it offers the favorites (live ones first); Enter starts, Tab changes the platform,
Esc or a click elsewhere closes it. It is recreated at each opening (always with the right theme)."""
import time
import tkinter as tk

from . import inputs
from .theme import apply_window_chrome
from .widgets import Button, Field, Pill, SuggestionList
from .wintray import bring_to_front

WIDTH = 580
MAX_ITEMS = 5


class MiniBar:
    def __init__(self, app):
        self.app = app
        self.win = None
        self.pid = None
        self.message = None
        self._suppress = False
        self.query = tk.StringVar(master=app)
        self.query.trace_add("write", self._on_query)

    @property
    def visible(self):
        return self.win is not None

    @property
    def platform(self):
        return self.app.platform_by_id(self.pid) or self.app.platforms[0]

    def has_focus(self):
        try:
            focus = self.win.focus_get() if self.win is not None else None
        except (KeyError, tk.TclError):
            focus = None
        return focus is not None and str(focus).startswith(str(self.win))

    def toggle(self):
        """Raccourci : ouvre ; s'il est déjà ouvert mais sans le focus, le ramène ; sinon ferme.

        Shortcut: opens; if it is already open but without focus, brings it back; otherwise closes."""
        if not self.visible:
            self.show()
        elif self.has_focus():
            self.hide()
        else:
            self._focus()

    # --- ouverture / fermeture
    # --- opening / closing
    def show(self):
        if self.win is not None:
            self._focus()
            return
        app, c, px, t = self.app, self.app.c, self.app.px, self.app.t
        self.pid = app.target[1] if app.target[0] == "platform" else app.platforms[0]["id"]
        self.message = None
        offer = app.clipboard_offer()  # lien de stream copié : la barre s'ouvre déjà remplie
                                       # stream link copied: the bar opens already filled in
        if offer:
            self.pid = offer[0]
            self.message = (t("mini_clip_hint"), "info")
        p = self.platform
        accent = (p["color"], p["text_color"])

        win = self.win = tk.Toplevel(app)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=c.border_strong)
        inner = tk.Frame(win, bg=c.popover)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        bar = tk.Frame(inner, bg=c.popover)
        bar.pack(fill="x", padx=(px(4), px(8)), pady=px(6))
        self.launch_btn = Button(bar, app, icon="play_fill", command=self.launch, kind="primary", height=40,
                                 width=40, accent=accent, icon_size=14, radius=10)
        self.launch_btn.pack(side="right")
        self.quality_lbl = tk.Label(bar, text=app.quality_for(p), font=app.fonts.tiny, bg=c.popover, fg=c.faint)
        self.quality_lbl.pack(side="right", padx=(px(10), px(12)))
        self.chip = Pill(bar, app, app.platform_name(p), dot=p["color"], command=self.next_platform, selected=True,
                         accent=accent)
        self.chip.pack(side="right")
        self.field = Field(bar, app, self.query, placeholder=app.placeholder_for(p), icon="search", height=44,
                           font=app.fonts.field, bg_key="popover", plain=True, accent=accent)
        self.field.pack(side="left", fill="x", expand=True)
        self.field.set_disabled(p["input"] == "none")

        self.list = SuggestionList(inner, app, self._pick, max_rows=MAX_ITEMS)
        self.list.pack(fill="x", padx=px(2))
        self.hint = tk.Label(inner, text=t("mini_hint"), font=app.fonts.tiny, bg=c.popover, fg=c.faint, anchor="w")
        self.hint.pack(fill="x", padx=px(18), pady=(px(2), px(10)))

        e = self.field.entry
        for seq in ("<Return>", "<KP_Enter>"):
            e.bind(seq, lambda ev: self._enter())
            win.bind(seq, lambda ev: self._enter())
        win.bind("<Escape>", lambda ev: self.hide())
        win.bind("<Down>", lambda ev: self._move(1))
        win.bind("<Up>", lambda ev: self._move(-1))
        e.bind("<Tab>", lambda ev: self.next_platform(1))
        e.bind("<Shift-Tab>", lambda ev: self.next_platform(-1))
        try:
            # Maj+Tab sous Linux (X11). Ce nom de touche n'existe pas sous Windows : sans ce try,
            # l'erreur interrompait l'ouverture et la barre mini ne s'affichait jamais.
            # Shift+Tab on Linux (X11). This key name does not exist on Windows: without this try,
            # the error interrupted the opening and the mini bar never showed up.
            e.bind("<ISO_Left_Tab>", lambda ev: self.next_platform(-1))
        except tk.TclError:
            pass
        win.bind("<FocusIn>", lambda ev: setattr(self, "_had_focus", True))
        win.bind("<FocusOut>", lambda ev: win.after(150, self._check_focus))
        win.bind("<Button-1>", lambda ev: self._focus(), add="+")
        self._had_focus = False
        self._shown_at = time.monotonic()

        if offer:
            self._set_query(offer[1])
        self.refresh()
        win.deiconify()
        apply_window_chrome(win, c.dark, border=accent[0])
        self._focus()
        if offer:
            self.field.entry.select_range(0, "end")  # taper remplace le lien proposé
                                                     # typing replaces the offered link
        win.after(80, self._focus)  # 2e essai : Windows applique parfois le premier plan avec un léger retard
                                    # 2nd attempt: Windows sometimes applies the foreground with a slight delay

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None
        self._set_query("")

    def _set_query(self, text):
        """Change le texte sans déclencher la détection de plateforme ni les suggestions.

        Changes the text without triggering the platform detection or the suggestions."""
        self._suppress = True
        self.query.set(text)
        self._suppress = False

    def _focus(self):
        if self.win is None:
            return
        try:
            self.win.lift()
            bring_to_front(self.win)
            self.win.focus_force()
            if not self.field.disabled:
                self.field.entry.focus_set()
        except tk.TclError:
            pass

    def _check_focus(self):
        """Ferme la barre quand on clique ailleurs, mais jamais si elle n'a pas encore eu le focus
        (sinon elle disparaîtrait aussitôt ouverte quand Windows refuse le premier plan).

        Closes the bar on a click elsewhere, but never if it has not had the focus yet
        (otherwise it would disappear as soon as it opened when Windows refuses the foreground)."""
        if self.win is None or not self._had_focus or time.monotonic() - self._shown_at < 0.6:
            return
        if not self.has_focus():
            self.hide()

    def _place(self):
        win, px = self.win, self.app.px
        win.update_idletasks()
        w = px(WIDTH)
        h = win.winfo_reqheight()
        x = (win.winfo_screenwidth() - w) // 2
        y = int(win.winfo_screenheight() * 0.22)
        win.geometry(f"{w}x{h}+{x}+{y}")

    # --- plateforme
    # --- platform
    def set_platform(self, pid):
        if self.win is None or not self.app.platform_by_id(pid):
            return
        self.pid = pid
        p = self.platform
        accent = (p["color"], p["text_color"])
        self.chip.set_state(text=self.app.platform_name(p), accent=accent)
        self.launch_btn.set_accent(accent)
        self.field.set_accent(accent)
        self.field.set_placeholder(self.app.placeholder_for(p))
        self.field.set_disabled(p["input"] == "none")
        if p["input"] == "none":
            self.win.focus_set()
        else:
            self.field.entry.focus_set()
        self.quality_lbl.configure(text=self.app.quality_for(p))
        apply_window_chrome(self.win, self.app.c.dark, border=accent[0])

    def next_platform(self, step=1):
        ids = [p["id"] for p in self.app.platforms]
        i = ids.index(self.pid) if self.pid in ids else 0
        self.set_platform(ids[(i + step) % len(ids)])
        return "break"

    # --- contenu
    # --- content
    def _on_query(self, *args):
        if self._suppress or self.win is None:
            return
        text = self.query.get()
        detected = inputs.detect_platform_in_text(self.app.platforms, text) if text else None
        if detected and detected != self.pid:
            self.set_platform(detected)
        self.message = None
        self.refresh()

    def items(self):
        app = self.app
        text = self.query.get().strip()
        if text:
            pairs = app.store.suggestions(text, limit=MAX_ITEMS)
        else:
            favs = sorted(app.store.favorites, key=lambda e: not (app.live_info(e) or {}).get("live"))
            pairs = [("favorite", f) for f in favs[:MAX_ITEMS]]
        return [app.suggestion_item(source, e, text, show_live=True) for source, e in pairs]

    def refresh(self):
        if self.win is None:
            return
        c = self.app.c
        self.list.set_items(self.items())
        if self.message:
            text, kind = self.message
            self.hint.configure(text=text, fg={"error": c.error, "info": c.muted}.get(kind, c.warn))
        else:
            self.hint.configure(text=self.app.t("mini_hint"), fg=c.faint)
        self._place()

    def show_message(self, text, kind="warn", action=None, **kwargs):
        """Même signature que App.toast : les erreurs de lancement s'affichent dans la barre.

        Same signature as App.toast: launch errors are shown in the bar."""
        self.message = (text, kind)
        self.refresh()

    # --- actions
    # --- actions
    def _move(self, d):
        self.list.move(d)
        return "break"

    def _enter(self):
        item = self.list.current()
        if item:
            self._pick(item)
        else:
            self.launch()
        return "break"

    def _pick(self, item):
        if self.app.launch_entry(item["value"], report=self.show_message):
            self.hide()

    def launch(self):
        if self.app.launch_platform(self.platform, self.query.get(), report=self.show_message):
            self.hide()
