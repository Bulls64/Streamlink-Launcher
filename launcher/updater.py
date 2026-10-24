"""Mises à jour : version de Streamlink (PyPI), mise à jour du lanceur depuis les releases GitHub (téléchargement, vérification, remplacement, redémarrage).

Updates: Streamlink version (PyPI), launcher update from the GitHub releases (download, checks, replacement, restart)."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from .core import FROZEN, find_streamlink, log
from .live import USER_AGENT

# ---------------------
# Streamlink est-il à jour ?
# Is Streamlink up to date?
# ---------------------
PYPI_URL = "https://pypi.org/pypi/streamlink/json"
WINDOWS_BUILDS_URL = "https://github.com/streamlink/windows-builds/releases/latest"
PIP_UPGRADE_CMD = "python -m pip install --upgrade streamlink"
VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def parse_version(text):
    """'streamlink 7.1.3' / '7.1.3-1' / '8.0.0+12.gabc' -> (7, 1, 3). None si introuvable.

    'streamlink 7.1.3' / '7.1.3-1' / '8.0.0+12.gabc' -> (7, 1, 3). None if not found."""
    m = VERSION_RE.search(text or "")
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())


def version_text(text):
    v = parse_version(text)
    return ".".join(map(str, v)) if v else None


def streamlink_version(path, timeout=20):
    """Version installée (ex. '7.1.3'), ou None si Streamlink ne répond pas.

    Installed version (e.g. '7.1.3'), or None if Streamlink does not answer."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    out = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, creationflags=flags,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    return version_text((out.stdout or "") + " " + (out.stderr or ""))


def _http_get_json(url, timeout):
    import urllib.request  # chargé seulement au besoin
                           # loaded only when needed
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_streamlink_version(timeout=8):
    """Dernière version stable publiée (PyPI, source officielle des versions de Streamlink).

    Latest stable version published (PyPI, the official source of Streamlink versions)."""
    data = _http_get_json(PYPI_URL, timeout)
    return version_text(((data or {}).get("info") or {}).get("version"))


def install_kind(path):
    """'windows' pour l'installateur officiel (…\\Streamlink\\bin\\streamlink.exe), sinon 'pip'.

    'windows' for the official installer (…\\Streamlink\\bin\\streamlink.exe), otherwise 'pip'."""
    p = (path or "").replace("/", "\\").lower()
    return "windows" if "\\streamlink\\bin\\" in p or p.endswith("\\streamlink\\bin") else "pip"


def check_streamlink_update(streamlink_path=""):
    """Renvoie {path, installed, latest, update, kind, error} ; 'update' vaut None si on ne peut pas conclure.

    Returns {path, installed, latest, update, kind, error}; 'update' is None if no conclusion can be drawn."""
    path = find_streamlink(streamlink_path)
    result = {"path": path, "installed": None, "latest": None, "update": None, "kind": install_kind(path),
              "error": None}
    if not path:
        result["error"] = "missing"
        return result
    try:
        result["installed"] = streamlink_version(path)
    except Exception:
        result["installed"] = None
    try:
        result["latest"] = latest_streamlink_version()
    except Exception as e:
        log.warning("Vérification de mise à jour impossible : %s", e)
        result["error"] = "network"
    if result["installed"] and result["latest"]:
        result["update"] = parse_version(result["latest"]) > parse_version(result["installed"])
    elif not result["error"]:
        result["error"] = "version"
    return result


# ---------------------
# Mise à jour du lanceur (releases GitHub)
# Launcher update (GitHub releases)
# ---------------------
REPO = "Bulls64/Streamlink-Launcher"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
UPDATE_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
UPDATE_MIN_BYTES, UPDATE_MAX_BYTES = 1_000_000, 100 * 1024 * 1024
OLD_SUFFIX = ".old"      # ancien exécutable, gardé le temps du redémarrage puis supprimé
                         # old executable, kept during the restart, then deleted


