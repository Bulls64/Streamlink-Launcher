"""Glisser-déposer de liens vers la fenêtre (Windows, OLE via ctypes, sans dépendance).

Une cible de dépôt OLE (IDropTarget) est enregistrée sur la fenêtre principale. Elle accepte :
  - un lien glissé depuis la barre d'adresse ou un onglet d'un navigateur,
  - du texte sélectionné puis glissé,
  - des fichiers (raccourcis Internet .url, fichiers texte).

RÈGLE : les rappels OLE ne touchent JAMAIS à Tk. Ils déposent des événements dans la file
`push` (deque.append) ; la boucle Tk les relit toutes les 100 ms (comme pour l'icône de zone
de notification). Événements : ("enter",) ("leave",) ("text", str) ("files", [chemins]).
Hors Windows, la classe existe mais ne fait rien (register() renvoie False).

Drag and drop of links onto the window (Windows, OLE via ctypes, no dependency).

An OLE drop target (IDropTarget) is registered on the main window. It accepts:
  - a link dragged from a browser's address bar or tab,
  - selected text, then dragged,
  - files (.url Internet shortcuts, text files).

RULE: the OLE callbacks NEVER touch Tk. They drop events into the `push`
queue (deque.append); the Tk loop reads them every 100 ms (as for the notification
area icon). Events: ("enter",) ("leave",) ("text", str) ("files", [paths]).
Outside Windows, the class exists but does nothing (register() returns False).
"""
import logging
import os

log = logging.getLogger("streamlink_launcher")

