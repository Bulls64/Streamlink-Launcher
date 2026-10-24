"""Mises à jour : version de Streamlink, mise à jour du lanceur depuis les releases GitHub.

Updates: Streamlink version, updating the launcher from the GitHub releases.

Mixin de App (voir app.py) : ces méthodes utilisent self comme la fenêtre principale.
Mixin of App (see app.py): these methods use self as the main window."""
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from . import core, updater, wintray


class UpdatesMixin:
    # --- Streamlink : version et mises à jour
    # --- Streamlink: version and updates
    def _update_sl_card(self, busy=False):
        t = self.t
        try:
            if not hasattr(self, "sl_card") or not self.sl_card.winfo_exists():
                return
        except tk.TclError:
            return
        path = core.find_streamlink(self.v_streamlink.get().strip())
        card = self.sl_card
        if busy:
            card.set_state(True, t("sl_checking"), path or "", button=t("btn_check"), level="busy")
            return
        if not path:
            card.set_state(False, t("sl_missing"), t("sl_missing_detail"), button=t("btn_install"))
            return
        r = self.sl_update if self.sl_update and self.sl_update.get("path") == path else None
        if r and r.get("update"):
            card.set_state(False, t("sl_update_title", latest=r["latest"]),
                           t("sl_update_detail", installed=r["installed"], path=path),
                           button=t("btn_update"), level="update", primary=True)
        elif r and r.get("update") is False:
            card.set_state(True, t("sl_up_to_date", version=r["installed"]), path, button=t("btn_check"))
        elif r and r.get("installed"):
            card.set_state(True, t("sl_version", version=r["installed"]), t("sl_check_failed"),
                           button=t("btn_check"))
        else:
            card.set_state(True, t("sl_found"), path, button=t("btn_check"))

    def _sl_card_action(self):
        path = core.find_streamlink(self.v_streamlink.get().strip())
        r = self.sl_update
        if not path:
            self.open_url(core.STREAMLINK_INSTALL_URL)
        elif r and r.get("path") == path and r.get("update"):
            self.open_update()
        else:
            self.check_streamlink_update(manual=True)

    def check_streamlink_update(self, manual=False):
        """Compare la version installée à la dernière publiée, hors de l'interface (thread).

        Compares the installed version with the latest published one, outside the interface (thread)."""
        if self._update_busy:
            return
        in_settings = self.panel_kind == "settings" and hasattr(self, "v_streamlink")
        path_setting = self.v_streamlink.get().strip() if in_settings else self.cfg["streamlink_path"]
        self._update_busy = True
        if in_settings:
            self._update_sl_card(busy=True)
        self.run_in_thread(lambda: updater.check_streamlink_update(path_setting),
                           lambda result: self._update_checked(result, manual))

    def _update_checked(self, result, manual):
        t = self.t
        self._update_busy = False
        if isinstance(result, Exception):
            result = {"path": None, "installed": None, "latest": None, "update": None, "kind": "pip",
                      "error": "network"}
        self.sl_update = result
        self._update_sl_card()
        self._refresh_update_badge()
        if result.get("update"):
            self.log(t("log_update_available", installed=result["installed"], latest=result["latest"]), "warn")
            self.toast(t("toast_update_available", latest=result["latest"]), "warn",
                       action=(t("btn_update"), self.open_update), duration=8000, low_priority=not manual)
            if not manual and self.tray_active and self.state() == "withdrawn":
                self.tray.notify(t("toast_update_available", latest=result["latest"]), t("notif_update_body"))
        elif result.get("update") is False:
            self.log(t("log_up_to_date", version=result["installed"], latest=result["latest"]), "dim")
            if manual:
                self.toast(t("toast_up_to_date", version=result["installed"]), "ok")
        elif manual:
            error = result.get("error")
            if error == "missing":
                self.toast(t("toast_no_streamlink"), "warn",
                           action=(t("btn_install"), lambda: self.open_url(core.STREAMLINK_INSTALL_URL)))
            elif error == "version":
                self.toast(t("toast_version_unknown"), "warn")
            else:
                self.toast(t("toast_update_check_failed"), "warn")

    def _refresh_update_badge(self):
        if hasattr(self, "settings_btn"):
            pending = (self.sl_update or {}).get("update") or (self.app_update or {}).get("update")
            try:
                self.settings_btn.set_badge(self.c.warn if pending else None)
            except tk.TclError:
                pass

    # --- Le lanceur : mise à jour depuis les releases GitHub
    # --- The launcher: update from the GitHub releases
    def _update_app_card(self):
        t = self.t
        try:
            if not hasattr(self, "app_card") or not self.app_card.winfo_exists():
                return
        except tk.TclError:
            return
        from . import __version__
        card, state, r = self.app_card, self._app_state, self.app_update
        title = t("app_card_title", version=__version__)
        if state == "checking":
            card.set_state(True, t("app_checking"), title, button=t("btn_check"), level="busy")
        elif state == "downloading":
            done, total = self._app_dl
            card.set_state(True, t("app_downloading", percent=int(done * 100 / total) if total else 0),
                           f"{t.format_size(done)} / {t.format_size(total)}", button=t("btn_cancel"), level="busy")
        elif state == "verifying":
            card.set_state(True, t("app_verifying"), t("app_verifying_detail"), button="", level="busy")
        elif state == "restart":
            card.set_state(True, t("app_restart_title"), t("app_restart_detail", latest=(r or {}).get("latest", "")),
                           button="", level="ok")
        elif state == "error":
            card.set_state(False, t("app_error_title"), t(self._app_error or "app_err_network"),
                           button=t("btn_retry"), level="warn")
        elif r and r.get("update"):
            asset = (r.get("release") or {}).get("asset")
            direct = bool(asset) and updater.can_self_update()
            detail = (t("app_update_detail", installed=__version__, size=t.format_size(asset["size"])) if direct
                      else t("app_update_manual", installed=__version__))
            card.set_state(False, t("app_update_title", latest=r["latest"]), detail,
                           button=t("btn_update") if direct else t("btn_open_release"), level="update", primary=True)
        elif r and r.get("update") is False:
            card.set_state(True, title, t("app_up_to_date"), button=t("btn_check"))
        else:
            card.set_state(True, title, updater.REPO_URL.split("//", 1)[1], button=t("btn_check"))

    def _app_card_action(self):
        state, r = self._app_state, self.app_update
        if state == "downloading":
            self._app_cancel.set()
        elif state in ("idle", "error") and r and r.get("update") and state != "error":
            self.install_app_update()
        elif state in ("idle", "error"):
            self.check_app_update(manual=True)

    def _open_release_notes(self):
        rel = (self.app_update or {}).get("release")
        self.open_url(rel["page"] if rel else updater.REPO_URL + "/releases")

    def check_app_update(self, manual=False):
        """Cherche une release plus récente sur GitHub, hors de l'interface (thread).

        Looks for a newer release on GitHub, outside the interface (thread)."""
        if self._app_state in ("checking", "downloading", "verifying", "restart"):
            return
        self._app_state, self._app_error = "checking", None
        self._update_app_card()
        self.run_in_thread(updater.check_app_update, lambda result: self._app_update_checked(result, manual))

    def _app_update_checked(self, result, manual):
        t = self.t
        self._app_state = "idle"
        if isinstance(result, Exception):
            result = {"error": "network", "update": None}
        self.app_update = None if result.get("error") else result
        if result.get("error") and manual:
            self._app_state = "error"
            self._app_error = {"network": "app_err_network", "release": "app_err_release"}.get(
                result["error"], "app_err_network")
        self._update_app_card()
        self._refresh_update_badge()
        # jamais de mise à jour surprise pendant un stream : la carte propose alors la mise à jour
        # never a surprise update during a stream: the card offers the update instead
        if not manual and not self.streams.running() and updater.should_auto_update(self.cfg, result, self._updated_from):
            self.log(t("log_app_auto_update", installed=result["current"], latest=result["latest"]), "warn")
            self.toast(t("toast_app_auto_update", latest=result["latest"]), "ok", duration=6000)
            self.install_app_update(auto=True)
            return
        if result.get("update"):
            self.log(t("log_app_update_available", installed=result["current"], latest=result["latest"]), "warn")
            self.toast(t("toast_app_update", latest=result["latest"]), "warn",
                       action=(t("btn_update"), self.open_settings), duration=8000, low_priority=not manual)
        elif result.get("update") is False and manual:
            self.toast(t("toast_app_up_to_date"), "ok")

    def install_app_update(self, auto=False):
        """Télécharge la release, la contrôle, remplace l'exécutable et redémarre. Sans exécutable
        remplaçable (lancé depuis les sources, dossier protégé…), ouvre la page de la release.

        Downloads the release, checks it, replaces the executable and restarts. Without a replaceable
        executable (started from the sources, protected folder…), opens the release page."""
        t = self.t
        rel = (self.app_update or {}).get("release")
        if not rel:
            return
        if not (rel.get("asset") and updater.can_self_update()):
            self.open_url(rel["page"])
            self.toast(t("toast_update_page_opened"), "ok")
            return
        running = self.streams.running()
        text = t("confirm_app_update", latest=rel["version"])
        if running:
            text += "\n" + t("confirm_app_update_streams", count=len(running))
        if not auto and not messagebox.askyesno(t("title_confirm"), text, parent=self):
            return
        self._app_state, self._app_error = "downloading", None
        self._app_dl = (0, rel["asset"]["size"])
        self._app_cancel = cancel = threading.Event()
        folder, exe = os.path.dirname(sys.executable), sys.executable

        def progress(done, total):
            self._app_dl = (done, total)

        def work():
            path = updater.download_update(rel, folder, progress, cancel)
            self._app_state = "verifying"
            key = updater.check_signature(exe, path)
            if key:
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise updater.UpdateError(key)
            return path

        self._update_app_card()
        self.after(200, self._poll_app_update)
        self.run_in_thread(work, lambda result: self._app_downloaded(result, rel))

    def _poll_app_update(self):
        if self._app_state in ("downloading", "verifying"):
            self._update_app_card()
            self.after(200, self._poll_app_update)

    def _app_downloaded(self, result, rel):
        t = self.t
        from . import __version__
        if isinstance(result, Exception):
            key = result.key if isinstance(result, updater.UpdateError) else "app_err_download"
            if key == "app_err_cancelled":
                self._app_state = "idle"
            else:
                self._app_state, self._app_error = "error", key
                self.log(t("log_app_update_failed", error=t(key)), "err")
                if not isinstance(result, updater.UpdateError):
                    core.log.error("Mise à jour : %r", result)
            self._update_app_card()
            return
        final = updater.target_exe(sys.executable, __version__, rel["version"])
        try:
            updater.install_update(result, final=final)
        except updater.UpdateError as e:
            try:
                os.remove(result)
            except OSError:
                pass
            self._app_state, self._app_error = "error", e.key
            self.log(t("log_app_update_failed", error=t(e.key)), "err")
            self._update_app_card()
            return
        self.log(t("log_app_updated", old=__version__, new=rel["version"]))
        if str(final) != sys.executable and self.cfg.get("autostart"):  # le démarrage avec Windows suit le nouveau nom
                                                                        # start-up with Windows follows the new name
            wintray.set_autostart(True, "", sys.executable, exe=str(final))
        if updater.relaunch(final, old_version=__version__, extra_args=("--tray",) if "--tray" in sys.argv else ()):
            self._shutdown()
        else:  # nouvelle version en place, mais impossible de la démarrer : à relancer à la main
               # new version in place, but it cannot be started: to be restarted by hand
            self._app_state = "restart"
            self._update_app_card()
            self.toast(t("app_restart_title") + " — " + t("app_restart_detail", latest=rel["version"]), "ok",
                       duration=8000)

    def open_update(self):
        """Installateur Windows : page de téléchargement. Installation pip : commande copiée.

        Windows installer: download page. pip installation: command copied."""
        t = self.t
        r = self.sl_update or {}
        if r.get("kind") == "windows":
            self.open_url(updater.WINDOWS_BUILDS_URL)
            self.toast(t("toast_update_page_opened"), "ok")
        else:
            self.clipboard_clear()
            self.clipboard_append(updater.PIP_UPGRADE_CMD)
            self.toast(t("toast_pip_copied", cmd=updater.PIP_UPGRADE_CMD), "ok", duration=6000)
            self.log(t("log_pip_command", cmd=updater.PIP_UPGRADE_CMD))

    def open_url(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            self.toast(self.t("log_error", error=e), "error")