class UpdateError(Exception):
    """Échec de mise à jour ; .key est la clé de traduction du message à afficher.

    Update failure; .key is the translation key of the message to show."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def parse_release(data):
    """Réponse de l'API GitHub -> {version, tag, page, asset} ou None si elle ne convient pas.
    asset = {name, url, size, sha256} ou None quand la version n'a pas d'exécutable téléchargeable.
    Tout est contrôlé : seules une release publiée (ni brouillon ni préversion) et une adresse de
    téléchargement qui est exactement celle attendue sur ce dépôt sont acceptées.

    GitHub API response -> {version, tag, page, asset} or None if it is not suitable.
    asset = {name, url, size, sha256} or None when the version has no downloadable executable.
    Everything is checked: only a published release (neither draft nor pre-release) and a
    download address that is exactly the one expected on this repository are accepted."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    m = UPDATE_TAG_RE.match(tag)
    if not m:
        return None
    version = m.group(1)
    release = {"version": version, "tag": tag, "page": f"{REPO_URL}/releases/tag/{tag}", "asset": None}
    name = f"StreamlinkLauncher-{version}.exe"
    url = f"{REPO_URL}/releases/download/{tag}/{name}"
    for a in data.get("assets") or []:
        if not isinstance(a, dict) or a.get("name") != name:
            continue
        size, digest = a.get("size"), SHA256_RE.match(str(a.get("digest") or ""))
        if (a.get("browser_download_url") == url and digest and isinstance(size, int) and not isinstance(size, bool)
                and UPDATE_MIN_BYTES <= size <= UPDATE_MAX_BYTES):
            release["asset"] = {"name": name, "url": url, "size": size, "sha256": digest.group(1)}
    return release


def check_app_update(current=None):
    """Compare la version du lanceur à la dernière release publiée.
    Renvoie {current, latest, update, release, error} ; 'update' vaut None si on ne peut pas conclure.

    Compares the launcher's version with the latest published release.
    Returns {current, latest, update, release, error}; 'update' is None if no conclusion can be drawn."""
    if current is None:
        from . import __version__ as current
    result = {"current": current, "latest": None, "update": None, "release": None, "error": None}
    try:
        data = _http_get_json(RELEASES_API, 10)
    except Exception as e:
        log.warning("Recherche de mise à jour du lanceur impossible : %s", e)
        result["error"] = "release" if getattr(e, "code", None) == 404 else "network"
        return result
    release = parse_release(data)
    if release is None:
        result["error"] = "release"
        return result
    result.update(latest=release["version"], release=release,
                  update=parse_version(release["version"]) > parse_version(current))
    return result


def should_auto_update(cfg, result, updated_from=None, can_update=None):
    """Faut-il installer sans demander la mise à jour trouvée au démarrage ? Oui si l'option est active (avec la
    vérification au démarrage), si une version plus récente existe avec un fichier téléchargeable, si cet exécutable
    peut se remplacer, et si le lanceur ne vient pas lui-même d'être mis à jour (pas de boucle de mises à jour).

    Should the update found at start-up be installed without asking? Yes if the option is on (along with the
    start-up check), if a newer version exists with a downloadable file, if this executable
    can replace itself, and if the launcher was not itself just updated (no update loop)."""
    if can_update is None:
        can_update = can_self_update()
    release = (result or {}).get("release") or {}
    return bool(cfg.get("auto_update") and cfg.get("update_check") and (result or {}).get("update")
                and release.get("asset") and can_update and not updated_from)


def can_self_update():
    """Vrai pour l'exécutable Windows dont le dossier est modifiable ; sinon, la page de la release s'ouvre.

    True for the Windows executable whose folder is writable; otherwise, the release page opens."""
    if not (FROZEN and os.name == "nt"):
        return False
    exe = Path(sys.executable)
    return os.access(exe.parent, os.W_OK) and os.access(exe, os.W_OK)


