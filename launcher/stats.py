"""Statistiques de visionnage : durée de chaque stream regardé, temps par chaîne et heures de pointe.

Chaque stream terminé après au moins une minute est noté dans stats.json (dossier des données) : chaîne,
plateforme (ou script), début et durée. Rien ne quitte l'ordinateur. Les séances de plus d'un an sont oubliées.

Viewing statistics: duration of each watched stream, time per channel and peak hours.

Each stream that ends after at least one minute is written to stats.json (data folder): channel,
platform (or script), start and duration. Nothing leaves the computer. Sessions older than a year are forgotten.
"""
from datetime import datetime, timedelta

from . import core

MIN_SECONDS = 60          # en dessous : lancement raté ou essai, pas un visionnage / below: failed start or a try
KEEP_DAYS = 365
LIMIT = 5000              # séances gardées au plus / sessions kept at most
MAX_SECONDS = 2 * 86400   # une séance plus longue est sûrement une horloge déréglée / longer: surely a wrong clock
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def stats_file():
    return core.DATA_FOLDER / "stats.json"


def _clean(raw):
    out = []
    for s in raw if isinstance(raw, list) else []:
        if not isinstance(s, dict) or not isinstance(s.get("channel"), str):
            continue
        seconds = s.get("seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not 0 < seconds <= MAX_SECONDS:
            continue
        try:
            datetime.strptime(s.get("start", ""), DATE_FMT)
        except (TypeError, ValueError):
            continue
        entry = {"channel": s["channel"][:200], "start": s["start"], "seconds": seconds}
        for k in ("platform", "script"):
            if isinstance(s.get(k), str):
                entry[k] = s[k][:100]
        out.append(entry)
    return out


class WatchStats:
    """Séances de visionnage, les plus récentes en tête.

    Viewing sessions, newest first."""

    def __init__(self):
        data = core.load_json(stats_file(), {"sessions": []}, recover=True)
        self.sessions = _clean(data.get("sessions") if isinstance(data, dict) else [])

    def save(self):
        return core.save_json(stats_file(), {"sessions": self.sessions})

    def add(self, entry, started, ended=None):
        """Note un stream regardé de started à ended (datetime). Renvoie la séance, ou None si trop courte.

        Records a stream watched from started to ended (datetime). Returns the session, or None if too short."""
        ended = ended or datetime.now()
        seconds = int((ended - started).total_seconds())
        if seconds < MIN_SECONDS or not entry.get("channel"):
            return None
        session = {"channel": str(entry["channel"])[:200], "start": started.strftime(DATE_FMT),
                   "seconds": min(seconds, MAX_SECONDS)}
        for k in ("platform", "script"):
            if entry.get(k):
                session[k] = str(entry[k])[:100]
        limit = (ended - timedelta(days=KEEP_DAYS)).strftime(DATE_FMT)
        self.sessions = [session] + [s for s in self.sessions if s["start"] >= limit][:LIMIT - 1]
        self.save()
        return session

    def clear(self):
        self.sessions = []
        self.save()


def summarize(sessions, days=None, now=None, top=10):
    """Résumé : {total, count, channels: [{entry, seconds, count}], hours: [24 durées]}.
    days : seulement les N derniers jours (None : tout). Le temps est réparti heure par heure
    (un stream de 21 h 30 à 23 h compte 30 min à 21 h et 1 h à 22 h).

    Summary: {total, count, channels: [{entry, seconds, count}], hours: [24 durations]}.
    days: only the last N days (None: all). Time is spread hour by hour
    (a stream from 9:30 to 11 pm counts 30 min at 9 pm and 1 h at 10 pm)."""
    now = now or datetime.now()
    since = now - timedelta(days=days) if days else None
    per, hours = {}, [0] * 24
    total = count = 0
    for s in sessions:
        start = datetime.strptime(s["start"], DATE_FMT)
        if since and start < since:
            continue
        count += 1
        total += s["seconds"]
        key = (s["channel"].lower(), s.get("platform") or "", s.get("script") or "")
        item = per.setdefault(key, {"entry": {k: s[k] for k in ("channel", "platform", "script") if k in s},
                                    "seconds": 0, "count": 0})
        item["seconds"] += s["seconds"]
        item["count"] += 1
        t, left = start, s["seconds"]
        while left > 0:
            nxt = t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            part = min(left, int((nxt - t).total_seconds()))
            hours[t.hour] += part
            left -= part
            t = nxt
    channels = sorted(per.values(), key=lambda i: (-i["seconds"], i["entry"]["channel"].lower()))
    return {"total": total, "count": count, "channels": channels[:top], "hours": hours}


def peak_hours(hours, n=3):
    """Les n heures les plus regardées (avec du temps), de la plus regardée à la moins regardée.

    The n most watched hours (with some time), from the most watched to the least."""
    return sorted((h for h in range(24) if hours[h]), key=lambda h: (-hours[h], h))[:n]


def format_duration(t, seconds):
    """'45 min', '2 h 05' — avec les traductions duration_*.

    '45 min', '2 h 05' — with the duration_* translations."""
    minutes = max(0, seconds) // 60
    if minutes < 60:
        return t("minutes", count=minutes)
    return t("duration_hours", hours=minutes // 60, minutes=f"{minutes % 60:02d}")
