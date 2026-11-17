"""Work out which anime entries (by MyAnimeList ID) the library has, and which are missing.

How it works:

1. Every Plex show/movie carries external IDs from its existing match (TVDB, TMDB, IMDb,
   or AniDB/MAL from older agents). Nothing is re-matched.
2. The anime-lists mapping says which MyAnimeList entries live inside that TVDB/TMDB show,
   and where: season N, or Specials (season 0) starting after a given episode offset.
3. Comparing that with the episodes Plex actually has gives owned / partial / missing.
4. Franchise groups (related MAL entries) then reveal sequels, OVAs, specials and movies
   that are not in the library at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .datasets import Datasets
from .ids import ANIDB, IMDB, MAL, TMDB, TVDB
from .plex import PlexItem

# Statuses, best first.
OWNED = "owned"
PARTIAL = "partial"
UNSURE = "unsure"
MISSING = "missing"
UPCOMING = "upcoming"

STATUS_RANK = {OWNED: 0, PARTIAL: 1, UNSURE: 2, MISSING: 3, UPCOMING: 4}

SHORT_SECONDS = 5 * 60  # entries with episodes shorter than this are usually promos, CMs, recaps


@dataclass
class EntryResult:
    mal_id: str
    title: str
    type: str
    episodes: Optional[int]
    year: Optional[int]
    status: str
    detail: str  # where it is / where it would go
    plex_title: str = ""  # Plex item it was found in
    have: Optional[int] = None  # episodes present, for partial
    anidb_id: Optional[str] = None
    thumbnail: Optional[str] = None
    short: bool = False
    airing: str = ""

    @property
    def mal_url(self) -> str:
        return f"https://myanimelist.net/anime/{self.mal_id}"

    @property
    def anidb_url(self) -> Optional[str]:
        return f"https://anidb.net/anime/{self.anidb_id}" if self.anidb_id else None


@dataclass
class Franchise:
    name: str
    entries: List[EntryResult] = field(default_factory=list)

    def count(self, *statuses: str, include_short: bool = False) -> int:
        return sum(1 for e in self.entries if e.status in statuses and (include_short or not e.short))


@dataclass
class Report:
    franchises: List[Franchise]
    unidentified: List[PlexItem]
    scanned: int
    identified: int
    titles_meta: dict = field(default_factory=dict)


class _Index:
    def __init__(self, ds: Datasets):
        self.by_mal: Dict[str, dict] = {}
        self.by_anidb: Dict[str, List[dict]] = {}
        self.by_tvdb: Dict[str, List[dict]] = {}
        self.by_tmdb_tv: Dict[str, List[dict]] = {}
        self.by_tmdb_movie: Dict[str, List[dict]] = {}
        self.by_imdb: Dict[str, List[dict]] = {}
        for e in ds.mapping:
            if e.get("mal_id") is not None:
                self.by_mal[str(e["mal_id"])] = e
            if e.get("anidb_id") is not None:
                self.by_anidb.setdefault(str(e["anidb_id"]), []).append(e)
            if e.get("tvdb_id") is not None:
                self.by_tvdb.setdefault(str(e["tvdb_id"]), []).append(e)
            tmdb = e.get("themoviedb_id") or {}
            if tmdb.get("tv") is not None:
                self.by_tmdb_tv.setdefault(str(tmdb["tv"]), []).append(e)
            for mid in _as_list(tmdb.get("movie")):
                self.by_tmdb_movie.setdefault(str(mid), []).append(e)
            for imdb in _as_list(e.get("imdb_id")):
                self.by_imdb.setdefault(str(imdb), []).append(e)


class FranchiseGraph:
    """Franchises built from the "related anime" links in the offline database.

    - Only links listed in both directions count, which drops one-sided noise.
    - Short clips (CMs, PVs, music videos) and crossovers/collabs ("Naruto x Ninkuu",
      "Snickers x Shingeki no Kyojin") never connect two entries. Otherwise a single shared
      commercial merges unrelated films into one "franchise". They still show up next to the
      entries they belong to.
    - Some old franchises are tied together by crossovers (Lupin III / Detective Conan,
      Fujiko F. Fujio, Tezuka). For groups bigger than BIG_GROUP only entries within
      NEAR_HOPS links of something you own are listed.
    """

    BIG_GROUP = 100
    NEAR_HOPS = 3

    def __init__(self, titles: Dict[str, dict]):
        self.titles = titles
        self.adj: Dict[str, Set[str]] = {}
        for a, info in titles.items():
            for b in info.get("rel") or ():
                b = str(b)
                other = titles.get(b)
                if other is not None and a in {str(x) for x in other.get("rel") or ()}:
                    self.adj.setdefault(a, set()).add(b)
                    self.adj.setdefault(b, set()).add(a)
        self.short = {m for m, info in titles.items() if _is_short(info) or _is_crossover(info.get("title"))}
        self.comp_of: Dict[str, int] = {}
        self.comps: List[List[str]] = []
        for m in titles:
            if m in self.short or m in self.comp_of:
                continue
            comp, stack = [], [m]
            self.comp_of[m] = len(self.comps)
            while stack:
                x = stack.pop()
                comp.append(x)
                for y in self.adj.get(x, ()):
                    if y not in self.comp_of and y not in self.short:
                        self.comp_of[y] = len(self.comps)
                        stack.append(y)
            self.comps.append(comp)

    def _core_neighbors_comp(self, mal_id: str) -> Set[int]:
        return {self.comp_of[n] for n in self.adj.get(mal_id, ()) if n in self.comp_of}

    def _near(self, comp: List[str], starts: Set[str]) -> Set[str]:
        allowed = set(comp)
        seen = {s for s in starts if s in allowed}
        frontier = set(seen)
        for _ in range(self.NEAR_HOPS):
            frontier = {y for x in frontier for y in self.adj.get(x, ()) if y in allowed and y not in seen}
            seen |= frontier
        return seen

    def franchises_for(self, have: Set[str]) -> List[List[str]]:
        """Group the given MAL IDs into franchises and add every related entry."""
        by_comp: Dict[int, Set[str]] = {}
        loose: List[str] = []
        for m in have:
            if m in self.comp_of:
                by_comp.setdefault(self.comp_of[m], set()).add(m)
            else:
                comps = self._core_neighbors_comp(m) if m in self.short else set()
                if comps:
                    for c in comps:
                        by_comp.setdefault(c, set()).add(m)
                else:
                    loose.append(m)
        out: List[List[str]] = []
        for c, starts in by_comp.items():
            comp = self.comps[c]
            members = set(comp) if len(comp) <= self.BIG_GROUP else self._near(comp, starts)
            members |= starts
            # Short clips hang off the entries they relate to.
            members |= {y for x in list(members) for y in self.adj.get(x, ()) if y in self.short}
            out.append(sorted(members))
        out.extend([m] for m in loose)
        return out

    def name_for(self, members: List[str], results: Dict[str, "EntryResult"]) -> str:
        """Name a franchise after the earliest TV series you have or that is directly related to
        one you have; fall back to the earliest entry."""
        def key(m):
            info = self.titles.get(m, {})
            return (info.get("year") or 9999, int(m) if m.isdigit() else 0)
        have = [m for m in members if m in results]
        near = set(have) | {y for x in have for y in self.adj.get(x, ()) if y not in self.short}
        tv_near = [m for m in members if m in near and self.titles.get(m, {}).get("type") == "TV"]
        tv = [m for m in members if self.titles.get(m, {}).get("type") == "TV" and m not in self.short]
        pick = min(tv_near or tv or have or members, key=key)
        info = self.titles.get(pick)
        if info and info.get("title"):
            return info["title"]
        r = results.get(pick)
        return r.title if r else f"MAL #{pick}"


_CROSSOVER_RE = re.compile(r"(\S+)\s+[x×]\s+(\S+)", re.IGNORECASE)


def _is_crossover(title: Optional[str]) -> bool:
    """'Naruto x Ninkuu' or 'Snickers x Shingeki no Kyojin', but not 'Hunter x Hunter'."""
    if not title:
        return False
    m = _CROSSOVER_RE.search(title)
    return bool(m) and m.group(1).strip(":!?,.").lower() != m.group(2).strip(":!?,.").lower()


def _is_short(info: dict) -> bool:
    duration = info.get("duration")
    return bool(duration) and duration < SHORT_SECONDS


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _source_for(item: PlexItem, library_ordering: str) -> str:
    """Which numbering Plex uses for this show's seasons: 'tmdb', 'tvdb' or 'absolute'."""
    ordering = (item.ordering or library_ordering or "").lower()
    if "absolute" in ordering:
        return "absolute"
    if "tmdb" in ordering:
        return "tmdb"
    if "tvdb" in ordering or ordering in ("aired", "dvd"):
        return "tvdb"
    # Unknown: follow the IDs the match has.
    if TVDB in item.ids:
        return "tvdb"
    if TMDB in item.ids:
        return "tmdb"
    return "tvdb"