def _safe_opener():
    """Ouvreur d'adresses qui refuse toute redirection hors de GitHub ou en clair (http).

    URL opener that refuses any redirect outside GitHub or in clear text (http)."""
    import urllib.error
    import urllib.request

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            u = urlparse(newurl)
            host = (u.hostname or "").lower()
            if u.scheme != "https" or not (host == "github.com" or host.endswith((".github.com", ".githubusercontent.com"))):
                raise urllib.error.URLError(f"redirection refusée : {u.scheme}://{host}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(Redirect)


def _open_download(url, timeout=20):
    import urllib.request
    return _safe_opener().open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def download_update(release, dest_dir, progress=None, cancel=None, opener=None):
    """Télécharge l'exécutable de la release dans dest_dir et le contrôle : taille annoncée, empreinte SHA-256
    publiée par GitHub, en-tête d'exécutable Windows. Renvoie son chemin. Lève UpdateError, et le fichier
    partiel est alors supprimé. progress(octets_reçus, total) ; cancel : threading.Event.

    Downloads the release's executable into dest_dir and checks it: announced size, SHA-256 digest
    published by GitHub, Windows executable header. Returns its path. Raises UpdateError, and the partial
    file is then deleted. progress(bytes_received, total); cancel: threading.Event."""
    import hashlib
    asset = (release or {}).get("asset")
    if not asset:
        raise UpdateError("app_err_release")
    dest = Path(dest_dir) / (asset["name"] + ".download")
    digest, done, ok = hashlib.sha256(), 0, False
    try:
        try:
            resp = (opener or _open_download)(asset["url"])
        except Exception as e:
            log.warning("Téléchargement impossible : %s", e)
            raise UpdateError("app_err_network") from e
        try:
            with resp, open(dest, "wb") as out:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise UpdateError("app_err_cancelled")
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > asset["size"]:
                        raise UpdateError("app_err_hash")
                    digest.update(chunk)
                    out.write(chunk)
                    if progress:
                        progress(done, asset["size"])
        except UpdateError:
            raise
        except Exception as e:
            log.warning("Téléchargement interrompu : %s", e)
            raise UpdateError("app_err_download") from e
        if done != asset["size"]:
            raise UpdateError("app_err_download")
        if digest.hexdigest() != asset["sha256"]:
            raise UpdateError("app_err_hash")
        with open(dest, "rb") as f:
            if f.read(2) != b"MZ":
                raise UpdateError("app_err_hash")
        ok = True
        return dest
    finally:
        if not ok:
            try:
                dest.unlink()
            except OSError:
                pass


def _parse_authenticode(text):
    """'Valid|CN=Nom, O=…' -> ('Valid', 'CN=Nom, O=…') ; sortie vide ou illisible -> ('error', None).

    'Valid|CN=Name, O=…' -> ('Valid', 'CN=Name, O=…'); empty or unreadable output -> ('error', None)."""
    lines = (text or "").strip().splitlines()
    status, _, subject = (lines[-1] if lines else "").partition("|")
    return (status.strip(), subject.strip() or None) if status.strip() else ("error", None)


def authenticode(path, timeout=40):
    """Signature d'un exécutable Windows : (statut, signataire). Statut : 'Valid', 'NotSigned', 'HashMismatch',
    'NotTrusted'… ou 'error' si PowerShell est indisponible.

    Signature of a Windows executable: (status, signer). Status: 'Valid', 'NotSigned', 'HashMismatch',
    'NotTrusted'… or 'error' if PowerShell is unavailable."""
    if os.name != "nt":
        return "error", None
    try:
        script = "$s = Get-AuthenticodeSignature -LiteralPath $env:SL_FILE; '{0}|{1}' -f $s.Status, $s.SignerCertificate.Subject"
        out = subprocess.run([shutil.which("powershell") or "powershell", "-NoProfile", "-NonInteractive",
                              "-ExecutionPolicy", "Bypass", "-Command", script],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             env=dict(os.environ, SL_FILE=str(path)))
        return _parse_authenticode(out.stdout)
    except Exception as e:
        log.warning("Lecture de la signature impossible : %s", e)
        return "error", None


def _common_name(subject):
    m = re.search(r"CN=([^,]+)", subject or "")
    return (m.group(1) if m else subject or "").strip()


def check_signature(current_file, new_file, probe=None):
    """None si la nouvelle version peut être installée, sinon la clé du message d'erreur.
    Si l'application actuelle est signée (signature valide), la nouvelle doit l'être aussi, par le même
    signataire : impossible de revenir à une version non signée. Sinon, on refuse seulement une signature
    présente mais invalide (fichier modifié).

    None if the new version can be installed, otherwise the key of the error message.
    If the current application is signed (valid signature), the new one must be too, by the same
    signer: going back to an unsigned version is impossible. Otherwise, only a signature that is
    present but invalid (modified file) is refused."""
    probe = probe or authenticode
    cur_status, cur_subject = probe(current_file)
    new_status, new_subject = probe(new_file)
    if cur_status == "Valid":
        same = new_status == "Valid" and _common_name(new_subject) == _common_name(cur_subject)
        return None if same else "app_err_signature"
    return None if new_status in ("Valid", "NotSigned", "error") else "app_err_signature"


def target_exe(exe, old_version, new_version):
    """Chemin sous lequel installer la nouvelle version : si le nom de fichier contient l'ancien numéro
    (StreamlinkLauncher-1.4.1.exe), il prend le nouveau, pour que le nom ne mente pas. Sinon, inchangé.

    Path under which to install the new version: if the file name contains the old number
    (StreamlinkLauncher-1.4.1.exe), it takes the new one, so that the name does not lie. Otherwise, unchanged."""
    exe = Path(exe)
    if not old_version or not new_version or old_version == new_version:
        return exe
    renamed = re.sub(r"(?<![\d.])" + re.escape(str(old_version)) + r"(?!\.?\d)", str(new_version), exe.name)
    target = exe.with_name(renamed)
    return target if renamed != exe.name and not target.exists() else exe


def install_update(new_file, exe=None, final=None):
    """Remplace l'exécutable : l'ancien est renommé en .old (Windows permet de renommer un exécutable en
    cours d'exécution, pas de l'écraser), le nouveau prend sa place (sous le nom `final` si donné, sinon
    celui de l'ancien). En cas d'échec, l'ancien est remis.

    Replaces the executable: the old one is renamed to .old (Windows allows renaming a running
    executable, not overwriting it), the new one takes its place (under the name `final` if given, otherwise
    that of the old one). On failure, the old one is put back."""
    exe, new_file = Path(exe or sys.executable), Path(new_file)
    final = Path(final) if final else exe
    old = exe.with_name(exe.name + OLD_SUFFIX)
    try:
        old.unlink(missing_ok=True)
        os.replace(exe, old)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        raise UpdateError("app_err_install") from e
    try:
        os.replace(new_file, final)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        try:
            os.replace(old, exe)
        except OSError:
            log.error("L'ancien exécutable n'a pas pu être remis en place (%s)", old)
        raise UpdateError("app_err_install") from e
    return old


def cleanup_old_executable(exe=None, tries=30, delay=1.0):
    """Supprime l'ancien exécutable laissé par une mise à jour (réessaie : l'ancienne instance peut
    mettre quelques secondes à se fermer). Renvoie True si rien ne reste.

    Deletes the old executable left by an update (retries: the old instance may
    take a few seconds to close). Returns True if nothing is left."""
    exe = Path(exe or sys.executable)
    old = exe.with_name(exe.name + OLD_SUFFIX)
    for _i in range(tries):
        if not old.exists():
            return True
        try:
            old.unlink()
            return True
        except OSError:
            time.sleep(delay)
    return False


def cleanup_update_leftovers(exe=None):
    """Au démarrage : ancien exécutable d'une mise à jour, et téléchargements interrompus.

    At start-up: old executable from an update, and interrupted downloads."""
    exe = Path(exe or sys.executable)
    cleanup_old_executable(exe)
    for f in [*exe.parent.glob("StreamlinkLauncher-*.exe.download"),
              *exe.parent.glob("StreamlinkLauncher-*.exe" + OLD_SUFFIX)]:  # .old d'avant un renommage
                                                                           # .old from before a rename
        try:
            f.unlink()
        except OSError:
            pass


def relaunch(exe=None, old_version=None, extra_args=()):
    """Démarre la nouvelle version, détachée de ce processus ; elle attend sa fermeture (--wait-pid) avant de
    prendre le verrou d'instance unique. PYINSTALLER_RESET_ENVIRONMENT : sans cela, un exécutable
    PyInstaller lancé par lui-même réutiliserait le dossier temporaire de l'ancien, supprimé à sa fermeture.

    Starts the new version, detached from this process; it waits for it to close (--wait-pid) before
    taking the single-instance lock. PYINSTALLER_RESET_ENVIRONMENT: without it, a PyInstaller
    executable started by itself would reuse the old one's temporary folder, deleted when it closes."""
    exe = str(exe or sys.executable)
    args = [exe, "--wait-pid", str(os.getpid()), *extra_args]
    if old_version:
        args += ["--updated-from", str(old_version)]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(args, cwd=os.path.dirname(exe), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        return True
    except OSError as e:
        log.error("Redémarrage impossible : %s", e)
        return False


def arg_value(name, argv=None):
    """Valeur qui suit l'option `name` sur la ligne de commande, ou None.

    Value that follows the `name` option on the command line, or None."""
    argv = sys.argv if argv is None else argv
    for i, a in enumerate(argv[:-1]):
        if a == name:
            return argv[i + 1]
    return None
