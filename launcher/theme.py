"""Couleurs, polices et réglages de fenêtre propres à Windows (tous facultatifs ailleurs).

Colors, fonts and window settings specific to Windows (all optional elsewhere)."""
import logging
import os
import tkinter.font as tkfont

log = logging.getLogger("streamlink_launcher")


# ---------------------
# Couleurs
# Colors
# ---------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(a, b, t):
    """Mélange a vers b (t = 0 -> a, t = 1 -> b).

    Blends a towards b (t = 0 -> a, t = 1 -> b)."""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def luminance(h):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hex_to_rgb(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


class Palette(dict):
    __getattr__ = dict.__getitem__

    def hover(self, base):
        return mix(base, "#808080", 0.14)


_BASE = {
    "dark": {
        "bg": "#141518", "title": "#101114", "surface": "#1C1D21", "surface_hover": "#222328",
        "field": "#1F2025", "raised": "#24262B", "seg_sel": "#3A3C43", "panel": "#1A1B1F",
        "popover": "#202126", "border": "#2E3037", "border_strong": "#3E414A",
        "text": "#EDEDEF", "muted": "#A1A3AB", "faint": "#8B8E97", "log_bg": "#0E0F11",
        "ok": "#3DD68C", "warn": "#F5A524", "error": "#F87171", "switch_off": "#3A3C43",
        "knob": "#FFFFFF", "scroll": "#3A3C43", "focus": "#C9B3FF",
    },
    "light": {
        "bg": "#F7F7F8", "title": "#EEEEF1", "surface": "#FFFFFF", "surface_hover": "#F4F4F6",
        "field": "#FFFFFF", "raised": "#ECECEF", "seg_sel": "#FFFFFF", "panel": "#FFFFFF",
        "popover": "#FFFFFF", "border": "#E0E1E5", "border_strong": "#C9CBD1",
        "text": "#17181B", "muted": "#5D5F67", "faint": "#6B6E76", "log_bg": "#FFFFFF",
        "ok": "#13804B", "warn": "#B45309", "error": "#C42B1C", "switch_off": "#C9CBD1",
        "knob": "#FFFFFF", "scroll": "#C9CBD1", "focus": "#5B2BB5",
    },
}


def palette(mode):
    p = Palette(_BASE["light" if mode == "light" else "dark"])
    p["mode"] = "light" if mode == "light" else "dark"
    p["dark"] = p["mode"] == "dark"
    p["popover_hover"] = mix(p["popover"], "#808080", 0.16)
    p["panel_hover"] = mix(p["panel"], "#808080", 0.12)
    return p


def accent_ring(color, bg):
    """Halo autour du champ actif (accent à ~28 % sur le fond).

    Halo around the active field (accent at ~28% over the background)."""
    return mix(bg, color, 0.30)


def readable_on(bg, color):
    """Version de 'color' suffisamment contrastée sur 'bg' (pour un texte d'action).

    Version of 'color' with enough contrast on 'bg' (for an action text)."""
    dark_bg = luminance(bg) < 0.4
    return mix(color, "#FFFFFF" if dark_bg else "#000000", 0.45)


def system_theme():
    if os.name == "nt":
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                value, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return "light" if value else "dark"
        except OSError:
            pass
    return "dark"


def resolve_theme(setting):
    return system_theme() if setting == "auto" else ("light" if setting == "light" else "dark")


# ---------------------
# Polices
# Fonts
# ---------------------
SANS = ["Segoe UI Variable Text", "Segoe UI", "Figtree", "Inter", "Helvetica Neue", "DejaVu Sans"]
SEMIBOLD = ["Segoe UI Variable Text Semibold", "Segoe UI Semibold"]
DISPLAY = ["Segoe UI Variable Display Semib", "Segoe UI Variable Display Semibold", "Segoe UI Semibold"]
MONO = ["Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"]
ICONS = ["Segoe Fluent Icons", "Segoe MDL2 Assets"]


class CachedFont(tkfont.Font):
    """Police dont les mesures de texte sont mémorisées.

    Chaque measure() est un aller-retour vers Tk ; or les mêmes textes (noms de chaînes, libellés) sont
    mesurés à chaque dessin. Les polices de l'application ne changent jamais de taille après leur
    création (une nouvelle échelle recrée l'objet Fonts), le cache reste donc juste.

    Font whose text measurements are memorized.

    Each measure() is a round trip to Tk; yet the same texts (channel names, labels) are
    measured at every drawing. The application's fonts never change size after their
    creation (a new scale recreates the Fonts object), so the cache stays correct.
    """

    _CACHE_MAX = 4000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._widths = {}

    def measure(self, text, displayof=None):
        if displayof is not None:
            return super().measure(text, displayof)
        width = self._widths.get(text)
        if width is None:
            if len(self._widths) >= self._CACHE_MAX:
                self._widths.clear()
            width = self._widths[text] = super().measure(text)
        return width


class Fonts:
    def __init__(self, root, px):
        families = set(tkfont.families(root))

        def pick(candidates):
            return next((f for f in candidates if f in families), None)

        sans = pick(SANS) or tkfont.nametofont("TkDefaultFont").actual("family")
        semi = pick(SEMIBOLD)
        display = pick(DISPLAY)
        mono = pick(MONO) or tkfont.nametofont("TkFixedFont").actual("family")
        self.icon_family = pick(ICONS)
        self.fluent = self.icon_family == "Segoe Fluent Icons"
        self._root, self._icons = root, {}

        def regular(size):
            return CachedFont(root=root, family=sans, size=-px(size))

        def semibold(size):
            if semi:
                return CachedFont(root=root, family=semi, size=-px(size))
            return CachedFont(root=root, family=sans, size=-px(size), weight="bold")

        self.title = (CachedFont(root=root, family=display, size=-px(21)) if display else semibold(21))
        self.panel_title = semibold(18)
        self.field = regular(15)
        self.button = semibold(15)
        self.body = regular(14)
        self.body_semi = semibold(14)
        self.card_title = semibold(15)
        self.small = regular(13)
        self.small_semi = semibold(13)
        self.tiny = regular(12)
        self.caps = semibold(11)
        self.mono = CachedFont(root=root, family=mono, size=-px(12))
        self.mono_field = CachedFont(root=root, family=mono, size=-px(13))

    def icon(self, size_px):
        if not self.icon_family:
            return None
        font = self._icons.get(size_px)
        if font is None:
            font = self._icons[size_px] = CachedFont(root=self._root, family=self.icon_family, size=-size_px)
        return font


def fit_text(font, text, width):
    """Coupe le texte avec « … » pour qu'il tienne dans 'width' pixels.

    Cuts the text with "…" so that it fits in 'width' pixels."""
    text = text or ""
    if font.measure(text) <= width:
        return text
    # Plus long préfixe qui tient avec « … » : recherche dichotomique (quelques mesures au lieu d'une
    # par caractère retiré). La largeur croît avec la longueur du préfixe, le résultat est donc le même.
    # Longest prefix that fits with "…": binary search (a few measurements instead of one
    # per removed character). The width grows with the prefix length, so the result is the same.
    lo, hi = 0, len(text) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + "…") <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + "…" if lo else ""


