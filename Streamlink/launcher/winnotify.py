"""Notifications Windows sans dépendance : toast natif (via Windows PowerShell) et clignotement
de la barre des tâches. Tout est ignoré silencieusement hors de Windows ou en cas d'échec."""
import os
import subprocess

# Script lancé seulement au début d'un live (rare) ; le texte passe par des variables d'environnement
# pour éviter tout problème de guillemets.
_TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$tpl = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$txt = $tpl.GetElementsByTagName('text')
$txt.Item(0).AppendChild($tpl.CreateTextNode($env:SLL_TITLE)) > $null
$txt.Item(1).AppendChild($tpl.CreateTextNode($env:SLL_BODY)) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($tpl)
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def toast(title, body):
    """Affiche une notification Windows. Renvoie True si la commande a pu être lancée."""
    if os.name != "nt":
        return False
    try:
        env = dict(os.environ, SLL_TITLE=title[:120], SLL_BODY=body[:240])
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                          "-Command", _TOAST_SCRIPT], env=env, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def flash_taskbar(win, count=3):
    """Fait clignoter le bouton de la fenêtre dans la barre des tâches (si elle n'a pas le focus)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x2 | 0xC, count, 0)  # TRAY | TIMERNOFG
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass
