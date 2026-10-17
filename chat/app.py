"""Streamlink Chat : les chats Twitch, Kick et Steam TV dans une fenêtre, avec le style du lanceur."""
import base64
import hashlib
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from collections import deque

from launcher import core
from launcher.gfx import Painter
from launcher.theme import (
    Fonts,
    apply_window_chrome,
    enable_dpi_awareness,
    mix,
    palette,
    resolve_theme,
    set_app_id,
)
from launcher.widgets import (
    Button,
    Field,
    IconButton,
    Popover,
    ScrollArea,
    Select,
    Switch,
    ThinScrollbar,
    Toast,
    Widget,
)

from . import auth, badges, config, emotes, instance
from .common import default_color, mentions, readable_color
from .kick import KickManager
from .steam import SteamManager
from .twitch import TwitchConnection

log = logging.getLogger("streamlink_launcher")

GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class Tab:
    def __init__(self, platform, channel):
        self.platform, self.channel = platform, channel
        self.title = channel
        self.status, self.detail = "connecting", ""
        self.unread, self.mentioned = 0, False
        self.info = {}
        self.view = None
        self.history = deque(maxlen=1000)
        self.chatters = {}          # pseudo en minuscules -> pseudo affiché (complétion avec Tab)

    @property
    def key(self):
        return (self.platform, self.channel)


# =====================================================
# Composants
# =====================================================
class ChannelTab(Widget):
    """Onglet d'un chat : pastille de plateforme, nom, compteur de messages non lus, croix au survol."""

    zone_cursor = True

    def __init__(self, parent, app, tab, selected, on_select, on_close, on_menu):
        self.tab, self.selected = tab, selected
        self.on_select, self.on_close = on_select, on_close
        super().__init__(parent, app, width=self._width(app), height=app.px(34), command=on_select)
        self.bind("<ButtonRelease-3>", lambda e: on_menu(self))
        self.bind("<ButtonRelease-2>", lambda e: on_close())

    def _badge_text(self):
        t = self.tab
        if self.selected or not t.unread:
            return ""
        return "99+" if t.unread > 99 else str(t.unread)

    def _width(self, app):
        f = app.fonts
        w = app.px(12) + app.px(16) + f.small_semi.measure(self.tab.title) + app.px(10) + app.px(22)
        badge = self._badge_text()
        if badge:
            w += f.tiny.measure(badge) + app.px(14)
        return w

    def refresh(self, selected=None):
        if selected is not None:
            self.selected = selected
        self.configure(width=self._width(self.app))
        self.redraw()

    def zone_at(self, x, y):
        w = self.winfo_width()
        return "close" if x >= w - self.px(26) else "tab"

    def on_click(self, e):
        if self.zone_at(e.x, e.y) == "close":
            self.on_close()
        else:
            self.on_select()

    def draw(self, w, h):
        c, bg, px, t = self.c, self.cget("bg"), self.px, self.tab
        color, on = config.PLATFORMS[t.platform][1:]
        r = h // 2
        if self.selected:
            self.P.round_rect(self, 0, 0, w, h, r, color, color, bg)
            fill, fg, dot = color, on, on
        else:
            fill = c.hover(bg) if self.hover else bg
            border = c.warn if t.mentioned else (c.border_strong if self.hover else c.border)
            self.P.round_rect(self, 0, 0, w, h, r, fill, border, bg)
            fg, dot = (c.text if t.unread or self.hover else c.muted), color
            if t.status in ("error", "reconnecting"):
                dot = c.error if t.status == "error" else c.warn
        x = px(12)
        self.P.circle(self, x + px(4), h / 2, px(8), dot, bg=fill)
        x += px(16)
        font = self.app.fonts.small_semi
        self.create_text(x, h / 2, text=t.title, font=font, fill=fg, anchor="w")
        x += font.measure(t.title) + px(8)
        badge = self._badge_text()
        if badge:
            bw = self.app.fonts.tiny.measure(badge) + px(10)
            bc = c.warn if t.mentioned else mix(fill, c.text, 0.18)
            self.P.round_rect(self, x, h / 2 - px(9), x + bw, h / 2 + px(9), px(9), bc, bc, fill)
            self.create_text(x + bw / 2, h / 2, text=badge, font=self.app.fonts.tiny,
                             fill="#000000" if t.mentioned else c.text)
        close_color = fg if (self.hover and self.zone == "close") else mix(fg, fill, 0.45)
        self.icon("close", w - px(15), h / 2, px(10), close_color)