# ---------------------
# Windows : DPI, barre de titre, identité de l'application
# Windows: DPI, title bar, application identity
# ---------------------
def enable_dpi_awareness():
    if os.name != "nt":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            log.debug("erreur ignorée", exc_info=True)


def set_app_id(app_id="Chris.StreamlinkLauncher"):
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        log.debug("erreur ignorée", exc_info=True)


def _colorref(h):
    r, g, b = hex_to_rgb(h)
    return (b << 16) | (g << 8) | r


def apply_window_chrome(win, dark, border=None, caption=None, text=None):
    """Barre de titre sombre/claire, coins arrondis et couleurs (Windows 10/11, ignoré ailleurs).

    Dark/light title bar, rounded corners and colors (Windows 10/11, ignored elsewhere)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi

        def set_attr(attr, value):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        set_attr(20, 1 if dark else 0)   # DWMWA_USE_IMMERSIVE_DARK_MODE
        set_attr(19, 1 if dark else 0)   # idem, anciennes versions de Windows 10
                                         # same, older versions of Windows 10
        set_attr(33, 2)                  # coins arrondis (Windows 11)
                                         # rounded corners (Windows 11)
        if border:
            set_attr(34, _colorref(border))   # couleur de bordure (Windows 11)
                                              # border color (Windows 11)
        if caption:
            set_attr(35, _colorref(caption))  # couleur de la barre de titre (Windows 11)
                                              # title bar color (Windows 11)
        if text:
            set_attr(36, _colorref(text))
    except Exception:
        log.debug("erreur ignorée", exc_info=True)
