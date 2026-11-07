"""Vérification en conditions réelles : le statut en direct du lanceur marche-t-il encore ?

Le statut des favoris repose sur deux sources qui peuvent changer sans prévenir :
- Twitch : l'accès web public du site (GraphQL), qui n'est pas une API officielle, et ses images d'aperçu ;
- Kick : `streamlink --json`, donc le plugin Kick de Streamlink.
Les tests du dépôt les imitent ; ce script, lui, interroge les vrais services, sans compte. Il sert à la
vérification quotidienne de la CI (live-check.yml), pour savoir qu'une source a changé avant les utilisateurs.

- Twitch réussit si la requête répond pour des chaînes connues et qu'au moins l'une d'elles est en direct
  avec un aperçu téléchargeable (il y a toujours quelqu'un en direct parmi elles).
- Kick réussit si Streamlink sait dire, pour au moins une chaîne, si elle est en direct ou hors ligne.
Code de sortie 0 si tout va bien, 1 sinon ; le résumé est écrit en Markdown (pour le ticket ouvert par la CI).

Real-world check: does the launcher's live status still work?

The favorites' status relies on two sources that can change without notice:
- Twitch: the website's public web endpoint (GraphQL), which is not an official API, and its preview images;
- Kick: `streamlink --json`, so Streamlink's Kick plugin.
The repository's tests imitate them; this script queries the real services, without an account. It is used by the
daily CI check (live-check.yml), to know that a source has changed before users do.

- Twitch passes if the request answers for well-known channels and at least one of them is live
  with a downloadable preview (someone among them is always live).
- Kick passes if Streamlink can tell, for at least one channel, whether it is live or offline.
Exit code 0 if all is well, 1 otherwise; the summary is written in Markdown (for the issue opened by the CI).

Usage: python packaging/live_check.py [--platform twitch|kick] [--summary FILE]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launcher import core, live

TWITCH_CHANNELS = ["kaicenat", "ibai", "xqc", "eslcs", "shroud", "auronplay", "zackrawrr", "jynxzi", "caedrel",
                   "tarik", "summit1g", "lirik", "pokimane", "riotgames", "rocketleague"]
KICK_CHANNELS = ["xqc", "adinross", "trainwreckstv", "amouranth", "cuffem"]


def check_twitch():
    states = live.twitch_live(TWITCH_CHANNELS)
    if set(states) != set(TWITCH_CHANNELS):
        return False, f"réponse incomplète : {len(states)}/{len(TWITCH_CHANNELS)} chaînes"
    on_air = [ch for ch, s in states.items() if s["live"]]
    if not on_air:
        return False, "aucune chaîne en direct : la réponse a peut-être changé de forme"
    for ch in on_air:
        url = live.preview_url(states[ch]["preview"])
        image = live.fetch_image(url) if url else None
        if image:
            title = (states[ch]["title"] or "")[:60]
            return True, f"{len(on_air)} en direct ; aperçu de {ch} : {len(image)} octets ; titre : {title!r}"
    return False, f"{len(on_air)} en direct, mais aucun aperçu téléchargeable"


def check_kick():
    streamlink = core.find_streamlink()
    if not streamlink:
        return False, "Streamlink introuvable"
    tried = []
    for ch in KICK_CHANNELS:
        try:
            info = live.streamlink_live(streamlink, f"https://kick.com/{ch}", timeout=60)
        except Exception as e:  # délai dépassé, etc. / timeout, etc.
            info = None
            tried.append(f"{ch} : {e!r}")
            continue
        if info is not None:
            return True, f"{ch} : {'en direct' if info['live'] else 'hors ligne'}" + (
                f" ; essais : {', '.join(tried)}" if tried else "")
        tried.append(f"{ch} : inconnu")
    return False, "Streamlink ne sait plus dire si une chaîne Kick est en direct : " + ", ".join(tried)


CHECKS = {"twitch": check_twitch, "kick": check_kick}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--platform", choices=sorted(CHECKS), action="append")
    parser.add_argument("--summary", help="fichier Markdown du résumé / Markdown summary file")
    args = parser.parse_args(argv)
    lines, failed = ["| Source | Résultat | Détail |", "|---|---|---|"], []
    for platform in args.platform or list(CHECKS):
        try:
            passed, detail = CHECKS[platform]()
        except Exception as e:  # le script doit toujours finir son résumé / the script must always finish
            passed, detail = False, f"exception : {e!r}"
        print(f"{platform:7} {'OK' if passed else 'échec'} : {detail}", flush=True)
        if not passed:
            failed.append(platform)
        lines.append(f"| {platform} | {'échec' if not passed else 'OK'} | {detail} |")
    summary = "\n".join(lines) + "\n"
    if args.summary:
        Path(args.summary).write_text(summary, encoding="utf-8")
    print("\n" + summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
