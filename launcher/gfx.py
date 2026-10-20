"""Dessin : rectangles arrondis lissés (coins pré-calculés et mis en cache) et icônes.

Drawing: smooth rounded rectangles (corners precomputed and cached) and icons."""
import math
import tkinter as tk

from .theme import hex_to_rgb

_SAMPLES = (0.125, 0.375, 0.625, 0.875)  # suréchantillonnage 4x4
                                         # 4x4 supersampling


def _tri_crosses(tri, i, j):
    """Un sommet du triangle tombe-t-il dans le pixel (i, j) ? (le triangle pourrait alors l'entamer
    sans qu'aucun coin du pixel soit dedans).

    Does a vertex of the triangle fall inside pixel (i, j)? (the triangle could then cut into it
    without any corner of the pixel being inside)."""
    return any(i <= x <= i + 1 and j <= y <= j + 1 for x, y in tri)


class Painter:
    """Les coins sont de petites images (r x r) où la couleur du fond est déjà mélangée :
    pas de transparence, donc rapide et identique sur toutes les versions de Tk.

    The corners are small images (r x r) where the background color is already blended in:
    no transparency, so fast and identical on every version of Tk."""

    def __init__(self, root):
        self.root = root
        self._corners = {}

    def _corner(self, r, fill, outline, bg, quad, bw):
        key = (r, fill, outline, bg, quad, bw)
        img = self._corners.get(key)
        if img is not None:
            return img
        F, Oc, B = hex_to_rgb(fill), hex_to_rgb(outline), hex_to_rgb(bg)
        inner2 = (r - bw) ** 2 if r > bw else -1
        r2 = r * r
        rows = []
        for j in range(r):
            cy = (j if quad[0] == "n" else r + j) - r
            row = []
            for i in range(r):
                cx = (i if quad[1] == "w" else r + i) - r
                tr = tg = tb = 0
                for sy in _SAMPLES:
                    dy2 = (cy + sy) ** 2
                    for sx in _SAMPLES:
                        d2 = (cx + sx) ** 2 + dy2
                        col = F if d2 <= inner2 else (Oc if d2 <= r2 else B)
                        tr += col[0]
                        tg += col[1]
                        tb += col[2]
                row.append("#%02x%02x%02x" % (tr >> 4, tg >> 4, tb >> 4))
            rows.append("{" + " ".join(row) + "}")
        img = tk.PhotoImage(master=self.root, width=r, height=r)
        img.put(" ".join(rows))
        self._corners[key] = img
        return img

    def round_rect(self, cv, x0, y0, x1, y1, r, fill=None, outline=None, bg=None, bw=1, tags=()):
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            return
        bg = bg or cv.cget("bg")
        fill = fill or bg
        outline = outline or fill
        r = int(max(0, min(r, w // 2, h // 2)))
        if r == 0:
            cv.create_rectangle(x0, y0, x1, y1, fill=outline, width=0, tags=tags)
            if outline != fill:
                cv.create_rectangle(x0 + bw, y0 + bw, x1 - bw, y1 - bw, fill=fill, width=0, tags=tags)
            return
        if x1 - r > x0 + r:
            cv.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, width=0, tags=tags)
        if y1 - r > y0 + r:
            cv.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, width=0, tags=tags)
        if outline != fill:
            if x1 - r > x0 + r:
                cv.create_rectangle(x0 + r, y0, x1 - r, y0 + bw, fill=outline, width=0, tags=tags)
                cv.create_rectangle(x0 + r, y1 - bw, x1 - r, y1, fill=outline, width=0, tags=tags)
            if y1 - r > y0 + r:
                cv.create_rectangle(x0, y0 + r, x0 + bw, y1 - r, fill=outline, width=0, tags=tags)
                cv.create_rectangle(x1 - bw, y0 + r, x1, y1 - r, fill=outline, width=0, tags=tags)
        for quad, x, y in (("nw", x0, y0), ("ne", x1 - r, y0), ("sw", x0, y1 - r), ("se", x1 - r, y1 - r)):
            cv.create_image(x, y, image=self._corner(r, fill, outline, bg, quad, bw), anchor="nw", tags=tags)

    def circle(self, cv, cx, cy, d, color, bg=None, outline=None, tags=()):
        x0 = int(round(cx - d / 2))
        y0 = int(round(cy - d / 2))
        self.round_rect(cv, x0, y0, x0 + d, y0 + d, d // 2, color, outline or color, bg, tags=tags)

    def dashed_round_rect(self, cv, x0, y0, x1, y1, r, color, tags=()):
        x1 -= 1
        y1 -= 1
        r = int(max(1, min(r, (x1 - x0) // 2, (y1 - y0) // 2)))
        kw = {"fill": color, "dash": "-", "tags": tags}
        cv.create_line(x0 + r, y0, x1 - r, y0, **kw)
        cv.create_line(x0 + r, y1, x1 - r, y1, **kw)
        cv.create_line(x0, y0 + r, x0, y1 - r, **kw)
        cv.create_line(x1, y0 + r, x1, y1 - r, **kw)
        akw = {"style": "arc", "outline": color, "dash": "-", "tags": tags, "extent": 90}
        cv.create_arc(x0, y0, x0 + 2 * r, y0 + 2 * r, start=90, **akw)
        cv.create_arc(x1 - 2 * r, y0, x1, y0 + 2 * r, start=0, **akw)
        cv.create_arc(x0, y1 - 2 * r, x0 + 2 * r, y1, start=180, **akw)
        cv.create_arc(x1 - 2 * r, y1 - 2 * r, x1, y1, start=270, **akw)

    def app_icon(self, size, color, fg="#FFFFFF"):
        """Icône de la fenêtre : carré arrondi + triangle « lecture », lissés.

        Window icon: rounded square + "play" triangle, smoothed."""
        C, W = hex_to_rgb(color), hex_to_rgb(fg)
        r = size * 0.24
        tri = [(size * 0.38, size * 0.28), (size * 0.38, size * 0.72), (size * 0.76, size * 0.50)]

        def in_rr(x, y):
            dx = max(r - x, 0, x - (size - r))
            dy = max(r - y, 0, y - (size - r))
            return dx * dx + dy * dy <= r * r

        def in_tri(x, y):
            (ax, ay), (bx, by), (cx, cy) = tri
            d1 = (x - bx) * (ay - by) - (ax - bx) * (y - by)
            d2 = (x - cx) * (by - cy) - (bx - cx) * (y - cy)
            d3 = (x - ax) * (cy - ay) - (cx - ax) * (y - ay)
            return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

        # Pixel entièrement dans une forme convexe (ses 4 coins le sont) : tous ses sous-échantillons aussi,
        # inutile de les calculer un par un. Seuls les pixels des bords sont suréchantillonnés : même résultat.
        # Pixel entirely inside a convex shape (its 4 corners are): all its subsamples are too,
        # no need to compute them one by one. Only the edge pixels are supersampled: same result.
        def solid(i, j, inside):
            return inside(i, j) and inside(i + 1, j) and inside(i, j + 1) and inside(i + 1, j + 1)

        color_c, color_w = "#%02x%02x%02x" % C, "#%02x%02x%02x" % W
        rows, transparent = [], []
        for j in range(size):
            row = []
            for i in range(size):
                if solid(i, j, in_rr):
                    if solid(i, j, in_tri):
                        row.append(color_w)
                        continue
                    if not any(in_tri(i + a, j + b) for a in (0, 1) for b in (0, 1)) and not _tri_crosses(
                            tri, i, j):
                        row.append(color_c)
                        continue
                acc = [0.0, 0.0, 0.0]
                cover = 0
                for sy in _SAMPLES:
                    for sx in _SAMPLES:
                        x, y = i + sx, j + sy
                        if in_rr(x, y):
                            cover += 1
                            col = W if in_tri(x, y) else C
                            for k in range(3):
                                acc[k] += col[k]
                if cover:
                    row.append("#%02x%02x%02x" % tuple(int(a / cover) for a in acc))
                    if cover < 8:
                        transparent.append((i, j))
                else:
                    row.append(color_c)
                    transparent.append((i, j))
            rows.append("{" + " ".join(row) + "}")
        img = tk.PhotoImage(master=self.root, width=size, height=size)
        img.put(" ".join(rows))  # une seule écriture au lieu d'une par pixel
                                 # a single write instead of one per pixel
        for i, j in transparent:
            img.transparency_set(i, j, True)
        return img


# ---------------------
# Icônes : police Segoe Fluent Icons / MDL2 Assets (Windows), sinon dessin simple
# Icons: Segoe Fluent Icons / MDL2 Assets font (Windows), otherwise a simple drawing
# ---------------------
GLYPHS = {
    "search": "", "play": "", "play_fill": "", "settings": "",
    "history": "", "chevron_down": "", "chevron_up": "", "more": "",
    "add": "", "stop": "", "close": "", "star": "", "star_fill": "",
    "check": "", "folder": "", "delete": "", "warning": "", "link": "",
    "arrow_up": "\ue74a", "sync": "\ue895",
}


def draw_icon(cv, fonts, name, x, y, size, color, tags=()):
    if fonts.icon_family:
        glyph = GLYPHS.get(name, "")
        if name == "play_fill" and not fonts.fluent:
            glyph = GLYPHS["play"]
        cv.create_text(x, y, text=glyph, font=fonts.icon(int(size)), fill=color, anchor="center", tags=tags)
        return
    _draw_fallback(cv, name, x, y, size, color, tags)


def _draw_fallback(cv, name, x, y, s, color, tags):
    w = max(1, round(s / 11))
    line = {"fill": color, "width": w, "capstyle": "round", "joinstyle": "round", "tags": tags}
    h = s / 2
    if name == "search":
        r = s * 0.32
        cx, cy = x - s * 0.08, y - s * 0.08
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=w, tags=tags)
        cv.create_line(cx + r * 0.72, cy + r * 0.72, x + h * 0.85, y + h * 0.85, **line)
    elif name in ("play", "play_fill"):
        pts = [x - s * 0.28, y - s * 0.38, x - s * 0.28, y + s * 0.38, x + s * 0.38, y]
        if name == "play_fill":
            cv.create_polygon(*pts, fill=color, outline=color, tags=tags)
        else:
            cv.create_polygon(*pts, fill="", outline=color, width=w, joinstyle="round", tags=tags)
    elif name == "settings":
        r1, r2 = s * 0.17, s * 0.36
        cv.create_oval(x - r1, y - r1, x + r1, y + r1, outline=color, width=w, tags=tags)
        cv.create_oval(x - r2, y - r2, x + r2, y + r2, outline=color, width=w, tags=tags)
        for k in range(8):
            a = k * math.pi / 4
            cv.create_line(x + math.cos(a) * r2, y + math.sin(a) * r2,
                           x + math.cos(a) * (r2 + s * 0.12), y + math.sin(a) * (r2 + s * 0.12), **line)
    elif name == "history":
        r = s * 0.4
        cv.create_arc(x - r, y - r, x + r, y + r, start=200, extent=-320, style="arc", outline=color, width=w,
                      tags=tags)
        cv.create_line(x, y - r * 0.55, x, y, x + r * 0.45, y + r * 0.3, **line)
    elif name in ("chevron_down", "chevron_up"):
        d = 1 if name == "chevron_down" else -1
        cv.create_line(x - s * 0.32, y - d * s * 0.15, x, y + d * s * 0.17, x + s * 0.32, y - d * s * 0.15, **line)
    elif name == "more":
        r = max(1, s * 0.07)
        for dx in (-s * 0.3, 0, s * 0.3):
            cv.create_oval(x + dx - r, y - r, x + dx + r, y + r, fill=color, outline=color, tags=tags)
    elif name == "add":
        cv.create_line(x - s * 0.36, y, x + s * 0.36, y, **line)
        cv.create_line(x, y - s * 0.36, x, y + s * 0.36, **line)
    elif name == "stop":
        cv.create_rectangle(x - s * 0.3, y - s * 0.3, x + s * 0.3, y + s * 0.3, fill=color, outline=color, tags=tags)
    elif name == "close":
        cv.create_line(x - s * 0.3, y - s * 0.3, x + s * 0.3, y + s * 0.3, **line)
        cv.create_line(x + s * 0.3, y - s * 0.3, x - s * 0.3, y + s * 0.3, **line)
    elif name in ("star", "star_fill"):
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = s * 0.45 if k % 2 == 0 else s * 0.2
            pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
        cv.create_polygon(*pts, fill=color if name == "star_fill" else "", outline=color, width=w, tags=tags)
    elif name == "check":
        cv.create_line(x - s * 0.35, y, x - s * 0.1, y + s * 0.27, x + s * 0.38, y - s * 0.27, **line)
    elif name == "folder":
        cv.create_polygon(x - s * 0.42, y - s * 0.3, x - s * 0.1, y - s * 0.3, x, y - s * 0.18, x + s * 0.42,
                          y - s * 0.18, x + s * 0.42, y + s * 0.32, x - s * 0.42, y + s * 0.32, fill="",
                          outline=color, width=w, tags=tags)
    elif name == "delete":
        cv.create_line(x - s * 0.38, y - s * 0.28, x + s * 0.38, y - s * 0.28, **line)
        cv.create_rectangle(x - s * 0.26, y - s * 0.28, x + s * 0.26, y + s * 0.4, outline=color, width=w, tags=tags)
    elif name == "warning":
        cv.create_polygon(x, y - s * 0.4, x + s * 0.42, y + s * 0.35, x - s * 0.42, y + s * 0.35, fill="",
                          outline=color, width=w, tags=tags)
        cv.create_line(x, y - s * 0.1, x, y + s * 0.1, **line)
    elif name == "arrow_up":
        cv.create_line(x, y + s * 0.36, x, y - s * 0.32, **line)
        cv.create_line(x - s * 0.28, y - s * 0.06, x, y - s * 0.36, x + s * 0.28, y - s * 0.06, **line)
    elif name == "sync":
        r = s * 0.36
        cv.create_arc(x - r, y - r, x + r, y + r, start=30, extent=280, style="arc", outline=color, width=w, tags=tags)
    elif name == "link":
        cv.create_line(x - s * 0.3, y + s * 0.3, x + s * 0.3, y - s * 0.3, **line)
