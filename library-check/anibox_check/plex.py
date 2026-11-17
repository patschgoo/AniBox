"""A deliberately read-only Plex Media Server client.

Only HTTP GET requests are ever sent, so the report cannot change matches, metadata,
watch states or settings on the server.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from . import __version__
from .ids import external_ids

PAGE_SIZE = 500

# Plex item type numbers used by /library/sections/{id}/all?type=N
TYPE_MOVIE = 1
TYPE_SHOW = 2
TYPE_EPISODE = 4


class PlexError(Exception):
    pass


@dataclass
class Section:
    key: str
    title: str
    type: str  # "show" or "movie"
    agent: str = ""
    ordering: str = ""  # library-wide episode ordering, e.g. "tmdbAiring", "tvdbAiring"


@dataclass
class PlexItem:
    rating_key: str
    title: str
    year: Optional[int]
    type: str  # "show" or "movie"
    section: str
    guid: str = ""
    ids: Dict[str, Set[str]] = field(default_factory=dict)
    ordering: str = ""  # per-show override of the episode ordering
    episodes: Set[Tuple[int, int]] = field(default_factory=set)  # (season, episode)

    def season_episodes(self, season: int) -> Set[int]:
        return {e for s, e in self.episodes if s == season}

    @property
    def episode_count(self) -> int:
        return len(self.episodes)


class PlexReader:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        if "://" not in base_url:
            base_url = "http://" + base_url
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.port and parsed.scheme == "http":
            base_url = f"{parsed.scheme}://{parsed.hostname}:32400"
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # -- low level ---------------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("X-Plex-Token", self.token)
        req.add_header("X-Plex-Product", "AniBox Library Check")
        req.add_header("X-Plex-Version", __version__)
        req.add_header("X-Plex-Client-Identifier", "anibox-library-check")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                return json.loads(body.decode("utf-8")) if body else {}
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    raise PlexError(
                        "Plex rejected the token (HTTP %d). Get a fresh X-Plex-Token and try again." % exc.code
                    ) from exc
                raise PlexError(f"Plex answered HTTP {exc.code} for {path}") from exc
            except (urllib.error.URLError, socket.timeout, ConnectionError) as exc:
                # A sleeping Shield can take a moment to answer; retry a couple of times.
                last_error = exc
                time.sleep(3 * (attempt + 1))
        raise PlexError(
            f"Could not reach Plex at {self.base_url} ({last_error}). "
            "Is the Shield awake and on the same network? Try opening "
            f"{self.base_url}/web in a browser."
        )

    def _paged(self, path: str, params: dict) -> List[dict]:
        items: List[dict] = []
        start = 0
        while True:
            data = self._get(
                path,
                params,
                headers={"X-Plex-Container-Start": str(start), "X-Plex-Container-Size": str(PAGE_SIZE)},
            )
            mc = data.get("MediaContainer", {})
            page = mc.get("Metadata", []) or []
            items.extend(page)
            total = mc.get("totalSize")
            start += len(page)
            if not page or total is None or start >= int(total):
                break
        return items

    # -- library -------------------------------------------------------------------------------

    def identity(self) -> dict:
        return self._get("/identity").get("MediaContainer", {})

    def sections(self) -> List[Section]:
        data = self._get("/library/sections")
        out = []
        for d in data.get("MediaContainer", {}).get("Directory", []) or []:
            if d.get("type") in ("show", "movie"):
                out.append(Section(key=str(d["key"]), title=d.get("title", ""), type=d["type"], agent=d.get("agent", "")))
        return out

    def section_ordering(self, section: Section) -> str:
        if section.type != "show":
            return ""
        try:
            data = self._get(f"/library/sections/{section.key}/prefs")
        except PlexError:
            return ""
        for s in data.get("MediaContainer", {}).get("Setting", []) or []:
            if s.get("id") == "showOrdering":
                return str(s.get("value") or s.get("default") or "")
        return ""

    def items(self, section: Section) -> List[PlexItem]:
        type_num = TYPE_SHOW if section.type == "show" else TYPE_MOVIE
        raw = self._paged(f"/library/sections/{section.key}/all", {"type": type_num, "includeGuids": 1})
        items: List[PlexItem] = []
        by_key: Dict[str, PlexItem] = {}
        for m in raw:
            guids = [m.get("guid", "")] + [g.get("id", "") for g in (m.get("Guid") or [])]
            year = m.get("year")
            item = PlexItem(
                rating_key=str(m.get("ratingKey")),
                title=m.get("title", ""),
                year=int(year) if isinstance(year, (int, str)) and str(year).isdigit() else None,
                type=section.type,
                section=section.title,
                guid=m.get("guid", ""),
                ids=external_ids(guids),
                ordering=str(m.get("showOrdering") or ""),
            )
            items.append(item)
            by_key[item.rating_key] = item
        if section.type == "show":
            for ep in self._paged(f"/library/sections/{section.key}/all", {"type": TYPE_EPISODE}):
                show = by_key.get(str(ep.get("grandparentRatingKey")))
                season, number = ep.get("parentIndex"), ep.get("index")
                if show is not None and season is not None and number is not None:
                    show.episodes.add((int(season), int(number)))
        return items
