"""Lancement des streams, suivi des streams en cours et tiroir du journal.

Launching streams, monitoring running streams and the log drawer.

Mixin de App (voir app.py) : ces méthodes utilisent self comme la fenêtre principale.
Mixin of App (see app.py): these methods use self as the main window."""
import os
import subprocess
import tkinter as tk

from . import core
from .app_common import LOG_LIMIT
from .widgets import (
    StreamRow,
)


class LaunchMixin:
    # =====================================================
    # Lancement
    # Launch
    # =====================================================
    def launch(self):
        kind, value = self.target
        if kind == "platform":
            return self.launch_platform(self.platform_by_id(value), self.query.get(), self.quality_select.value)
        return self.launch_script(value, self.query.get())

    def launch_entry(self, entry, report=None):
        """report : où afficher les erreurs (par défaut les notifications de la fenêtre).

        report: where to show errors (by default the window's notifications)."""
        report = report or self.toast
        target = self.entry_target(entry)
        if not target:
            report(self.t("err_unknown_target", name=entry.get("platform") or entry.get("script") or "?"),
                       "error")
            return False
        if target[0] == "platform":
            return self.launch_platform(target[1], entry.get("channel", ""), report=report)
        return self.launch_script(target[1], entry.get("channel", ""), report=report)

    def launch_platform(self, p, raw, quality=None, report=None):
        t = self.t
        quiet = report is not None  # lancé depuis le mode mini : erreurs affichées dans la barre
                                    # started from the mini mode: errors shown in the bar
        report = report or self.toast
        streamlink = core.find_streamlink(self.cfg["streamlink_path"])
        if not streamlink:
            report(t("toast_no_streamlink"), "error", action=(t("action_settings"), self.open_settings))
            self.log(t("log_no_streamlink", url=core.STREAMLINK_INSTALL_URL), "err")
            return False
        try:
            url, display = core.resolve_target(p, raw)
        except core.InputError as e:
            report(t(e.key, name=self.platform_name(p)), "warn")
            if not quiet:
                self.field.focus()
            return False
        quality = quality if quality and quality not in ("—", "__custom__") else self.quality_for(p)
        if not core.QUALITY_RE.match(quality):
            report(t("err_quality"), "warn")
            return False
        # Le lien lancé n'est pas à reproposer. Lu AVANT de démarrer le processus : sous X11, lire le presse-papiers
        # traite des événements, et une notification d'échec pourrait sinon être recouverte par « Lancement ».
        # The started link must not be offered again. Read BEFORE starting the process: on X11, reading the clipboard
        # processes events, and a failure notification could otherwise be covered by "Starting".
        self._clip_seen = self._clip_key()[0]
        opts, missing = core.player_options(self.cfg)
        if missing:
            self.log(t("log_player_not_found", player=core.PLAYER_NAMES.get(missing, missing)), "warn")
        player = self.cfg["player"]
        player_label = None
        if player in core.PLAYER_NAMES and not missing:
            player_label = core.PLAYER_NAMES[player]
        elif player == "custom" and not missing:
            player_label = t("player_custom")
        pname = self.platform_name(p)
        name = display if p["input"] != "none" else pname
        detail = " · ".join(x for x in (pname if p["input"] != "none" else None, quality, player_label) if x)
        command = [streamlink, *p["args"], *opts, url, quality]
        try:
            self.streams.start(command, {"name": name, "detail": detail, "color": p["color"], "label": name})
        except Exception as e:
            report(t("toast_launch_failed"), "error", action=(t("action_show_log"), self.show_log))
            self.log(t("log_error", error=e), "err")
            return False
        self.log(t("log_launching", label=f"{pname} / {name}", quality=quality))
        self.store.add_history({"channel": display, "platform": p["id"]})
        self.toast(t("toast_launching", name=name, platform=pname), "ok")
        self.build_recents()
        self._refresh_panel("history")
        self.refresh_drawer()
        self.start_polling()
        return True

    def launch_script(self, script_name, raw, report=None):
        t = self.t
        report = report or self.toast
        full_path = os.path.join(self.cfg["scripts_folder"], script_name)
        if not os.path.exists(full_path):
            report(t("err_script_not_found", path=script_name), "error")
            return False
        arg = (raw or "").strip()
        if arg and not core.SCRIPT_ARG_RE.match(arg):
            report(t("err_script_arg"), "warn")
            return False
        try:
            command = core.build_script_command(full_path, arg)
            if command is None:
                os.startfile(full_path)
            else:
                flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
                subprocess.Popen(command, cwd=os.path.dirname(full_path), creationflags=flags)
        except Exception as e:
            report(t("toast_launch_failed"), "error")
            self.log(t("log_error", error=e), "err")
            return False
        self.log(t("log_launching", label=script_name + (f" / {arg}" if arg else ""), quality="-"))
        self.store.add_history({"channel": arg, "script": script_name})
        self.toast(t("toast_launching", name=arg or script_name, platform=t("pill_scripts")), "ok")
        self.build_recents()
        return True

    def stop_stream(self, stream):
        stream["stopped"] = True
        self.streams.stop(stream)
        self.toast(self.t("toast_stopped", name=stream["name"]), "ok")

    # --- suivi des streams (uniquement quand il y en a)
    # --- stream monitoring (only when there are some)
    def start_polling(self):
        if not self._polling:
            self._polling = True
            self.after(120, self._poll)

    def _poll(self):
        t = self.t
        for kind, stream, value in self.streams.poll():
            if kind == "line":
                self.log(f"[{stream['label']}] {value}")
            else:
                failed = value not in (0, None) and not stream.get("stopped")
                if stream.get("stopped"):
                    self.log(t("log_stream_stopped", label=stream["label"]), "dim")
                else:
                    self.log(t("log_stream_ended", label=stream["label"], code=value), "err" if failed else "dim")
                if failed:
                    self.toast(t("toast_stream_failed", name=stream["name"]), "error",
                               action=(t("action_show_log"), self.show_log), duration=5000)
                self.refresh_drawer()
        if self.streams.busy():
            self.after(150, self._poll)
        else:
            self._polling = False

    # =====================================================
    # Tiroir du journal
    # Log drawer
    # =====================================================
    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        if self.drawer_open:
            self._build_drawer_body()
        elif self.drawer_body is not None:
            self.drawer_body.destroy()
            self.drawer_body = self.log_text = None
        self.refresh_drawer()

    def show_log(self):
        if not self.drawer_open:
            self.toggle_drawer()

    def _build_drawer_body(self):
        c, px, f = self.c, self.px, self.fonts
        body = self.drawer_body = tk.Frame(self.drawer, bg=c.title)
        body.pack(fill="x", padx=(px(32), px(20)), pady=(0, px(14)))
        self.stream_rows = tk.Frame(body, bg=c.title)
        self.stream_rows.pack(fill="x")
        border = tk.Frame(body, bg=c.border)
        border.pack(fill="x", pady=(px(4), 0))
        self.log_text = tk.Text(border, height=6, bg=c.log_bg, fg=c.muted, font=f.mono, relief="flat", bd=0,
                                highlightthickness=0, wrap="word", padx=px(12), pady=px(8), cursor="",
                                insertwidth=0, selectbackground=c.border_strong, spacing1=px(1), spacing3=px(1))
        self.log_text.pack(fill="x", padx=1, pady=1)
        self.log_text.tag_configure("err", foreground=c.error)
        self.log_text.tag_configure("warn", foreground=c.warn)
        self.log_text.tag_configure("dim", foreground=c.faint)
        if not self.log_lines:
            self.log_text.insert("end", self.t("log_empty") + "\n", "dim")
        for msg, tag in self.log_lines:
            self.log_text.insert("end", msg + "\n", tag or ())
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self._fill_stream_rows()

    def _fill_stream_rows(self):
        for w in self.stream_rows.winfo_children():
            w.destroy()
        for s in self.streams.streams:
            StreamRow(self.stream_rows, self, s["name"], s["detail"], s["color"], self.t("btn_stop"),
                      lambda s=s: self.stop_stream(s)).pack(fill="x", pady=(0, self.px(6)))

    def refresh_drawer(self):
        t = self.t
        n = len(self.streams.streams)
        text = t("drawer_none") if n == 0 else (t("drawer_running_one") if n == 1 else t("drawer_running", count=n))
        self.drawer_bar.set_state(text, t("drawer_log"), self.drawer_open, n > 0)
        if self.drawer_open and self.drawer_body is not None:
            self._fill_stream_rows()

    def log(self, msg, tag=None):
        if tag is None:
            low = msg.lower()
            if "error" in low or "erreur" in low:
                tag = "err"
            elif "warning" in low:
                tag = "warn"
        if not self.log_lines and self.log_text is not None:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        self.log_lines.append((msg, tag))
        if self.log_text is not None:
            lt = self.log_text
            lt.configure(state="normal")
            lt.insert("end", msg + "\n", tag or ())
            lines = int(lt.index("end-1c").split(".")[0])
            if lines > LOG_LIMIT:
                lt.delete("1.0", f"{lines - LOG_LIMIT}.0")
            lt.configure(state="disabled")
            lt.see("end")
