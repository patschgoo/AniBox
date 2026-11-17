"""Turn Plex GUID strings into external IDs (TVDB, TMDB, IMDb, AniDB, MyAnimeList).

Plex stores the match of every item as a GUID. Depending on which agent matched it,
the GUID looks very different:

- Modern Plex agents: ``plex://show/5d9c...`` plus a ``Guid`` list such as
  ``tvdb://78857``, ``tmdb://46260``, ``imdb://tt0409591``.
- Legacy agents: ``com.plexapp.agents.thetvdb://78857?lang=en``,
  ``com.plexapp.agents.themoviedb://46260?lang=en``, ``com.plexapp.agents.imdb://tt0409591``.
- HAMA: ``com.plexapp.agents.hama://anidb-239?lang=en`` (also ``tvdb3-``, ``tmdb-``, ...).
- Fribb's MyAnimeList.bundle: ``net.fribbtastic.coding.plex.myanimelist://20?lang=en``.
- Custom metadata providers (PMS 1.43+): ``tv.plex.agents.custom.<name>.tvdb://show/78874``.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

# Kinds returned by parse_guid.
MAL = "mal"
ANIDB = "anidb"
TVDB = "tvdb"
TMDB = "tmdb"
IMDB = "imdb"

_IMDB_RE = re.compile(r"(tt\d+)")
_DIGITS_RE = re.compile(r"(\d+)")


def _kind_from_word(word: str) -> Optional[str]:
    word = word.lower()
    if "myanimelist" in word or word == "mal":
        return MAL
    if word.startswith("anidb"):
        return ANIDB
    if word in ("thetvdb", "tvdb") or re.fullmatch(r"tvdb\d*", word):
        return TVDB
    if word in ("themoviedb", "tmdb") or re.fullmatch(r"tmdb\d*", word):
        return TMDB
    if word == "imdb":
        return IMDB
    return None


def _kind_from_scheme(scheme: str) -> Optional[str]:
    # Check the most specific words first, e.g. "...myanimelist" before any other token.
    tokens = re.split(r"[.\-_]", scheme.lower())
    for token in reversed(tokens):
        kind = _kind_from_word(token)
        if kind:
            return kind
    return None


def _extract_id(kind: str, value: str) -> Optional[str]:
    if kind == IMDB:
        m = _IMDB_RE.search(value)
        return m.group(1) if m else None
    m = _DIGITS_RE.search(value)
    return m.group(1) if m else None


def parse_guid(guid: str) -> Optional[Tuple[str, str]]:
    """Return ``(kind, id)`` for a Plex GUID, or ``None`` if it carries no usable external ID."""
    if not guid or "://" not in guid:
        return None
    scheme, rest = guid.split("://", 1)
    rest = rest.split("?", 1)[0].strip("/")
    if not rest:
        return None
    scheme_l = scheme.lower()
    if scheme_l in ("plex", "local", "file") or scheme_l.endswith(".shoko") or "shokorelay" in scheme_l:
        return None

    # The last path segment holds the ID ("show/78874" -> "78874", "movie/tmdb-movie-19934").
    segment = rest.split("/")[-1] if scheme_l.startswith("tv.plex.agents.custom.") else rest.split("/")[0]

    kind = None
    if "hama" in scheme_l or "-" in segment:
        # Values like "anidb-239", "tvdb3-78857", "tmdb-movie-19934" name their own source.
        prefix, _, value = segment.partition("-")
        kind = _kind_from_word(prefix)
        if kind is not None:
            segment = value
    if kind is None:
        kind = _kind_from_scheme(scheme_l)
    if kind is None:
        return None
    ident = _extract_id(kind, segment)
    return (kind, ident) if ident else None


def external_ids(guids: Iterable[str]) -> dict:
    """Collect every external ID from a list of GUID strings into ``{kind: set(ids)}``."""
    found: dict = {}
    for g in guids:
        parsed = parse_guid(g)
        if parsed:
            kind, ident = parsed
            found.setdefault(kind, set()).add(ident)
    return found