class ChatView:
    """Un tk.Text par onglet : lignes de messages, badges, emotes en images, liens, mentions."""

    def __init__(self, app, parent, tab):
        self.app, self.tab = app, tab
        c, px = app.c, app.px
        bg = c.surface
        self.frame = tk.Frame(parent, bg=bg)
        self.text = tk.Text(self.frame, bg=bg, fg=c.text, font=app.chat_font, wrap="word", bd=0, highlightthickness=0,
                            padx=px(14), pady=px(10), spacing1=px(3), spacing3=px(3), cursor="arrow",
                            insertwidth=0, takefocus=0, selectbackground=mix(bg, app.accent[0], 0.40),
                            inactiveselectbackground=mix(bg, app.accent[0], 0.30), selectforeground=c.text,
                            exportselection=True, undo=False, height=1, width=1)
        self.bar = ThinScrollbar(self.frame, app, self.text)
        self.text.configure(yscrollcommand=self._yscroll)
        self.bar.pack(side="right", fill="y", padx=(0, px(3)), pady=px(6))
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Key>", lambda e: None if (e.state & 0x4 and e.keysym.lower() in ("c", "a")) else "break")
        self.text.bind("<Button-3>", self._context)
        self.text.bind("<Button-1>", lambda e: self.text.focus_set(), add="+")
        self.first_n = 1          # numéro du message affiché sur la ligne 1
        self.next_n = 1
        self.lines = deque()      # messages affichés, dans l'ordre des lignes
        self.by_id = {}
        self.by_user = {}
        self.at_bottom = True
        self._setup_tags()

    # --- apparence
    def _setup_tags(self):
        app, c = self.app, self.app.c
        t, bg = self.text, c.surface
        t.tag_configure("time", foreground=c.faint, font=app.chat_small)
        t.tag_configure("name", font=app.chat_bold)
        t.tag_configure("mention", font=app.chat_bold)
        t.tag_configure("link", foreground="#8AB4F8" if c.dark else "#1A56DB", underline=True)
        t.tag_configure("reply", foreground=c.faint, font=app.chat_small)
        t.tag_configure("notice", foreground=c.muted, font=app.chat_small)
        t.tag_configure("event", background=mix(bg, app.accent[0], 0.12), foreground=c.text)
        t.tag_configure("mention_line", background=mix(bg, c.warn, 0.16))
        t.tag_configure("first_line", background=mix(bg, c.ok, 0.10))
        t.tag_configure("highlight_line", background=mix(bg, "#9146FF", 0.16))
        t.tag_configure("own_line", background=mix(bg, c.text, 0.035))
        t.tag_configure("deleted", overstrike=True, foreground=c.faint)
        t.tag_bind("badge", "<Enter>", self._badge_enter)
        t.tag_bind("badge", "<Leave>", lambda e: self.app.hide_tip())
        t.tag_configure("emote_text", foreground=c.muted)
        t.tag_raise("deleted")
        t.tag_raise("sel")
        for tag in ("name", "mention"):
            t.tag_bind(tag, "<Enter>", lambda e: t.configure(cursor="hand2"))
            t.tag_bind(tag, "<Leave>", lambda e: t.configure(cursor="arrow"))
            t.tag_bind(tag, "<ButtonRelease-1>", self._user_click)
        t.tag_bind("link", "<Enter>", lambda e: t.configure(cursor="hand2"))
        t.tag_bind("link", "<Leave>", lambda e: t.configure(cursor="arrow"))
        t.tag_bind("link", "<ButtonRelease-1>", self._link_click)

    def color_tag(self, color):
        tag = "c" + color[1:]
        if tag not in self.text.tag_names():
            self.text.tag_configure(tag, foreground=color)
            self.text.tag_lower(tag, "deleted")
        return tag

    # --- défilement
    def _yscroll(self, first, last):
        self.bar.set(first, last)
        self.at_bottom = float(last) >= 0.999
        self.app.update_more_button(self)

    def scroll_to_end(self):
        self.text.yview_moveto(1.0)
        self.at_bottom = True
        self.app.update_more_button(self)

    # --- messages
    def add(self, messages):
        t = self.text
        stick = self.at_bottom
        t.configure(state="normal")
        try:
            for msg in messages:
                self._insert(msg)
            self._trim(stick)
        finally:
            t.configure(state="disabled")
        if stick:
            t.yview_moveto(1.0)

    def _trim(self, stick):
        limit = self.app.cfg["max_messages"]
        excess = len(self.lines) - limit
        if excess <= 0 or (not stick and len(self.lines) < limit * 1.5):
            return
        self.text.delete("1.0", f"{excess + 1}.0")
        for _ in range(excess):
            msg = self.lines.popleft()
            if msg.id:
                self.by_id.pop(msg.id, None)
        self.first_n += excess

    def _insert(self, msg):
        app, t, cfg = self.app, self.text, self.app.cfg
        start = t.index("end-1c")
        base = ()
        if cfg["timestamps"]:
            t.insert("end", time.strftime("%H:%M", time.localtime(msg.ts)) + " ", ("time",))
        if msg.reply_to:
            t.insert("end", f"↪ @{msg.reply_to} ", ("reply",))
        if msg.kind in ("notice",):
            base = ("notice",)
        elif msg.kind != "event":
            if cfg["badges"]:
                for kind, label in msg.badges:
                    idx = t.index("end-1c")
                    t.image_create("end", image=app.badge_image(kind, msg.platform), padx=1, align="center")
                    t.tag_add("badge", idx)
                    t.tag_add(app.badge_label_tag(label), idx)
                if msg.badges:
                    t.insert("end", " ")
            color = readable_color(msg.color or default_color(msg.user or msg.display_name), app.c.surface) \
                or app.c.text
            ctag = self.color_tag(color)
            name = msg.display_name
            if msg.user and not msg.display_name.isascii() and msg.platform == "twitch":
                name = f"{msg.display_name} ({msg.user})"  # pseudo affiché dans une autre écriture
            t.insert("end", name, ("name", ctag), " " if msg.kind == "action" else ": ", ())
            if msg.kind == "action":
                base = (ctag,)
        for frag in msg.fragments or [("text", msg.text)]:
            kind = frag[0]
            if kind == "text":
                t.insert("end", frag[1], base)
            elif kind == "link":
                t.insert("end", frag[1], ("link",) + base)
            elif kind == "mention":
                t.insert("end", frag[1], ("mention",) + base)
            elif kind == "emote":
                self._emote(frag[1], frag[2], base)
        t.insert("end", "\n")
        line_tag = None
        if msg.kind == "event":
            line_tag = "event"
        elif msg.highlight:
            line_tag = "highlight_line"
        elif msg.kind == "msg" and app.is_mention(self.tab, msg):
            line_tag = "mention_line"
        elif msg.first:
            line_tag = "first_line"
        elif msg.own:
            line_tag = "own_line"
        if line_tag:
            t.tag_add(line_tag, start, "end-1c")
        if msg.deleted:
            t.tag_add("deleted", start, "end-1c")
        n = self.next_n
        self.next_n += 1
        self.lines.append(msg)
        if msg.id:
            self.by_id[msg.id] = n
        if msg.user:
            self.tab.chatters[msg.user] = msg.display_name

    def _emote(self, name, url, base):
        app, t = self.app, self.text
        img = app.emote_image(url)
        if img:
            t.image_create("end", image=img, padx=1, align="center")
        elif img is None:  # en cours de chargement
            t.insert("end", name, (app.emote_tag(url), "emote_text") + base)
        else:  # image illisible : le nom reste en texte
            t.insert("end", name, base)

    def image_ready(self, url, img):
        tag = self.app.emote_tag(url)
        ranges = self.text.tag_ranges(tag)
        if not ranges:
            return
        self.text.configure(state="normal")
        try:
            for i in range(len(ranges) - 2, -1, -2):
                a, b = ranges[i], ranges[i + 1]
                if img:
                    self.text.delete(a, b)
                    self.text.image_create(a, image=img, padx=1, align="center")
                else:  # illisible : le nom reste, en texte normal
                    self.text.tag_remove(tag, a, b)
                    self.text.tag_remove("emote_text", a, b)
        finally:
            self.text.configure(state="disabled")
        if self.at_bottom:
            self.text.yview_moveto(1.0)

    def _badge_enter(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        label = next((self.app.badge_labels[t] for t in self.text.tag_names(idx) if t in self.app.badge_labels), "")
        if label:
            self.app.show_tip(label, e.x_root, e.y_root)

    def _line_of(self, n):
        line = n - self.first_n + 1
        return line if 1 <= line <= len(self.lines) else None

    def delete_message(self, mid):
        n = self.by_id.get(mid)
        line = self._line_of(n) if n else None
        if line:
            self.lines[line - 1].deleted = True
            self.text.tag_add("deleted", f"{line}.0", f"{line}.end")

    def clear_user(self, user):
        for i, msg in enumerate(self.lines):
            if msg.user == user and not msg.deleted:
                msg.deleted = True
                self.text.tag_add("deleted", f"{i + 1}.0", f"{i + 1}.end")

    # --- interactions
    def _message_at(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        line = int(idx.split(".")[0])
        return self.lines[line - 1] if 1 <= line <= len(self.lines) else None

    def _user_click(self, e):
        msg = self._message_at(e)
        if not msg:
            return
        word = None
        idx = self.text.index(f"@{e.x},{e.y}")
        if "mention" in self.text.tag_names(idx):
            r = self.text.tag_prevrange("mention", idx + "+1c")
            word = self.text.get(*r).lstrip("@").rstrip(",.:!?") if r else None
        self.app.user_menu(self, e, word or msg.display_name, None if word else msg)

    def _link_click(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        r = self.text.tag_prevrange("link", idx + "+1c")
        if r:
            url = self.text.get(*r)
            self.app.open_url(url if "://" in url else "https://" + url)

    def _context(self, e):
        msg = self._message_at(e)
        if msg:
            self.app.message_menu(self, e, msg)

    def destroy(self):
        self.frame.destroy()


# =====================================================
# Application
# =====================================================
class ChatApp(tk.Tk):
    def __init__(self, targets=()):
        super().__init__(className="StreamlinkChat")
        self.withdraw()
        self.scale = max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        self.launcher_cfg = core.load_config()
        self.cfg = config.load()
        lang = self.cfg["language"] or self.launcher_cfg.get("language") or core.detect_system_language()
        self.t = core.I18n(lang)
        self.painter = Painter(self)
        self.fonts = Fonts(self, self.px)
        self.popover = Popover(self)
        self.events = queue.Queue()
        self.tabs = []
        self.current = None
        self.panel = self.panel_kind = None
        self.toast_widget = None
        self.more_btn = None
        self.tab_widgets = {}
        self.history_input, self.history_pos = [], None
        self._complete = None
        self.global_emotes = {}
        self.channel_emotes = {}
        self.emote_maps = {}
        self.images = {}            # url -> PhotoImage, False (illisible) ; absent = pas encore demandé
        self.emote_names = {}
        self.anims = {}             # url -> [image affichée, [(image, délai)], index, prochain changement]
        self.badge_images, self.badge_tags, self.badge_labels = {}, {}, {}
        self.loader = emotes.ImageLoader(config.CACHE_DIR)
        self.conns = {}
        self.input_var = tk.StringVar()
        self.add_var = tk.StringVar()
        self._make_chat_fonts()
        self.title("Streamlink Chat")
        self._icons = [self.painter.app_icon(s, "#9146FF") for s in (16, 32)]
        self.iconphoto(True, *self._icons)
        self.minsize(self.px(380), self.px(460))
        self._restore_geometry()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<ButtonPress-1>", self._global_click, add="+")
        self.bind("<Escape>", lambda e: self.popover.close() if self.popover.is_open else self.close_panel())
        self.bind("<Control-t>", lambda e: self.add_field.focus())
        self.bind("<Control-w>", lambda e: self.close_tab(self.current) if self.current else None)
        self.bind("<Control-Tab>", lambda e: self.cycle_tab(1))
        for seq in ("<Control-Shift-Tab>", "<Control-ISO_Left_Tab>"):  # ISO_Left_Tab : X11 seulement
            try:
                self.bind(seq, lambda e: self.cycle_tab(-1))
            except tk.TclError:
                pass
        self.build()
        for saved in self.cfg["tabs"]:
            self.open_tab(saved["platform"], saved["channel"], select=False, save=False)
        if self.tabs:
            self.select_tab(self.tabs[min(self.cfg["selected"], len(self.tabs) - 1)])
        for platform, channel in targets:
            self.open_tab(platform, channel)
        self.deiconify()
        self.after(40, self._pump)
        self.after(200, self._load_global_emotes)
        self.after(60, self._animate)
        self.after(300, self._check_accounts)
        instance.serve(lambda targets: self.events.put(("open", targets)))

    # --- outils
    def px(self, v):
        return int(round(v * self.scale))

    @property
    def c(self):
        return self._palette

    @property
    def accent(self):
        if self.current:
            return config.PLATFORMS[self.current.platform][1:]
        return config.NEUTRAL

    def platform_name(self, pid):
        return config.PLATFORMS[pid][0]

    def _make_chat_fonts(self):
        size = self.cfg["font_size"]
        family = self.fonts.body.actual("family")
        semi = self.fonts.body_semi.actual()
        self.chat_font = tkfont.Font(root=self, family=family, size=-self.px(size))
        self.chat_bold = tkfont.Font(root=self, family=semi["family"], size=-self.px(size),
                                     weight=semi.get("weight", "normal"))
        self.chat_small = tkfont.Font(root=self, family=family, size=-self.px(max(10, size - 2)))

    def run_in_thread(self, work, done):
        def runner():
            try:
                result = work()
            except Exception as e:
                result = e
            self.events.put(("call", done, result))
        threading.Thread(target=runner, daemon=True).start()

    def open_url(self, url):
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    def _restore_geometry(self):
        m = GEOMETRY_RE.match(self.cfg.get("geometry") or "")
        if m and 0 <= int(m.group(3)) < self.winfo_screenwidth() - 100 \
                and 0 <= int(m.group(4)) < self.winfo_screenheight() - 100:
            self.geometry(self.cfg["geometry"])
        else:
            self.geometry(f"{self.px(560)}x{self.px(780)}")

    def toast(self, text, kind="ok", action=None, duration=3200):
        if self.toast_widget is not None:
            self.toast_widget.dismiss()
        self.toast_widget = Toast(self, text, kind, action, duration, bottom=self.px(96))

    def _global_click(self, e):
        if self.popover.is_open and not self.popover.contains(e.widget) and \
                not (self.popover.anchor and str(e.widget).startswith(str(self.popover.anchor))):
            self.popover.close()

    # =====================================================
    # Construction
    # =====================================================
    def build(self):
        self.popover.close()
        for w in self.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()
        self.panel = self.panel_kind = None
        self.more_btn = None
        theme = self.cfg["theme"] or self.launcher_cfg.get("theme", "auto")
        self.mode = resolve_theme(theme)
        self._palette = c = palette(self.mode)
        t, px, f = self.t, self.px, self.fonts
        self.configure(bg=c.bg)
        for tab in self.tabs:
            tab.view = None

        content = tk.Frame(self, bg=c.bg)
        content.pack(fill="both", expand=True, padx=px(20), pady=(px(16), px(16)))
        self.content = content

        head = tk.Frame(content, bg=c.bg)
        head.pack(fill="x")
        tk.Label(head, text=t("chat_title"), font=f.title, bg=c.bg, fg=c.text).pack(side="left")
        IconButton(head, self, "settings", command=self.open_settings).pack(side="right")

        row = tk.Frame(content, bg=c.bg)
        row.pack(fill="x", pady=(px(12), 0))
        self.platform_select = Select(row, self, [(p, v[0]) for p, v in config.PLATFORMS.items()],
                                      self.cfg["default_platform"], self._set_default_platform, height=44,
                                      bg_key="surface", popup_width=150)
        self.platform_select.pack(side="right", padx=(px(8), 0))
        self.add_field = Field(row, self, self.add_var, placeholder=t("chat_add_placeholder"), icon="add",
                               kbd=t("kbd_enter"), ring=True, height=44, font=f.body, radius=10,
                               accent=self.accent, bg_key="surface")
        self.add_field.pack(side="left", fill="x", expand=True)
        self.add_field.entry.bind("<Return>", self._add_from_field)
        self.add_field.entry.bind("<KP_Enter>", self._add_from_field)

        self.tabs_row = tk.Frame(content, bg=c.bg, height=px(34))
        self.tabs_row.pack(fill="x", pady=(px(12), 0))
        self.tabs_row.pack_propagate(False)
        self.tabs_row.bind("<Configure>", lambda e: self._flow_tabs())

        # Saisie
        bottom = tk.Frame(content, bg=c.bg)
        bottom.pack(side="bottom", fill="x", pady=(px(12), 0))
        self.send_btn = Button(bottom, self, icon="send", command=self.send, kind="primary", height=44, width=44,
                               accent=self.accent, icon_size=16)
        self.send_btn.pack(side="right", padx=(px(8), 0))
        self.input = Field(bottom, self, self.input_var, placeholder="", height=44, font=f.body, radius=10,
                           ring=True, accent=self.accent, bg_key="surface")
        self.input.pack(side="left", fill="x", expand=True)
        e = self.input.entry
        e.bind("<Return>", lambda ev: self.send())
        e.bind("<KP_Enter>", lambda ev: self.send())
        e.bind("<Up>", lambda ev: self._recall(-1))
        e.bind("<Down>", lambda ev: self._recall(1))
        e.bind("<Tab>", self._tab_complete)
        e.bind("<Key>", self._reset_complete, add="+")
        self.input.cv.bind("<ButtonRelease-1>", self._input_click, add="+")
        # Carte du chat
        self.card = tk.Frame(content, bg=c.bg)
        self.card.pack(fill="both", expand=True, pady=(px(12), 0))
        self.card_cv = tk.Canvas(self.card, bg=c.bg, highlightthickness=0, bd=0)
        self.card_cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.card_cv.bind("<Configure>", lambda e: self._draw_card())
        inner = tk.Frame(self.card, bg=c.surface)
        inner.pack(fill="both", expand=True, padx=px(1), pady=px(1))
        self.card_inner = inner
        self.header = tk.Frame(inner, bg=c.surface)
        self.header.pack(fill="x", padx=(px(14), px(8)), pady=(px(8), 0))
        self.header_title = tk.Label(self.header, text="", font=f.card_title, bg=c.surface, fg=c.text)
        self.header_title.pack(side="left")
        self.header_status = tk.Label(self.header, text="", font=f.tiny, bg=c.surface, fg=c.muted)
        self.header_status.pack(side="left", padx=(px(10), 0))
        self.header_btns = tk.Frame(self.header, bg=c.surface)
        self.header_btns.pack(side="right")
        IconButton(self.header_btns, self, "link", command=self.open_in_browser, size=32, icon_size=14,
                   bg=c.surface).pack(side="right")
        IconButton(self.header_btns, self, "play", command=self.watch, size=32, icon_size=14,
                   bg=c.surface).pack(side="right")
        self.header_sep = tk.Frame(inner, bg=c.border, height=1)
        self.header_sep.pack(fill="x", pady=(px(8), 0))
        self.views_box = tk.Frame(inner, bg=c.surface)
        self.views_box.pack(fill="both", expand=True)
        self.empty = tk.Label(self.views_box, text=t("chat_empty"), font=f.body, bg=c.surface, fg=c.muted,
                              justify="center", wraplength=px(360))

        self.build_tabs()
        if self.current:
            current, self.current = self.current, None
            self.select_tab(current)
        else:
            self.refresh_current()
        self.after_idle(self.apply_chrome)

    def apply_chrome(self):
        apply_window_chrome(self, self.c.dark, border=self.accent[0], caption=self.c.title, text=self.c.text)

    def _draw_card(self):
        cv, c, px = self.card_cv, self.c, self.px
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w > 2 and h > 2:
            self.painter.round_rect(cv, 0, 0, w, h, px(12), c.surface, c.border, c.bg)
            self.card_inner.pack_configure(padx=px(4), pady=px(4))

    # --- onglets
    def build_tabs(self):
        for w in self.tabs_row.winfo_children():
            w.destroy()
        self.tab_widgets = {}
        for tab in self.tabs:
            self.tab_widgets[tab.key] = ChannelTab(self.tabs_row, self, tab, tab is self.current,
                                                   lambda tb=tab: self.select_tab(tb),
                                                   lambda tb=tab: self.close_tab(tb),
                                                   lambda w, tb=tab: self.tab_menu(w, tb))
        self.more_tabs = Button(self.tabs_row, self, icon="more", command=self._hidden_tabs_menu, kind="secondary",
                                height=34, width=40, radius=17)
        self._flow_tabs()

    def _flow_tabs(self):
        width = self.tabs_row.winfo_width()
        if width <= 1:
            return
        gap, x, reserve = self.px(6), 0, self.px(46)
        self._hidden = []
        widgets = [(tab, self.tab_widgets.get(tab.key)) for tab in self.tabs]
        for i, (tab, w) in enumerate(widgets):
            if w is None:
                continue
            need = int(w.cget("width"))
            limit = width - (reserve if i < len(widgets) - 1 else 0)
            if not self._hidden and x + need <= limit:
                w.place(x=x, y=0)
                x += need + gap
            else:
                w.place_forget()
                self._hidden.append(tab)
        if self._hidden:
            self.more_tabs.place(x=x, y=0)
            self.more_tabs.set_badge(self.c.warn if any(t.mentioned for t in self._hidden) else None)
        else:
            self.more_tabs.place_forget()

    def _hidden_tabs_menu(self):
        items = [{"label": t.title, "value": t, "right": self.platform_name(t.platform),
                  "right_dot": config.PLATFORMS[t.platform][1], "right_color": self.c.muted,
                  "selected": t is self.current} for t in getattr(self, "_hidden", [])]
        self.popover.show(self.more_tabs, items, lambda it: self.select_tab(it["value"], to_front=True),
                          width=self.px(260))

    def open_tab(self, platform, channel, select=True, save=True):
        for tab in self.tabs:
            if tab.key == (platform, channel):
                if select:
                    self.select_tab(tab)
                return tab
        tab = Tab(platform, channel)
        tab.history = deque(maxlen=self.cfg["max_messages"])
        self.tabs.append(tab)
        self._connection(platform).join(channel)
        if self.tab_widgets is not None and hasattr(self, "tabs_row"):
            self.build_tabs()
        if select:
            self.select_tab(tab)
        if save:
            self.save_tabs()
        return tab

    def close_tab(self, tab):
        if tab not in self.tabs:
            return
        i = self.tabs.index(tab)
        self.tabs.remove(tab)
        conn = self.conns.get(tab.platform)
        if conn:
            conn.part(tab.channel)
        if tab.view:
            tab.view.destroy()
        if self.current is tab:
            self.current = None
            if self.tabs:
                self.select_tab(self.tabs[min(i, len(self.tabs) - 1)])
            else:
                self.refresh_current()
        self.build_tabs()
        self.save_tabs()

    def select_tab(self, tab, to_front=False):
        if to_front and tab in self.tabs:
            self.tabs.remove(tab)
            self.tabs.insert(0, tab)
            self.build_tabs()
        previous, self.current = self.current, tab
        if previous and previous.view and previous is not tab:
            previous.view.frame.pack_forget()
        tab.unread, tab.mentioned = 0, False
        for t, w in list(self.tab_widgets.items()):
            w.refresh(selected=(t == tab.key))
        self._flow_tabs()
        self.refresh_current()
        self.save_tabs()

    def cycle_tab(self, d):
        if self.tabs and self.current in self.tabs:
            self.select_tab(self.tabs[(self.tabs.index(self.current) + d) % len(self.tabs)])
        return "break"

    def tab_menu(self, widget, tab):
        t = self.t
        items = [{"label": t("chat_menu_watch"), "icon": "play", "value": "watch"},
                 {"label": t("chat_menu_browser"), "icon": "link", "value": "browser"},
                 {"label": t("chat_menu_reconnect"), "icon": "sync", "value": "reconnect"},
                 {"label": t("chat_menu_close"), "icon": "close", "value": "close"}]

        def pick(item):
            v = item["value"]
            if v == "watch":
                self.watch(tab)
            elif v == "browser":
                self.open_in_browser(tab)
            elif v == "reconnect":
                self.reconnect(tab)
            else:
                self.close_tab(tab)
        self.popover.show(widget, items, pick, width=self.px(240))

    def save_tabs(self):
        self.cfg["tabs"] = [{"platform": t.platform, "channel": t.channel} for t in self.tabs]
        self.cfg["selected"] = self.tabs.index(self.current) if self.current in self.tabs else 0
        try:
            config.save(self.cfg)
        except OSError as e:
            log.warning("chat.json : %s", e)

    def _set_default_platform(self, pid):
        self.cfg["default_platform"] = pid
        config.save(self.cfg)

    def _add_from_field(self, e=None):
        target = config.parse_target(self.add_var.get(), self.cfg["default_platform"])
        if not target:
            self.toast(self.t("chat_bad_channel"), "warn")
            return "break"
        self.add_var.set("")
        self.open_tab(*target)
        self.input.focus()
        return "break"

    # --- vue du chat courant
    def refresh_current(self):
        tab = self.current
        accent = self.accent
        for w in (self.add_field, self.input):
            w.set_accent(accent)
        self.send_btn.set_accent(accent)
        if not tab:
            self.header.pack_forget()
            self.header_sep.pack_forget()
            self.empty.pack(fill="both", expand=True)
            self._update_input()
            self.apply_chrome()
            return
        self.empty.pack_forget()
        if not self.header.winfo_ismapped():
            self.header_sep.pack(fill="x", pady=(self.px(8), 0), before=self.views_box)
            self.header.pack(fill="x", padx=(self.px(14), self.px(8)), pady=(self.px(8), 0),
                             before=self.header_sep)
        if tab.view is None:
            tab.view = ChatView(self, self.views_box, tab)
            if tab.history:
                tab.view.add(list(tab.history))
        tab.view.frame.pack(fill="both", expand=True)
        tab.view.scroll_to_end()
        self.update_header()
        self._update_input()
        self.apply_chrome()

    def update_header(self):
        tab = self.current
        if not tab:
            return
        c, t = self.c, self.t
        self.header_title.configure(text=tab.title)
        status = {"connecting": (t("chat_status_connecting"), c.muted),
                  "reconnecting": (t("chat_status_reconnecting"), c.warn),
                  "error": (self._error_text(tab), c.error)}.get(tab.status)
        if tab.status == "connected":
            conn = self.conns.get(tab.platform)
            status = (t("chat_status_rw") if conn and conn.can_send else t("chat_status_ro"), c.ok)
        text, color = status or ("", c.muted)
        self.header_status.configure(text=f"●  {self.platform_name(tab.platform)} · {text}", fg=color)

    def _error_text(self, tab):
        d, t = tab.detail, self.t
        if d == "blocked":
            return t("chat_err_blocked")
        if d == "not_found":
            return t("chat_err_not_found")
        if d == "offline":
            return t("chat_err_offline")
        return t("chat_status_error")

    def update_more_button(self, view):
        if view is not (self.current.view if self.current else None):
            return
        if view.at_bottom:
            if self.more_btn is not None:
                self.more_btn.place_forget()
            return
        if self.more_btn is None or not self.more_btn.winfo_exists():
            self.more_btn = Button(self.views_box, self, text=self.t("chat_more"), icon="arrow_down",
                                   command=lambda: self.current and self.current.view and
                                   self.current.view.scroll_to_end(), kind="primary", height=32,
                                   accent=self.accent, radius=16, font=self.fonts.small_semi, icon_size=12, pad=14)
        self.more_btn.set_accent(self.accent)
        self.more_btn.place(relx=0.5, rely=1.0, y=-self.px(12), anchor="s")
        tk.Misc.lift(self.more_btn)

    def _update_input(self):
        tab, t = self.current, self.t
        conn = self.conns.get(tab.platform) if tab else None
        can = bool(tab and conn and conn.can_send and tab.status == "connected")
        if not tab:
            hint = t("chat_input_none")
        elif tab.platform == "steamtv":
            hint = t("chat_input_steam")
        elif not (conn and conn.can_send):
            hint = t("chat_input_login", platform=self.platform_name(tab.platform))
        elif not can:
            hint = t("chat_status_connecting")
        else:
            hint = t("chat_input_placeholder", channel=tab.title)
        self.input.set_placeholder(hint)
        self.input.set_disabled(not can)
        self.send_btn.set_disabled(not can)
        self._input_needs_login = bool(tab and tab.platform != "steamtv" and not (conn and conn.can_send))

    def _input_click(self, e):
        if getattr(self, "_input_needs_login", False):
            self.open_settings(section="accounts")

    # =====================================================
    # Connexions et événements
    # =====================================================
    def _connection(self, platform):
        conn = self.conns.get(platform)
        if conn is not None:
            return conn
        emit = self.events.put
        if platform == "twitch":
            acc = self.cfg["accounts"].get("twitch") or {}
            conn = TwitchConnection(emit, acc.get("login"), acc.get("access_token"),
                                    emote_lookup=lambda ch: self.emote_maps.get(("twitch", ch), self.global_emotes),
                                    theme="dark" if self.c.dark else "light")
        elif platform == "kick":
            acc = self.cfg["accounts"].get("kick") or {}
            conn = KickManager(emit, acc.get("access_token"),
                               emote_lookup=lambda ch: self.emote_maps.get(("kick", ch), {}))
        else:
            conn = SteamManager(emit)
        self.conns[platform] = conn.start()
        return conn

    def restart_connection(self, platform):
        old = self.conns.pop(platform, None)
        if old:
            old.stop()
        tabs = [t for t in self.tabs if t.platform == platform]
        if tabs:
            conn = self._connection(platform)
            for tab in tabs:
                conn.join(tab.channel)
        self._update_input()
        self.update_header()

    def reconnect(self, tab):
        conn = self.conns.get(tab.platform)
        if conn:
            conn.part(tab.channel)
            conn.join(tab.channel)

    def _tab(self, platform, channel):
        return next((t for t in self.tabs if t.platform == platform and t.channel == channel), None)

    def _pump(self):
        batches = {}
        try:
            for _ in range(800):
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "message":
                    msg = ev[1]
                    if msg.channel == "*":  # avis général de Twitch : chat courant
                        if self.current and self.current.platform == msg.platform:
                            msg.channel = self.current.channel
                        else:
                            continue
                    tab = self._tab(msg.platform, msg.channel)
                    if tab:
                        tab.history.append(msg)
                        batches.setdefault(tab.key, (tab, []))[1].append(msg)
                elif kind == "call":
                    try:
                        ev[1](ev[2])
                    except tk.TclError:
                        pass
                else:
                    self._event(ev, batches)
        except queue.Empty:
            pass
        for tab, msgs in batches.values():
            if tab.view:
                tab.view.add(msgs)
            if tab is not self.current:
                tab.unread += sum(1 for m in msgs if m.kind == "msg")
                if any(m.kind == "msg" and self.is_mention(tab, m) for m in msgs):
                    tab.mentioned = True
                w = self.tab_widgets.get(tab.key)
                if w:
                    w.refresh()
        if any(tab is not self.current for tab, _ in batches.values()):
            self._flow_tabs()
        self.after(40, self._pump)

    def _event(self, ev, batches):
        kind = ev[0]
        if kind == "open":
            for platform, channel in ev[1]:
                self.open_tab(platform, channel)
            self.deiconify()
            self.lift()
            self.focus_force()
            return
        if kind == "auth_failed":
            self.toast(self.t("chat_auth_failed", platform=self.platform_name(ev[1])), "error")
            self.cfg["accounts"][ev[1]] = {k: v for k, v in self.cfg["accounts"][ev[1]].items()
                                          if k in ("client_id", "client_secret")}
            config.save(self.cfg)
            self.after(100, lambda: self.restart_connection(ev[1]))
            return
        platform, channel = ev[1], ev[2]
        tab = self._tab(platform, channel)
        if tab is None:
            return
        if kind == "status":
            tab.status, tab.detail = ev[3], ev[4]
            w = self.tab_widgets.get(tab.key)
            if w:
                w.redraw()
            if tab is self.current:
                self.update_header()
                self._update_input()
        elif kind == "room":
            info = ev[3]
            tab.info.update(info)
            if info.get("name") and info["name"] != tab.title:
                tab.title = info["name"]
                self.build_tabs()
                if tab is self.current:
                    self.update_header()
            self._load_channel_emotes(tab)
        elif kind == "delete" and tab.view:
            self._flush(tab, batches)
            tab.view.delete_message(ev[3])
        elif kind == "clear_user" and tab.view:
            self._flush(tab, batches)
            tab.view.clear_user(ev[3])
        elif kind == "clear":
            from .common import ChatMessage
            msg = ChatMessage(platform, channel, text=self.t("chat_cleared"), kind="notice",
                              fragments=[("text", self.t("chat_cleared"))])
            tab.history.append(msg)
            batches.setdefault(tab.key, (tab, []))[1].append(msg)

    def _flush(self, tab, batches):
        """Affiche les messages en attente avant une suppression qui pourrait les viser."""
        pending = batches.pop(tab.key, None)
        if pending and tab.view:
            tab.view.add(pending[1])

    def is_mention(self, tab, msg):
        names = []
        acc = self.cfg["accounts"].get(tab.platform) or {}
        if acc.get("login"):
            names.append(acc["login"])
        if msg.own or not (names or self.cfg["highlights"]):
            return False
        return mentions(msg.fragments, names, self.cfg["highlights"])

    # =====================================================
    # Badges et infobulles
    # =====================================================
    def badge_image(self, kind, platform):
        size = self.px(18)
        key = (kind, platform if kind == "subscriber" else "", size)
        img = self.badge_images.get(key)
        if img is None:
            color, fg = (config.PLATFORMS[platform][1:] if kind == "subscriber" else (None, "#FFFFFF"))
            img = self.badge_images[key] = tk.PhotoImage(master=self, data=badges.badge_b64(kind, size, color, fg))
        return img

    def badge_label_tag(self, label):
        tag = self.badge_tags.get(label)
        if tag is None:
            tag = self.badge_tags[label] = f"bl{len(self.badge_tags)}"
            self.badge_labels[tag] = label
        return tag

    def show_tip(self, text, x_root, y_root):
        self.hide_tip()
        c, f = self.c, self.fonts
        tip = self._tip = tk.Label(self, text=text, font=f.tiny, bg=c.text, fg=c.bg, padx=self.px(8),
                                   pady=self.px(3))
        tip.place(x=x_root - self.winfo_rootx() + self.px(10), y=y_root - self.winfo_rooty() - self.px(30))
        tk.Misc.lift(tip)

    def hide_tip(self):
        tip = getattr(self, "_tip", None)
        if tip is not None:
            tip.destroy()
            self._tip = None

    # =====================================================
    # Emotes
    # =====================================================
    def emote_tag(self, url):
        return "em_" + hashlib.md5(url.encode()).hexdigest()[:12]

    def emote_image(self, url):
        """PhotoImage si prête, None si en cours de chargement, False si illisible."""
        if url in self.images:
            return self.images[url]
        self.images[url] = None
        self.loader.request(url, lambda u, data: self.events.put(("call", self._image_loaded, (u, data))))
        return None

    def _image_loaded(self, payload):
        url, data = payload
        if self.images.get(url):
            return  # déjà chargée (deux demandes simultanées)
        img = False
        if data:
            try:
                kind = emotes.image_kind(data)
                img = tk.PhotoImage(master=self, data=base64.b64encode(data), format=kind)
                if kind == "gif":
                    delays = emotes.gif_frames(data)
                    if len(delays) > 1:
                        frames = []
                        for i, d in enumerate(delays):
                            frames.append((tk.PhotoImage(master=self, data=base64.b64encode(data),
                                                         format=f"gif -index {i}"), d))
                        self.anims[url] = [img, frames, 0, time.time() + delays[0] / 1000]
            except tk.TclError:
                img = False
        self.images[url] = img
        for tab in self.tabs:
            if tab.view:
                tab.view.image_ready(url, img or None)

    def _animate(self):
        if self.cfg["animated"] and self.anims:
            now = time.time()
            for anim in self.anims.values():
                if now >= anim[3]:
                    anim[2] = (anim[2] + 1) % len(anim[1])
                    frame, delay = anim[1][anim[2]]
                    try:
                        anim[0].tk.call(anim[0], "copy", frame, "-compositingrule", "set")
                    except tk.TclError:
                        pass
                    anim[3] = now + delay / 1000
        self.after(40, self._animate)

    def _load_global_emotes(self):
        providers = tuple(self.cfg["providers"])
        if not providers:
            return
        self.run_in_thread(lambda: emotes.fetch_global(providers), self._global_emotes_loaded)

    def _global_emotes_loaded(self, result):
        if isinstance(result, dict):
            self.global_emotes = result
            self._rebuild_emote_maps()

    def _load_channel_emotes(self, tab):
        providers = tuple(self.cfg["providers"])
        uid = tab.info.get("room_id") or (tab.info.get("user_id") if tab.platform == "kick" else None)
        if not providers or not uid or tab.platform == "steamtv":
            return
        key = tab.key
        self.run_in_thread(lambda: emotes.fetch_channel(tab.platform, uid, providers),
                           lambda r: self._channel_emotes_loaded(key, r))

    def _channel_emotes_loaded(self, key, result):
        if isinstance(result, dict):
            self.channel_emotes[key] = result
            self._rebuild_emote_maps()

    def _rebuild_emote_maps(self):
        maps = {}
        for tab in self.tabs:
            base = self.global_emotes if tab.platform == "twitch" else {}
            maps[tab.key] = {**base, **self.channel_emotes.get(tab.key, {})}
        self.emote_maps = maps
        self.emote_names = {url: name for m in maps.values() for name, url in m.items()}

    # =====================================================
    # Envoi
    # =====================================================
    def send(self):
        tab = self.current
        text = self.input_var.get().strip()
        if not tab or not text:
            return "break"
        conn = self.conns.get(tab.platform)
        if not conn or not conn.can_send:
            self.open_settings(section="accounts")
            return "break"
        self.history_input.append(text)
        self.history_input = self.history_input[-50:]
        self.history_pos = None
        self.input_var.set("")
        if tab.platform == "twitch":
            echo = conn.send_message(tab.channel, text)
            if echo:
                self.events.put(("message", echo))
        else:
            channel = tab.channel
            self.run_in_thread(lambda: conn.send_message(channel, text), self._sent)
        return "break"

    def _sent(self, result):
        if isinstance(result, Exception):
            log.warning("Envoi : %s", result)
            self.toast(self.t("chat_send_failed"), "error")

    def _recall(self, d):
        if not self.history_input:
            return "break"
        if self.history_pos is None:
            self.history_pos = len(self.history_input)
        self.history_pos = max(0, min(len(self.history_input), self.history_pos + d))
        self.input_var.set(self.history_input[self.history_pos] if self.history_pos < len(self.history_input) else "")
        self.input.entry.icursor("end")
        return "break"

    def _reset_complete(self, e):
        if e.keysym not in ("Tab", "Shift_L", "Shift_R"):
            self._complete = None

    def _tab_complete(self, e):
        tab = self.current
        if not tab:
            return "break"
        entry = self.input.entry
        text, pos = self.input_var.get(), entry.index("insert")
        if self._complete is None:
            start = pos
            while start > 0 and not text[start - 1].isspace():
                start -= 1
            word = text[start:pos]
            if not word:
                return "break"
            at = word.startswith("@")
            prefix = word.lstrip("@").lower()
            names = sorted(set(tab.chatters.values()), key=str.lower)
            cands = [("@" if at else "") + n for n in names if n.lower().startswith(prefix)]
            if not at:
                cands += sorted(n for n in self.emote_maps.get(tab.key, {}) if n.lower().startswith(prefix))
            if not cands:
                return "break"
            self._complete = [start, cands, -1, len(word)]
        start, cands, i, length = self._complete
        i = (i + 1) % len(cands)
        new = cands[i] + " "
        self.input_var.set(text[:start] + new + text[start + length:])
        entry.icursor(start + len(new))
        self._complete = [start, cands, i, len(new)]
        return "break"

    # =====================================================
    # Menus
    # =====================================================
    def _anchor_at(self, e):
        anchor = getattr(self, "_menu_anchor", None)
        if anchor is None or not anchor.winfo_exists():
            anchor = self._menu_anchor = tk.Frame(self, width=1, height=1, bg=self.c.bg)
        anchor.place(x=e.x_root - self.winfo_rootx(), y=e.y_root - self.winfo_rooty())
        anchor.update_idletasks()
        return anchor

    def user_menu(self, view, e, name, msg):
        t, tab = self.t, view.tab
        conn = self.conns.get(tab.platform)
        items = []
        if conn and conn.can_send:
            items.append({"label": t("chat_menu_mention", name=name), "icon": "chat", "value": "mention"})
        items += [{"label": t("chat_menu_copy_name"), "icon": "link", "value": "copy"},
                  {"label": t("chat_menu_open_chat", name=name), "icon": "add", "value": "open"},
                  {"label": t("chat_menu_profile"), "icon": "link", "value": "profile"}]

        def pick(item):
            v = item["value"]
            login = (msg.user if msg and msg.user else name).lower()
            if v == "mention":
                cur = self.input_var.get()
                self.input_var.set((cur + " " if cur and not cur.endswith(" ") else cur) + f"@{name} ")
                self.input.focus()
            elif v == "copy":
                self.clipboard_clear()
                self.clipboard_append(name)
            elif v == "open":
                target = config.parse_target(login, tab.platform)
                if target:
                    self.open_tab(*target)
            elif v == "profile":
                self.open_url(config.channel_url(tab.platform, login))
        self.popover.show(self._anchor_at(e), items, pick, width=self.px(260))

    def message_menu(self, view, e, msg):
        t = self.t
        items = [{"label": t("chat_menu_copy_message"), "icon": "link", "value": "copy"}]
        if msg.user:
            items.append({"label": t("chat_menu_copy_name"), "icon": "link", "value": "name"})

        def pick(item):
            self.clipboard_clear()
            self.clipboard_append(msg.text if item["value"] == "copy" else msg.display_name)
            self.toast(t("chat_copied"))
        self.popover.show(self._anchor_at(e), items, pick, width=self.px(240))

    # =====================================================
    # Regarder / ouvrir
    # =====================================================
    def open_in_browser(self, tab=None):
        tab = tab or self.current
        if tab:
            self.open_url(config.channel_url(tab.platform, tab.channel))

    def watch(self, tab=None):
        """Lance le stream avec Streamlink, avec les réglages du lanceur (lecteur, qualité, options)."""
        tab = tab or self.current
        if not tab:
            return
        t = self.t
        lcfg = core.load_config()
        streamlink = core.find_streamlink(lcfg.get("streamlink_path", ""))
        if not streamlink:
            self.toast(t("toast_no_streamlink"), "error")
            return
        platforms, _ = core.load_platforms()
        p = next((x for x in platforms if x["id"] == tab.platform), None)
        url = config.channel_url(tab.platform, tab.channel)
        quality = (lcfg.get("qualities") or {}).get(tab.platform) or (p or {}).get("default_quality") or "best"
        opts, _ = core.player_options(lcfg)
        command = [streamlink, *((p or {}).get("args") or []), *opts, url, quality]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags)
            self.toast(t("chat_watch_started", channel=tab.title))
        except OSError as e:
            log.warning("Streamlink : %s", e)
            self.toast(t("toast_launch_failed"), "error")

    # =====================================================
    # Paramètres
    # =====================================================
    def open_panel(self, kind, title, body_builder, footer_builder=None):
        self.close_panel()
        self.popover.close()
        c, px = self.c, self.px
        panel = tk.Frame(self, bg=c.panel)
        panel.place(relx=1.0, rely=0, anchor="ne", relheight=1.0, width=min(px(392), self.winfo_width()))
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
        panel.update_idletasks()
        body_builder(body)
        panel.lift()
        self.panel, self.panel_kind, self.panel_area = panel, kind, area

    def close_panel(self):
        if self.panel is not None:
            self.panel.destroy()
        self.panel = self.panel_kind = None
        self.popover.close()
        cancel = getattr(self, "_login_cancel", None)
        if cancel:
            cancel.set()

    def _section(self, parent, title, first=False):
        c, px = self.c, self.px
        f = tk.Frame(parent, bg=c.panel)
        f.pack(fill="x", pady=(0 if first else px(22), 0))
        tk.Label(f, text=title.upper(), font=self.fonts.caps, bg=c.panel, fg=c.muted).pack(anchor="w",
                                                                                          pady=(0, px(6)))
        return f

    def _hint(self, parent, text, link=None):
        lbl = tk.Label(parent, text=text, font=self.fonts.tiny, bg=self.c.panel, fg=self.c.faint, justify="left",
                       wraplength=self.px(320), anchor="w")
        lbl.pack(anchor="w", pady=(self.px(6), 0))
        if link:
            lbl.configure(cursor="hand2", fg=self.c.muted)
            lbl.bind("<ButtonRelease-1>", lambda e: self.open_url(link))
        return lbl

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
        if sub:
            tk.Label(left, text=sub, font=self.fonts.tiny, bg=c.panel, fg=c.faint, anchor="w", justify="left",
                     wraplength=px(260)).pack(anchor="w")

    def _field(self, parent, value, placeholder="", secret=False):
        var = tk.StringVar(value=value)
        f = Field(parent, self, var, placeholder=placeholder, height=40, font=self.fonts.body, radius=8,
                  accent=self.accent, bg_key="field")
        if secret:
            f.entry.configure(show="•")
        f.pack(fill="x", pady=(self.px(4), 0))
        return var

    def open_settings(self, section=None):
        t = self.t
        s = self.settings_state = {k: (list(v) if isinstance(v, list) else v) for k, v in self.cfg.items()
                                   if k not in ("tabs", "accounts", "geometry", "selected")}
        accounts = self.cfg["accounts"]

        def body(b):
            sec = self._section(b, t("chat_section_display"), first=True)
            langs = core.available_languages()
            self._setting_row(sec, t("label_language"), lambda r: Select(
                r, self, [("", t("chat_same_as_launcher"))] + [(code, name) for code, name in langs],
                s["language"], lambda v: s.update(language=v), height=36, width=180, font=self.fonts.small))
            self._setting_row(sec, t("label_theme"), lambda r: Select(
                r, self, [("", t("chat_same_as_launcher")), ("auto", t("theme_auto")), ("light", t("theme_light")),
                          ("dark", t("theme_dark"))], s["theme"], lambda v: s.update(theme=v), height=36, width=180,
                font=self.fonts.small))
            self._setting_row(sec, t("chat_label_font_size"), lambda r: Select(
                r, self, [(n, f"{n} px") for n in config.FONT_SIZES], s["font_size"],
                lambda v: s.update(font_size=v), height=36, width=110, font=self.fonts.small))
            self._switch_row(sec, t("chat_label_timestamps"), None, s["timestamps"],
                             lambda v: s.update(timestamps=v))
            self._switch_row(sec, t("chat_label_badges"), None, s["badges"], lambda v: s.update(badges=v))
            self._switch_row(sec, t("chat_label_animated"), None, s["animated"], lambda v: s.update(animated=v))

            sec = self._section(b, t("chat_section_emotes"))
            for pid, label in (("bttv", "BetterTTV"), ("ffz", "FrankerFaceZ"), ("7tv", "7TV")):
                def toggle(v, pid=pid):
                    s["providers"] = [x for x in s["providers"] if x != pid] + ([pid] if v else [])
                self._switch_row(sec, label, None, pid in s["providers"], toggle)
            self._hint(sec, t("chat_hint_emotes"))

            sec = self._section(b, t("chat_section_highlights"))
            hl = self._field(sec, ", ".join(s["highlights"]), placeholder=t("chat_highlights_placeholder"))
            s["_highlights_var"] = hl
            self._hint(sec, t("chat_hint_highlights"))
            self._setting_row(sec, t("chat_label_max_messages"), lambda r: Select(
                r, self, [(n, str(n)) for n in config.MAX_MESSAGES], s["max_messages"],
                lambda v: s.update(max_messages=v), height=36, width=110, font=self.fonts.small))

            sec = self._section(b, t("chat_section_accounts"))
            self.accounts_box = sec
            self._account_block(sec, "twitch", accounts.get("twitch") or {})
            self._account_block(sec, "kick", accounts.get("kick") or {})
            if section == "accounts":
                self.after(50, lambda: self._scroll_to(sec))

        def footer(fb):
            Button(fb, self, text=t("btn_save"), kind="primary", accent=self.accent, height=40,
                   command=self.save_settings).pack(side="right")
        self.open_panel("settings", t("title_settings"), body, footer)

    def _scroll_to(self, widget):
        try:
            area = self.panel_area
            area.update_idletasks()
            total = max(1, area.body.winfo_height())
            area.canvas.yview_moveto(max(0.0, widget.winfo_y() / total - 0.02))
        except (tk.TclError, AttributeError):
            pass

    def _account_block(self, parent, platform, acc):
        t, c, px = self.t, self.c, self.px
        box = tk.Frame(parent, bg=c.panel)
        box.pack(fill="x", pady=(px(4), px(14)))
        top = tk.Frame(box, bg=c.panel)
        top.pack(fill="x")
        color = config.PLATFORMS[platform][1]
        dot = tk.Canvas(top, width=px(10), height=px(10), bg=c.panel, highlightthickness=0, bd=0)
        self.painter.circle(dot, px(5), px(5), px(8), color, bg=c.panel)
        dot.pack(side="left", padx=(0, px(8)))
        tk.Label(top, text=self.platform_name(platform), font=self.fonts.body_semi, bg=c.panel,
                 fg=c.text).pack(side="left")
        logged = bool(acc.get("access_token"))
        state = t("chat_account_logged", name=acc.get("login") or "?") if logged else t("chat_account_none")
        tk.Label(top, text=state, font=self.fonts.tiny, bg=c.panel, fg=c.ok if logged else c.faint).pack(
            side="right")
        if logged:
            Button(box, self, text=t("chat_logout"), kind="secondary", height=36,
                   command=lambda: self.logout(platform)).pack(anchor="w", pady=(px(8), 0))
            return
        cid = self._field(box, acc.get("client_id", ""), placeholder=t("chat_client_id"))
        secret = None
        if platform == "kick":
            secret = self._field(box, acc.get("client_secret", ""), placeholder=t("chat_client_secret"),
                                 secret=True)
        Button(box, self, text=t("chat_login", platform=self.platform_name(platform)), kind="primary",
               accent=config.PLATFORMS[platform][1:], height=36,
               command=lambda: self.login(platform, cid.get().strip(), secret.get().strip() if secret else "")
               ).pack(anchor="w", pady=(px(8), 0))
        if platform == "twitch":
            self._hint(box, t("chat_hint_twitch_app"), link="https://dev.twitch.tv/console/apps/create")
        else:
            self._hint(box, t("chat_hint_kick_app", redirect=auth.KICK_REDIRECT),
                       link="https://kick.com/settings/developer")

    def save_settings(self):
        s = self.settings_state
        hl = s.pop("_highlights_var", None)
        if hl is not None:
            s["highlights"] = [w.strip() for w in hl.get().split(",") if w.strip()][:30]
        rebuild = any(s[k] != self.cfg[k] for k in ("language", "theme", "font_size", "timestamps", "badges"))
        providers_changed = sorted(s["providers"]) != sorted(self.cfg["providers"])
        self.cfg.update({k: v for k, v in s.items() if k in self.cfg})
        config.save(self.cfg)
        for tab in self.tabs:
            if tab.history.maxlen != self.cfg["max_messages"]:
                tab.history = deque(tab.history, maxlen=self.cfg["max_messages"])
        self.close_panel()
        if rebuild:
            lang = self.cfg["language"] or self.launcher_cfg.get("language") or core.detect_system_language()
            self.t = core.I18n(lang)
            self._make_chat_fonts()
            self.build()
        if providers_changed:
            self.global_emotes, self.channel_emotes = {}, {}
            self._rebuild_emote_maps()
            self._load_global_emotes()
            for tab in self.tabs:
                self._load_channel_emotes(tab)
        self.toast(self.t("toast_settings_saved"))

    # --- comptes
    def login(self, platform, client_id, secret=""):
        t = self.t
        if not client_id or (platform == "kick" and not secret):
            self.toast(t("chat_need_client_id"), "warn")
            return
        acc = self.cfg["accounts"].setdefault(platform, {})
        acc["client_id"] = client_id
        if secret:
            acc["client_secret"] = secret
        config.save(self.cfg)
        self._login_cancel = cancel = threading.Event()
        if platform == "twitch":
            self.run_in_thread(lambda: auth.twitch_device_start(client_id),
                               lambda r: self._twitch_device(client_id, r, cancel))
        else:
            page = ("<html><body style='font-family:sans-serif;background:#141518;color:#EDEDEF;padding:40px'>"
                    f"<h2>Streamlink Chat</h2><p>{t('chat_login_browser_done')}</p></body></html>").encode()
            self.toast(t("chat_login_browser"), duration=6000)
            self.run_in_thread(lambda: auth.kick_login(client_id, secret, webbrowser.open, cancel, page=page),
                               lambda r: self._login_done("kick", r))

    def _twitch_device(self, client_id, device, cancel):
        t, c, px = self.t, self.c, self.px
        if isinstance(device, Exception):
            log.warning("Twitch device : %s", device)
            self.toast(t("chat_login_failed", platform="Twitch"), "error")
            return
        uri = device.get("verification_uri") or "https://www.twitch.tv/activate"

        def body(b):
            tk.Label(b, text=t("chat_device_intro"), font=self.fonts.body, bg=c.panel, fg=c.text, justify="left",
                     wraplength=px(320), anchor="w").pack(anchor="w")
            code = tk.Label(b, text=device.get("user_code", ""), font=self.fonts.title, bg=c.panel, fg=c.text)
            code.pack(anchor="w", pady=(px(18), px(18)))
            row = tk.Frame(b, bg=c.panel)
            row.pack(fill="x")
            Button(row, self, text=t("chat_device_open"), icon="link", kind="primary", height=40,
                   accent=config.PLATFORMS["twitch"][1:], command=lambda: self.open_url(uri)).pack(side="left")

            def copy():
                self.clipboard_clear()
                self.clipboard_append(device.get("user_code", ""))
                self.toast(t("chat_copied"))
            Button(row, self, text=t("chat_device_copy"), kind="secondary", height=40, command=copy).pack(
                side="left", padx=(px(8), 0))
            self._hint(b, t("chat_device_wait"))
        self.open_panel("login", t("chat_login", platform="Twitch"), body)
        self._login_cancel = cancel
        self.open_url(uri)
        self.run_in_thread(lambda: auth.twitch_device_poll(client_id, device, cancel),
                           lambda r: self._login_done("twitch", r))

    def _login_done(self, platform, result):
        t = self.t
        if isinstance(result, Exception):
            if str(result) != "cancelled":
                log.warning("Connexion %s : %s", platform, result)
                self.toast(t("chat_login_failed", platform=self.platform_name(platform)), "error")
            return
        acc = self.cfg["accounts"].setdefault(platform, {})
        acc.update(result)
        config.save(self.cfg)
        if self.panel_kind == "login":
            self.close_panel()
        elif self.panel_kind == "settings":
            self.open_settings(section="accounts")
        self.toast(t("chat_login_ok", platform=self.platform_name(platform), name=result.get("login") or "?"))
        self.restart_connection(platform)

    def logout(self, platform):
        acc = self.cfg["accounts"].get(platform) or {}
        self.cfg["accounts"][platform] = {k: v for k, v in acc.items() if k in ("client_id", "client_secret")}
        config.save(self.cfg)
        self.restart_connection(platform)
        if self.panel_kind == "settings":
            self.open_settings(section="accounts")

    def _check_accounts(self):
        """Au démarrage : vérifie / renouvelle les jetons enregistrés (hors de l'interface)."""
        tw = self.cfg["accounts"].get("twitch") or {}
        if tw.get("access_token"):
            self.run_in_thread(lambda: auth.twitch_ensure(tw), lambda r: self._account_checked("twitch", tw, r))
        kk = self.cfg["accounts"].get("kick") or {}
        if kk.get("access_token") and kk.get("refresh_token") and kk.get("expires_at", 0) < time.time() + 300:
            self.run_in_thread(lambda: auth.kick_refresh(kk), lambda r: self._account_checked("kick", kk, r))

    def _account_checked(self, platform, old, result):
        if isinstance(result, Exception):
            return  # réseau indisponible : on garde le jeton, la connexion le dira
        if result is None:
            self.cfg["accounts"][platform] = {k: v for k, v in old.items() if k in ("client_id", "client_secret")}
            self.toast(self.t("chat_auth_failed", platform=self.platform_name(platform)), "warn")
        elif result != old:
            self.cfg["accounts"][platform] = result
        else:
            return
        config.save(self.cfg)
        self.restart_connection(platform)

    # =====================================================
    # Fermeture
    # =====================================================
    def on_close(self):
        try:
            if self.state() == "normal":
                self.cfg["geometry"] = self.geometry()
            self.save_tabs()
        except (tk.TclError, OSError):
            pass
        for conn in self.conns.values():
            conn.stop()
        self.loader.shutdown()
        instance.stop()
        self.destroy()


def main(targets=()):
    core.setup_logging()
    if instance.forward(targets):
        return  # déjà ouvert : la fenêtre existante ouvre ces chats
    enable_dpi_awareness()
    set_app_id("Bulls64.StreamlinkChat")
    ChatApp(targets).mainloop()


def targets_from_argv(argv):
    """--open twitch:eslcs --open kick:xqc, ou des liens en arguments."""
    out = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--open" and args:
            a = args.pop(0)
        elif a.startswith("--"):
            continue
        target = config.parse_target(a)
        if target:
            out.append(target)
    return out


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main(targets_from_argv(sys.argv[1:]))