class Analyzer:
    def __init__(self, ds: Datasets):
        self.ds = ds
        self.idx = _Index(ds)
        self.graph = FranchiseGraph(ds.titles)

    # -- helpers -------------------------------------------------------------------------------

    def _info(self, mal_id: str) -> dict:
        return self.ds.titles.get(mal_id) or {}

    def _result(self, entry: dict, status: str, detail: str, plex_title: str = "", have=None) -> Optional[EntryResult]:
        if entry.get("mal_id") is None:
            return None
        mal_id = str(entry["mal_id"])
        info = self._info(mal_id)
        duration = info.get("duration")
        anidb = entry.get("anidb_id") or info.get("anidb")
        result = EntryResult(
            mal_id=mal_id,
            title=info.get("title") or f"MAL #{mal_id}",
            type=info.get("type") or entry.get("type") or "UNKNOWN",
            episodes=info.get("episodes"),
            year=info.get("year"),
            status=status,
            detail=detail,
            plex_title=plex_title,
            have=have,
            anidb_id=str(anidb) if anidb else None,
            thumbnail=info.get("thumbnail"),
            short=bool(duration) and duration < SHORT_SECONDS,
            airing=info.get("status") or "",
        )
        if status == MISSING and info.get("status") == "UPCOMING":
            result.status = UPCOMING
        return result

    # -- show matching -------------------------------------------------------------------------

    def _entries_for_show(self, item: PlexItem) -> Tuple[List[Tuple[dict, str]], str]:
        """Mapping entries for a Plex show and how they were found ('mal', 'anidb', 'tvdb', 'tmdb', 'imdb')."""
        found: List[Tuple[dict, str]] = []
        seen: Set[int] = set()

        def add(entries: Iterable[dict], how: str):
            for e in entries:
                if id(e) not in seen:
                    seen.add(id(e))
                    found.append((e, how))

        for mid in item.ids.get(MAL, ()):
            if mid in self.idx.by_mal:
                add([self.idx.by_mal[mid]], "mal")
        for aid in item.ids.get(ANIDB, ()):
            add(self.idx.by_anidb.get(aid, []), "anidb")
        if found:
            return found, "direct"
        for tid in item.ids.get(TVDB, ()):
            add(self.idx.by_tvdb.get(tid, []), "tvdb")
        for tid in item.ids.get(TMDB, ()):
            add(self.idx.by_tmdb_tv.get(tid, []), "tmdb")
        if found:
            return found, "mapped"
        for iid in item.ids.get(IMDB, ()):
            add([e for e in self.idx.by_imdb.get(iid, []) if e.get("type") in ("TV", "ONA", "OVA")], "imdb")
        return found, "imdb" if found else "none"

    def _place_in_show(self, item: PlexItem, entry: dict, library_ordering: str) -> EntryResult:
        source = _source_for(item, library_ordering)
        title = item.title
        mal_id = str(entry.get("mal_id"))
        info = self._info(mal_id)
        n_eps = info.get("episodes") or 0
        season_map = entry.get("season") or {}
        offset_map = entry.get("episode_offset") or {}
        key = "tmdb" if source == "tmdb" else "tvdb"
        season = season_map.get(key, season_map.get("tvdb" if key == "tmdb" else "tmdb"))
        offset = offset_map.get(key)

        if source == "absolute" or season is None:
            # Absolute numbering or the entry spans the whole show: we can only see whether the show has episodes.
            if item.episode_count:
                return self._result(entry, OWNED, "Part of this show (absolute numbering)", title)
            return self._result(entry, MISSING, "Show has no episodes", title)

        season = int(season)
        present = item.season_episodes(season)
        where = "Specials" if season == 0 else f"Season {season}"

        if season == 0 and offset is None:
            # Somewhere in Specials, but the exact episode numbers aren't known.
            if present:
                return self._result(
                    entry, UNSURE, f"Specials (Season 0): you have {len(present)} special(s); check which", title
                )
            return self._result(entry, MISSING, "Would go in Specials (Season 0)", title)

        start = int(offset or 0) + 1
        if n_eps:
            wanted = set(range(start, start + int(n_eps)))
            have = len(wanted & present)
            span = f"S{season:02d}E{start:02d}" + (f"–E{start + int(n_eps) - 1:02d}" if n_eps > 1 else "")
            if have == len(wanted):
                return self._result(entry, OWNED, f"{where} ({span})", title, have=have)
            if have:
                return self._result(entry, PARTIAL, f"{where} ({span}): {have} of {n_eps} episodes", title, have=have)
            return self._result(entry, MISSING, f"Would go in {where} ({span})", title, have=0)
        # Episode count unknown (often still airing): any episode in range counts.
        if any(e >= start for e in present):
            return self._result(entry, OWNED, f"{where} (from E{start:02d})", title)
        return self._result(entry, MISSING, f"Would go in {where} (from E{start:02d})", title)

    # -- main ----------------------------------------------------------------------------------

    def analyze(
        self,
        shows: List[PlexItem],
        movies: List[PlexItem],
        orderings: Optional[Dict[str, str]] = None,
    ) -> Report:
        orderings = orderings or {}
        results: Dict[str, EntryResult] = {}
        unidentified: List[PlexItem] = []
        identified = 0

        def keep(r: Optional[EntryResult]):
            if r is None:
                return
            old = results.get(r.mal_id)
            if old is None or STATUS_RANK[r.status] < STATUS_RANK[old.status]:
                results[r.mal_id] = r

        for show in shows:
            entries, how = self._entries_for_show(show)
            if not entries:
                unidentified.append(show)
                continue
            identified += 1
            if how == "direct":
                # Older anime agents matched this show to one MAL/AniDB entry: the show *is* that entry.
                for e, _ in entries:
                    keep(self._result(e, OWNED if show.episode_count else MISSING, "This show", show.title))
            elif how == "imdb" and len(entries) > 1:
                for e, _ in entries:
                    keep(self._result(e, UNSURE, "Matched only by IMDb; check", show.title))
            else:
                for e, _ in entries:
                    keep(self._place_in_show(show, e, orderings.get(show.section, "")))

        for movie in movies:
            entries: List[dict] = []
            for mid in movie.ids.get(MAL, ()):
                if mid in self.idx.by_mal:
                    entries.append(self.idx.by_mal[mid])
            for aid in movie.ids.get(ANIDB, ()):
                entries.extend(self.idx.by_anidb.get(aid, []))
            for tid in movie.ids.get(TMDB, ()):
                entries.extend(self.idx.by_tmdb_movie.get(tid, []))
            if not entries:
                for iid in movie.ids.get(IMDB, ()):
                    entries.extend(e for e in self.idx.by_imdb.get(iid, []) if e.get("type") == "MOVIE")
            if entries:
                identified += 1
            for e in entries:
                keep(self._result(e, OWNED, "Movie library", movie.title))

        # Franchises: everything related to what you have.
        owned_show_ids = self._owned_show_ids(shows)
        all_fr: List[Franchise] = []
        for members in self.graph.franchises_for(set(results)):
            fr = Franchise(self.graph.name_for(members, results))
            for mid in members:
                if mid in results:
                    fr.entries.append(results[mid])
                    continue
                entry = self.idx.by_mal.get(mid) or {"mal_id": mid}
                r = self._result(entry, MISSING, self._suggest_place(entry, owned_show_ids))
                if r:
                    fr.entries.append(r)
            all_fr.append(fr)

        for fr in all_fr:
            fr.entries.sort(key=lambda e: (e.year or 9999, e.title.lower()))
        all_fr.sort(key=lambda f: f.name.lower())
        return Report(
            franchises=all_fr,
            unidentified=sorted(unidentified, key=lambda i: i.title.lower()),
            scanned=len(shows) + len(movies),
            identified=identified,
            titles_meta=self.ds.titles_meta,
        )

    def _owned_show_ids(self, shows: List[PlexItem]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for s in shows:
            for kind in (TVDB, TMDB):
                for i in s.ids.get(kind, ()):
                    out[f"{kind}:{i}"] = s.title
        return out

    def _suggest_place(self, entry: dict, owned: Dict[str, str]) -> str:
        """Where a missing entry would show up in Plex with the built-in agents."""
        tvdb = entry.get("tvdb_id")
        tmdb = entry.get("themoviedb_id") or {}
        season = (entry.get("season") or {}).get("tvdb")
        where = ""
        if season is not None:
            where = "Specials" if int(season) == 0 else f"Season {season}"
        suffix = f" → {where}" if where else ""
        for key in (f"tvdb:{tvdb}" if tvdb is not None else None, f"tmdb:{tmdb.get('tv')}" if tmdb.get("tv") else None):
            if key and key in owned:
                return f"Would go in {owned[key]}{suffix}"
        if tvdb is not None:
            return f"Separate show on TVDB ({tvdb})" + (f", {where}" if where else "")
        if tmdb.get("tv") is not None:
            return f"Separate show on TMDB ({tmdb['tv']})" + (f", {where}" if where else "")
        if tmdb.get("movie"):
            return f"Movie on TMDB ({_as_list(tmdb['movie'])[0]}): add to a movie library"
        return "No TVDB/TMDB link known: Plex's built-in agents may not find it"
