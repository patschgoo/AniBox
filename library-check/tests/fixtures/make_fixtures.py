"""Small, hand-made datasets and Plex responses used by the tests.

IDs are real (Naruto Shippuden, Frieren, One Piece, Princess Mononoke) so the scenario is easy
to follow, but the data is trimmed to what the tests need.
"""

from __future__ import annotations

import json
from pathlib import Path

MAPPING = [
    # Naruto (original): its own TVDB show, not in the test library -> missing, separate show.
    {"type": "TV", "mal_id": 20, "anidb_id": 239, "tvdb_id": 78857, "themoviedb_id": {"tv": 46260}, "imdb_id": ["tt0409591"]},
    # Naruto Shippuden: whole TVDB show, no season -> absolute.
    {"type": "TV", "mal_id": 1735, "anidb_id": 4880, "tvdb_id": 79824, "themoviedb_id": {"tv": 31910}, "imdb_id": ["tt0988824"]},
    # Movies/OVAs that TVDB keeps in Shippuden's Specials.
    {"type": "MOVIE", "mal_id": 2472, "anidb_id": 5178, "tvdb_id": 79824, "themoviedb_id": {"tv": 31910},
     "season": {"tvdb": 0, "tmdb": 0}},
    {"type": "MOVIE", "mal_id": 16870, "anidb_id": 9588, "tvdb_id": 79824, "themoviedb_id": {"tv": 31910},
     "season": {"tvdb": 0, "tmdb": 0}, "episode_offset": {"tvdb": 11, "tmdb": 11}},
    {"type": "OVA", "mal_id": 10075, "anidb_id": 8159, "tvdb_id": 79824, "themoviedb_id": {"tv": 31910},
     "season": {"tvdb": 0, "tmdb": 0}, "imdb_id": ["tt0988824"]},
    # Frieren: season 1, season 2, a mini special with no TVDB/TMDB entry, and an upcoming movie.
    {"type": "TV", "mal_id": 52991, "anidb_id": 17617, "tvdb_id": 424536, "themoviedb_id": {"tv": 209867},
     "season": {"tvdb": 1, "tmdb": 1}},
    {"type": "TV", "mal_id": 59978, "anidb_id": 18966, "tvdb_id": 424536, "themoviedb_id": {"tv": 209867},
     "season": {"tvdb": 2, "tmdb": 2}},
    {"type": "SPECIAL", "mal_id": 56805, "anidb_id": 18011},
    {"type": "MOVIE", "mal_id": 99999},
    # One Piece, matched by HAMA in the test library.
    {"type": "TV", "mal_id": 21, "anidb_id": 69, "tvdb_id": 81797, "themoviedb_id": {"tv": 37854}},
    # Princess Mononoke, in a movie library.
    {"type": "MOVIE", "mal_id": 164, "anidb_id": 7, "themoviedb_id": {"movie": [128]}, "imdb_id": ["tt0119698"]},
]

# "Related anime" links (both directions), as in the offline database.
RELATED = [
    ("20", "1735"), ("1735", "2472"), ("1735", "16870"), ("1735", "10075"),
    ("52991", "59978"), ("52991", "56805"), ("59978", "99999"),
    # A commercial related to both Frieren and Mononoke must not merge the two.
    ("88888", "52991"), ("88888", "164"),
]


def _t(title, type_, eps, year, status="FINISHED", duration=1440, anidb=None):
    return {"title": title, "type": type_, "episodes": eps, "status": status, "year": year,
            "season": None, "duration": duration, "thumbnail": None, "anidb": anidb, "rel": []}


TITLES = {
    "source": "https://github.com/cedya77/anime-offline-database",
    "license": "ODbL",
    "lastUpdate": "2026-11-15",
    "titles": {
        "20": _t("Naruto", "TV", 220, 2002),
        "1735": _t("Naruto: Shippuuden", "TV", 500, 2007),
        "2472": _t("Naruto: Shippuuden Movie", "MOVIE", 1, 2007, duration=5640),
        "16870": _t("The Last: Naruto the Movie", "MOVIE", 1, 2014, duration=6720),
        "10075": _t("Naruto x UT", "OVA", 1, 2011, duration=360),
        "52991": _t("Sousou no Frieren", "TV", 28, 2023),
        "59978": _t("Sousou no Frieren 2nd Season", "TV", 10, 2026),
        "56805": _t("Sousou no Frieren: Mini Anime", "SPECIAL", 26, 2023, duration=120),
        "99999": _t("Sousou no Frieren Movie", "MOVIE", 1, 2027, status="UPCOMING"),
        "21": _t("One Piece", "TV", None, 1999, status="ONGOING"),
        "164": _t("Mononoke Hime", "MOVIE", 1, 1997, duration=8040),
        "88888": _t("Some Company x Anime CM", "SPECIAL", 1, 2024, duration=30),
    },
}
for _a, _b in RELATED:
    TITLES["titles"][_a]["rel"].append(_b)
    TITLES["titles"][_b]["rel"].append(_a)


def write_datasets(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "anime-list-full.json").write_text(json.dumps(MAPPING), encoding="utf-8")
    (data_dir / "titles-v2.json").write_text(json.dumps(TITLES), encoding="utf-8")


# ---- Fake Plex responses ------------------------------------------------------------------------

SECTIONS = {"MediaContainer": {"Directory": [
    {"key": "1", "type": "show", "title": "Anime", "agent": "tv.plex.agents.series"},
    {"key": "2", "type": "movie", "title": "Anime Movies", "agent": "tv.plex.agents.movie"},
    {"key": "3", "type": "artist", "title": "Music", "agent": "tv.plex.agents.music"},
]}}

SHOWS = [
    {"ratingKey": "100", "title": "Naruto Shippuden", "year": 2007, "guid": "plex://show/5d9c08",
     "Guid": [{"id": "imdb://tt0988824"}, {"id": "tmdb://31910"}, {"id": "tvdb://79824"}]},
    {"ratingKey": "200", "title": "Frieren: Beyond Journey's End", "year": 2023, "guid": "plex://show/6512",
     "Guid": [{"id": "tvdb://424536"}, {"id": "tmdb://209867"}]},
    {"ratingKey": "300", "title": "One Piece", "year": 1999, "guid": "com.plexapp.agents.hama://anidb-69?lang=en"},
    {"ratingKey": "400", "title": "Some Western Show", "year": 2015, "guid": "plex://show/abc",
     "Guid": [{"id": "tvdb://999999"}]},
]


def _eps(show_key, season, numbers):
    return [{"ratingKey": f"{show_key}{season:02d}{n:03d}", "type": "episode", "grandparentRatingKey": show_key,
             "parentIndex": season, "index": n} for n in numbers]


EPISODES = (
    _eps("100", 1, range(1, 4))
    + _eps("100", 0, [12])  # The Last (S00E12)
    + _eps("200", 1, range(1, 29))
    + _eps("200", 2, range(1, 6))
    + _eps("300", 1, range(1, 3))
)

MOVIES = [
    {"ratingKey": "500", "title": "Princess Mononoke", "year": 1997, "guid": "plex://movie/5d77",
     "Guid": [{"id": "imdb://tt0119698"}, {"id": "tmdb://128"}]},
    {"ratingKey": "600", "title": "Heat", "year": 1995, "guid": "plex://movie/5d78", "Guid": [{"id": "tmdb://949"}]},
]

PREFS = {"MediaContainer": {"Setting": [{"id": "showOrdering", "value": "", "default": ""}]}}
IDENTITY = {"MediaContainer": {"friendlyName": "SHIELD", "machineIdentifier": "abc"}}