FORMAT_URL_W = "UniformResourceLocatorW"
FORMAT_URL_A = "UniformResourceLocator"

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT, CF_HDROP = 13, 15
    TYMED_HGLOBAL = 1
    DROPEFFECT_NONE, DROPEFFECT_COPY = 0, 1
    S_OK, E_NOINTERFACE = 0, -2147467262  # 0x80004002
    HRESULT = ctypes.c_long

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort),
                    ("d", ctypes.c_ubyte * 8)]

    def _guid(text):
        g = GUID()
        ole32.CLSIDFromString(text, ctypes.byref(g))
        return bytes(g)

    class POINTL(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class FORMATETC(ctypes.Structure):
        _fields_ = [("cfFormat", ctypes.c_ushort), ("ptd", ctypes.c_void_p), ("dwAspect", wintypes.DWORD),
                    ("lindex", ctypes.c_long), ("tymed", wintypes.DWORD)]

    class STGMEDIUM(ctypes.Structure):
        _fields_ = [("tymed", wintypes.DWORD), ("handle", ctypes.c_void_p), ("pUnkForRelease", ctypes.c_void_p)]

    ole32 = ctypes.WinDLL("ole32")
    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    shell32 = ctypes.WinDLL("shell32")

    ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
    ole32.CLSIDFromString.restype = HRESULT
    ole32.OleInitialize.argtypes = [ctypes.c_void_p]
    ole32.OleInitialize.restype = HRESULT
    ole32.RegisterDragDrop.argtypes = [wintypes.HWND, ctypes.c_void_p]
    ole32.RegisterDragDrop.restype = HRESULT
    ole32.RevokeDragDrop.argtypes = [wintypes.HWND]
    ole32.RevokeDragDrop.restype = HRESULT
    ole32.ReleaseStgMedium.argtypes = [ctypes.c_void_p]
    ole32.ReleaseStgMedium.restype = None
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT

    _VP = ctypes.c_void_p
    _QI = ctypes.WINFUNCTYPE(HRESULT, _VP, _VP, ctypes.POINTER(_VP))
    _REF = ctypes.WINFUNCTYPE(ctypes.c_ulong, _VP)
    _ENTER = ctypes.WINFUNCTYPE(HRESULT, _VP, _VP, wintypes.DWORD, POINTL, ctypes.POINTER(wintypes.DWORD))
    _OVER = ctypes.WINFUNCTYPE(HRESULT, _VP, wintypes.DWORD, POINTL, ctypes.POINTER(wintypes.DWORD))
    _LEAVE = ctypes.WINFUNCTYPE(HRESULT, _VP)
    _GETDATA = ctypes.WINFUNCTYPE(HRESULT, _VP, ctypes.POINTER(FORMATETC), ctypes.POINTER(STGMEDIUM))
    _QUERY = ctypes.WINFUNCTYPE(HRESULT, _VP, ctypes.POINTER(FORMATETC))

    def _call(obj, index, proto, *args):
        """Appelle la méthode n° `index` de la table virtuelle d'un objet COM.

        Calls method number `index` of a COM object's virtual table."""
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(_VP)))[0]
        return proto(vtbl[index])(obj, *args)

    def _fmt(cf):
        return FORMATETC(cf, None, 1, -1, TYMED_HGLOBAL)

    def _hglobal(data_obj, cf):
        """Contenu (octets) d'un format HGLOBAL de l'objet de données, ou None.

        Content (bytes) of an HGLOBAL format of the data object, or None."""
        fe, sm = _fmt(cf), STGMEDIUM()
        if _call(data_obj, 3, _GETDATA, ctypes.byref(fe), ctypes.byref(sm)) != S_OK:
            return None
        try:
            if sm.tymed != TYMED_HGLOBAL or not sm.handle:
                return None
            ptr = kernel32.GlobalLock(sm.handle)
            if not ptr:
                return None
            try:
                return ctypes.string_at(ptr, min(kernel32.GlobalSize(sm.handle), 1 << 20))
            finally:
                kernel32.GlobalUnlock(sm.handle)
        finally:
            ole32.ReleaseStgMedium(ctypes.byref(sm))

    def _has(data_obj, cf):
        return _call(data_obj, 5, _QUERY, ctypes.byref(_fmt(cf))) == S_OK

    def _files(data_obj):
        fe, sm = _fmt(CF_HDROP), STGMEDIUM()
        if _call(data_obj, 3, _GETDATA, ctypes.byref(fe), ctypes.byref(sm)) != S_OK:
            return []
        try:
            n = shell32.DragQueryFileW(sm.handle, 0xFFFFFFFF, None, 0)
            out = []
            for i in range(min(n, 20)):
                buf = ctypes.create_unicode_buffer(1024)
                if shell32.DragQueryFileW(sm.handle, i, buf, 1024):
                    out.append(buf.value)
            return out
        finally:
            ole32.ReleaseStgMedium(ctypes.byref(sm))

    def _as_ptr(data_obj):
        return data_obj if isinstance(data_obj, ctypes.c_void_p) else ctypes.c_void_p(data_obj)

    def read_data_object(data_obj):
        """-> ("text", str) | ("files", [chemins]) | None, en lisant un IDataObject.
        Ordre : lien (Unicode puis ANSI, glissé depuis un navigateur), texte, puis fichiers.

        -> ("text", str) | ("files", [paths]) | None, by reading an IDataObject.
        Order: link (Unicode then ANSI, dragged from a browser), text, then files."""
        data_obj = _as_ptr(data_obj)
        for cf, encoding in ((user32.RegisterClipboardFormatW(FORMAT_URL_W), "utf-16-le"),
                             (user32.RegisterClipboardFormatW(FORMAT_URL_A), "cp1252"),
                             (CF_UNICODETEXT, "utf-16-le")):
            raw = _hglobal(data_obj, cf)
            text = raw.decode(encoding, "ignore").split("\0")[0].strip() if raw else ""
            if text:
                return ("text", text)
        files = _files(data_obj)
        return ("files", files) if files else None

    def accepts(data_obj):
        data_obj = _as_ptr(data_obj)
        formats = (user32.RegisterClipboardFormatW(FORMAT_URL_W), CF_UNICODETEXT, CF_HDROP)
        return any(_has(data_obj, cf) for cf in formats)

    class DropTarget:
        """Cible de dépôt OLE enregistrée sur une fenêtre de premier niveau.

        OLE drop target registered on a top-level window."""

        def __init__(self, hwnd, push):
            self.hwnd, self.push = hwnd, push
            self.registered = False
            self._ok = False
            self._refs = 1
            self._iid = {_guid("{00000000-0000-0000-C000-000000000046}"),
                         _guid("{00000122-0000-0000-C000-000000000046}")}
            self._cb = (_QI(self._query), _REF(self._add), _REF(self._release),
                        _ENTER(self._enter), _OVER(self._over), _LEAVE(self._leave),
                        _ENTER(self._drop))
            self._vtbl = (_VP * 7)(*[ctypes.cast(c, _VP) for c in self._cb])
            self._obj = _VP(ctypes.addressof(self._vtbl))

        # --- méthodes COM (jamais de Tk ici) ---
        # --- COM methods (never any Tk here) ---
        def _query(self, this, riid, ppv):
            try:
                if bytes(ctypes.cast(riid, ctypes.POINTER(GUID))[0]) in self._iid:
                    ppv[0] = this
                    self._refs += 1
                    return S_OK
            except Exception:
                log.debug("erreur ignorée", exc_info=True)
            ppv[0] = None
            return E_NOINTERFACE

        def _add(self, this):
            self._refs += 1
            return self._refs

        def _release(self, this):
            self._refs = max(1, self._refs - 1)
            return self._refs

        def _enter(self, this, data_obj, keys, pt, effect):
            try:
                self._ok = bool(data_obj) and accepts(data_obj)
            except Exception:
                log.exception("drag enter")
                self._ok = False
            effect[0] = DROPEFFECT_COPY if self._ok else DROPEFFECT_NONE
            if self._ok:
                self.push(("enter",))
            return S_OK

        def _over(self, this, keys, pt, effect):
            effect[0] = DROPEFFECT_COPY if self._ok else DROPEFFECT_NONE
            return S_OK

        def _leave(self, this):
            if self._ok:
                self.push(("leave",))
            self._ok = False
            return S_OK

        def _drop(self, this, data_obj, keys, pt, effect):
            effect[0] = DROPEFFECT_NONE
            try:
                got = read_data_object(data_obj) if data_obj else None
                if got:
                    effect[0] = DROPEFFECT_COPY
                    self.push(got)
            except Exception:
                log.exception("drop")
            self.push(("leave",))
            self._ok = False
            return S_OK

        # --- cycle de vie ---
        # --- life cycle ---
        def register(self):
            try:
                hr = ole32.OleInitialize(None)          # S_OK / S_FALSE (déjà fait) : tous deux acceptables
                                                        # S_OK / S_FALSE (already done): both acceptable
                if hr not in (0, 1):
                    log.warning("OleInitialize: 0x%08X", hr & 0xFFFFFFFF)
                    return False
                hr = ole32.RegisterDragDrop(self.hwnd, ctypes.byref(self._obj))
                self.registered = hr == S_OK
                if not self.registered:
                    log.warning("RegisterDragDrop: 0x%08X", hr & 0xFFFFFFFF)
            except Exception:
                log.exception("register drop target")
                self.registered = False
            return self.registered

        def revoke(self):
            if self.registered:
                try:
                    ole32.RevokeDragDrop(self.hwnd)
                except Exception:
                    log.debug("erreur ignorée", exc_info=True)
                self.registered = False

    def toplevel_hwnd(widget):
        """HWND de la fenêtre de premier niveau d'un widget Tk.

        HWND of the top-level window of a Tk widget."""
        wid = widget.winfo_id()
        return user32.GetParent(wid) or wid

else:
    def accepts(data_obj):
        return False

    def read_data_object(data_obj):
        return None

    class DropTarget:
        def __init__(self, hwnd, push):
            self.hwnd, self.push, self.registered = hwnd, push, False

        def register(self):
            return False

        def revoke(self):
            pass

    def toplevel_hwnd(widget):
        return widget.winfo_id()
