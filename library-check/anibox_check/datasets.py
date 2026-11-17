"""Download and cache the public anime datasets the report is built from.

No account or API key is needed. Three files are used:

- Fribb/anime-lists ``anime-list-full.json``: links MyAnimeList, AniDB, TVDB, TMDB and IMDb IDs,
  including which TVDB/TMDB season (0 = Specials) and episode offset an entry sits at.
- anime-offline-database (cedya77 fork, weekly, ODbL): titles, type, episode count, year, status,
  and "related anime" links, which the report turns into franchises.

The offline database is about 60 MB, so after downloading it is reduced to a small
``titles-v2.json`` with only the fields the report needs.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

MAPPING_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
OFFLINE_DB_URL = (
    "https://github.com/cedya77/anime-offline-database/releases/download/latest/"
    "anime-offline-database-minified.json"
)

MAPPING_FILE = "anime-list-full.json"
TITLES_FILE = "titles-v2.json"

MAX_AGE_SECONDS = 7 * 24 * 3600
USER_AGENT = "AniBox-LibraryCheck/0.1"

_MAL_URL_RE = re.compile(r"myanimelist\.net/anime/(\d+)")
_ANIDB_URL_RE = re.compile(r"anidb\.net/anime/(\d+)")


def default_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "AniBox" / "data"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "anibox"


def _download(url: str, dest: Path, log: Callable[[str], None]) -> None:
    log(f"Downloading {url.rsplit('/', 1)[-1]} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    os.replace(tmp, dest)


def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < MAX_AGE_SECONDS


def reduce_offline_db(raw_path: Path, out_path: Path) -> int:
    """Keep only the fields the report needs, keyed by MAL ID. Returns the number of entries kept."""
    with open(raw_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    titles = {}
    for entry in raw.get("data", []):
        mal_id = anidb_id = None
        for src in entry.get("sources", []):
            m = _MAL_URL_RE.search(src)
            if m:
                mal_id = m.group(1)
            m = _ANIDB_URL_RE.search(src)
            if m:
                anidb_id = m.group(1)
        if not mal_id:
            continue
        related = sorted({m.group(1) for r in entry.get("relatedAnime", []) for m in [_MAL_URL_RE.search(r)] if m})
        duration = (entry.get("duration") or {}).get("value")
        season = entry.get("animeSeason") or {}
        titles[mal_id] = {
            "title": entry.get("title"),
            "type": entry.get("type"),
            "episodes": entry.get("episodes"),
            "status": entry.get("status"),
            "year": season.get("year"),
            "season": season.get("season"),
            "duration": duration,
            "thumbnail": entry.get("thumbnail"),
            "anidb": anidb_id,
            "rel": related,
        }
    payload = {
        "source": raw.get("repository"),
        "license": (raw.get("license") or {}).get("name"),
        "lastUpdate": raw.get("lastUpdate"),
        "titles": titles,
    }
    tmp = out_path.with_suffix(".part")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    return len(titles)


class Datasets:
    """The datasets, loaded into memory."""

    def __init__(self, mapping: list, titles: dict, titles_meta: Optional[dict] = None):
        self.mapping = mapping
        self.titles = titles
        self.titles_meta = titles_meta or {}

    @classmethod
    def load(cls, data_dir: Path) -> "Datasets":
        with open(data_dir / MAPPING_FILE, encoding="utf-8") as fh:
            mapping = json.load(fh)
        with open(data_dir / TITLES_FILE, encoding="utf-8") as fh:
            titles_payload = json.load(fh)
        meta = {k: v for k, v in titles_payload.items() if k != "titles"}
        return cls(mapping, titles_payload["titles"], meta)


def ensure_datasets(
    data_dir: Path,
    refresh: bool = False,
    offline: bool = False,
    log: Callable[[str], None] = print,
) -> Datasets:
    """Make sure all datasets are present and reasonably fresh, then load them.

    Downloads happen only when a file is missing, older than a week, or ``refresh`` is set.
    If a download fails but an older copy exists, the older copy is used.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        (MAPPING_URL, data_dir / MAPPING_FILE, None),
        (OFFLINE_DB_URL, data_dir / "anime-offline-database-minified.json", data_dir / TITLES_FILE),
    ]
    for url, raw_path, reduced_path in jobs:
        final_path = reduced_path or raw_path
        if offline:
            if not final_path.exists():
                raise FileNotFoundError(
                    f"{final_path.name} is not in {data_dir}. Run once without --offline to download it."
                )
            continue
        if final_path.exists() and _is_fresh(final_path) and not refresh:
            continue
        try:
            _download(url, raw_path, log)
            if reduced_path:
                count = reduce_offline_db(raw_path, reduced_path)
                raw_path.unlink(missing_ok=True)
                log(f"  kept {count} titles")
        except Exception as exc:  # network problems, GitHub down, ...
            if final_path.exists():
                log(f"  download failed ({exc}); using the copy from {time.ctime(final_path.stat().st_mtime)}")
            else:
                raise RuntimeError(f"Could not download {url}: {exc}") from exc
    return Datasets.load(data_dir)
