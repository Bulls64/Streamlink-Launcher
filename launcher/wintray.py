"""Icône dans la zone de notification + raccourci clavier global (Windows, sans dépendance).

Une petite fenêtre Windows invisible reçoit les clics sur l'icône et le raccourci. La boucle de Tk
distribue déjà les messages Windows de son thread, donc aucun thread supplémentaire n'est nécessaire.
Les actions sont transmises à l'interface via 'callback(nom)' ; tout échec est silencieux.
"""
import os
import logging
import ctypes

_log = logging.getLogger("streamlink_launcher")

if os.name == "nt":
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                    ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                    ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    # Signatures explicites (indispensable en 64 bits)
    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  wintypes.UINT]
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      wintypes.HWND, wintypes.LPVOID]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.RegisterWindowMessageW.restype = wintypes.UINT
    user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32_le = ctypes.WinDLL("kernel32", use_last_error=True)  # pour lire GetLastError de façon fiable
    user32_le = ctypes.WinDLL("user32", use_last_error=True)
    user32_le.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32_le.RegisterHotKey.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, wintypes.LPVOID]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.SetActiveWindow.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32_le.CreateMutexW.restype = wintypes.HANDLE
    kernel32_le.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]

WM_USER = 0x0400
WM_TRAY = WM_USER + 20
WM_SHOW_EXISTING = WM_USER + 21
WM_HOTKEY = 0x0312
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
NIN_BALLOONUSERCLICK = WM_USER + 5
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_USER, NIIF_LARGE_ICON = 0x4, 0x20
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK_SPACE = 0x20
# Raccourcis proposés : id -> (modificateurs, touche, libellé)
HOTKEYS = {
    "ctrl+alt+s": (MOD_CONTROL | MOD_ALT, ord("S"), "Ctrl+Alt+S"),
    "ctrl+alt+space": (MOD_CONTROL | MOD_ALT, VK_SPACE, "Ctrl+Alt+Space"),
    "ctrl+shift+space": (MOD_CONTROL | MOD_SHIFT, VK_SPACE, "Ctrl+Shift+Space"),
    "alt+shift+s": (MOD_ALT | MOD_SHIFT, ord("S"), "Alt+Shift+S"),
    "ctrl+alt+l": (MOD_CONTROL | MOD_ALT, ord("L"), "Ctrl+Alt+L"),
}
DEFAULT_HOTKEY = "ctrl+alt+s"
ERROR_HOTKEY_ALREADY_REGISTERED = 1409


def hotkey_label(combo):
    return HOTKEYS.get(combo, HOTKEYS[DEFAULT_HOTKEY])[2]
MF_STRING, MF_SEPARATOR, MF_GRAYED = 0x0, 0x800, 0x1
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY = 0x2, 0x100, 0x80
IMAGE_ICON, LR_LOADFROMFILE = 1, 0x10
HOTKEY_ID = 1
CLASS_NAME = "StreamlinkLauncherTray"


class Tray:
    """callback(event) reçoit : 'open', 'menu', 'balloon', 'hotkey'.

    Attention : callback est appelé depuis la procédure de fenêtre Windows, pendant que Tkinter traite
    ses propres messages. Il ne doit JAMAIS appeler Tkinter (pas même after()) : seulement déposer
    l'événement quelque part (ex. deque.append), à relire depuis la boucle Tk."""

    def __init__(self, callback, icon_path=None, tooltip="Streamlink Launcher"):
        self.callback = callback
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.hwnd = None
        self.icon_shown = False
        self.hotkey = False
        self.hotkey_combo = None
        self.hotkey_error = 0
        self._hicon = None
        self._proc = None
        self._hinst = None
        self._taskbar_created = 0

    @property
    def available(self):
        return self.hwnd is not None

    def start(self):
        if os.name != "nt":
            return False
        try:
            self._hinst = kernel32.GetModuleHandleW(None)
            self._proc = WNDPROC(self._wndproc)  # garder une référence : sinon le callback est libéré
            wc = WNDCLASSW()
            wc.lpfnWndProc = self._proc
            wc.hInstance = self._hinst
            wc.lpszClassName = CLASS_NAME
            user32.RegisterClassW(ctypes.byref(wc))  # échoue sans gravité si déjà enregistrée
            self.hwnd = user32.CreateWindowExW(0, CLASS_NAME, "Streamlink Launcher", 0, 0, 0, 0, 0,
                                               None, None, self._hinst, None)
            if not self.hwnd:
                self.hwnd = None
                return False
            self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
            self._hicon = self._load_icon()
            return True
        except Exception:
            self.hwnd = None
            return False

    def _load_icon(self):
        try:
            if self.icon_path and os.path.isfile(self.icon_path):
                h = user32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
                if h:
                    return h
        except Exception:
            pass
        return user32.LoadIconW(None, ctypes.c_void_p(32512))  # IDI_APPLICATION

    def _nid(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = self.tooltip[:127]
        return nid

    # --- icône
    def show_icon(self):
        if not self.available or self.icon_shown:
            return self.icon_shown
        try:
            self.icon_shown = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(
                self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP))))
        except Exception:
            self.icon_shown = False
        return self.icon_shown

    def hide_icon(self):
        if self.available and self.icon_shown:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid(0)))
            except Exception:
                pass
        self.icon_shown = False

    def set_tooltip(self, text):
        self.tooltip = text
        if self.icon_shown:
            try:
                shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid(NIF_TIP)))
            except Exception:
                pass

    def notify(self, title, body):
        """Notification Windows attachée à l'icône (cliquable). Renvoie False si impossible."""
        if not self.icon_shown:
            return False
        try:
            nid = self._nid(NIF_INFO)
            nid.szInfoTitle = title[:63]
            nid.szInfo = body[:255]
            nid.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON
            nid.hBalloonIcon = self._hicon
            return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))
        except Exception:
            return False

    # --- raccourci global
    def register_hotkey(self, combo=DEFAULT_HOTKEY):
        """Enregistre le raccourci global. En cas d'échec, hotkey_error contient le code Windows
        (1409 = déjà utilisé par une autre application)."""
        combo = combo if combo in HOTKEYS else DEFAULT_HOTKEY
        if not self.available:
            self.hotkey_error = -1
            return False
        if self.hotkey and self.hotkey_combo == combo:
            return True
        self.unregister_hotkey()
        mods, vk, _ = HOTKEYS[combo]
        try:
            ok = bool(user32_le.RegisterHotKey(self.hwnd, HOTKEY_ID, mods | MOD_NOREPEAT, vk))
            self.hotkey_error = 0 if ok else ctypes.get_last_error()
        except Exception:
            ok, self.hotkey_error = False, -2
        self.hotkey = ok
        self.hotkey_combo = combo if ok else None
        return ok

    def unregister_hotkey(self):
        if self.available and self.hotkey:
            try:
                user32.UnregisterHotKey(self.hwnd, HOTKEY_ID)
            except Exception:
                pass
        self.hotkey = False
        self.hotkey_combo = None

    # --- menu contextuel natif
    def show_menu(self, items):
        """items : [(id, libellé, défaut: bool)] ou None pour un séparateur. Renvoie l'id choisi ou 0."""
        if not self.available:
            return 0
        menu = None
        try:
            menu = user32.CreatePopupMenu()
            for item in items:
                if item is None:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                    continue
                cmd, label, default = item
                user32.AppendMenuW(menu, MF_STRING, cmd, label)
                if default:
                    user32.SetMenuDefaultItem(menu, cmd, 0)
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self.hwnd)
            chosen = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0,
                                           self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
            return chosen
        except Exception:
            return 0
        finally:
            if menu:
                user32.DestroyMenu(menu)

    def stop(self):
        self.unregister_hotkey()
        self.hide_icon()
        if self.available:
            try:
                user32.DestroyWindow(self.hwnd)
                user32.UnregisterClassW(CLASS_NAME, self._hinst)
            except Exception:
                pass
        self.hwnd = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                event = lparam & 0xFFFF
                if event == WM_LBUTTONUP:
                    self.callback("open")
                elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self.callback("menu")
                elif event == NIN_BALLOONUSERCLICK:
                    self.callback("balloon")
                return 0
            if msg == WM_SHOW_EXISTING:
                self.callback("open")
                return 0
            if msg == WM_HOTKEY and wparam == HOTKEY_ID:
                self.callback("hotkey")
                return 0
            if self._taskbar_created and msg == self._taskbar_created and self.icon_shown:
                self.icon_shown = False   # l'Explorateur a redémarré : on remet l'icône
                self.show_icon()
                return 0
        except Exception as e:  # une erreur ici ne doit jamais remonter dans la boucle de messages Windows
            _log.warning("Message Windows ignoré : %s", e)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def bring_to_front(win):
    """Met une fenêtre Tk au premier plan, même si une autre application avait le focus
    (Windows bloque sinon SetForegroundWindow : la fenêtre s'ouvrirait sans le focus clavier)."""
    if os.name != "nt":
        return False
    try:
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        current = kernel32.GetCurrentThreadId()
        foreground = user32.GetForegroundWindow()
        other = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        attached = bool(other and other != current and user32.AttachThreadInput(other, current, True))
        try:
            user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
            user32.BringWindowToTop(hwnd)
            ok = bool(user32.SetForegroundWindow(hwnd))
            user32.SetActiveWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(other, current, False)
        return ok
    except Exception:
        return False


# ---------------------
# Démarrage avec Windows (clé « Run » de l'utilisateur)
# ---------------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "StreamlinkLauncher"


def autostart_command(script_path, python_exe):
    import sys
    if getattr(sys, "frozen", False):  # version .exe : on lance l'exécutable lui-même
        return f'"{sys.executable}" --tray'
    folder = os.path.dirname(python_exe)
    pythonw = os.path.join(folder, "pythonw.exe")
    exe = pythonw if os.path.isfile(pythonw) else python_exe
    return f'"{exe}" "{script_path}" --tray'


def set_autostart(enabled, script_path, python_exe):
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, autostart_command(script_path, python_exe))
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


# ---------------------
# Une seule instance (Windows)
# ---------------------
_mutex = None


def acquire_single_instance():
    """True si c'est la première instance. Sinon, demande à l'instance déjà ouverte d'afficher
    sa fenêtre et renvoie False (si elle ne répond pas, on la laisse et on démarre quand même)."""
    global _mutex
    if os.name != "nt":
        return True
    try:
        _mutex = kernel32_le.CreateMutexW(None, False, "Local\\StreamlinkLauncherSingleton")
        if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
            return True
        hwnd = user32.FindWindowW(CLASS_NAME, None)
        if hwnd:
            user32.PostMessageW(hwnd, WM_SHOW_EXISTING, 0, 0)
            return False
    except Exception as e:
        _log.warning("Contrôle d'instance unique impossible : %s", e)
    return True
