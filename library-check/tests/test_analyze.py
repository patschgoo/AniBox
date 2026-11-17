import copy
import unittest

from anibox_check.analyze import MISSING, OWNED, PARTIAL, UNSURE, UPCOMING, Analyzer, _is_crossover
from anibox_check.datasets import Datasets
from anibox_check.ids import external_ids
from anibox_check.plex import PlexItem
from tests.fixtures import make_fixtures as fx


def show(title, guids, episodes=(), ordering="", section="Anime"):
    return PlexItem(rating_key=title, title=title, year=None, type="show", section=section,
                    guid=guids[0] if guids else "", ids=external_ids(guids), ordering=ordering,
                    episodes=set(episodes))


def movie(title, guids):
    return PlexItem(rating_key=title, title=title, year=None, type="movie", section="Movies",
                    guid=guids[0], ids=external_ids(guids))


def eps(season, numbers):
    return [(season, n) for n in numbers]


def datasets():
    return Datasets(copy.deepcopy(fx.MAPPING), copy.deepcopy(fx.TITLES["titles"]), {"lastUpdate": "2026-11-15"})


def by_mal(report):
    return {e.mal_id: e for f in report.franchises for e in f.entries}


class AnalyzeTest(unittest.TestCase):
    def setUp(self):
        self.shows = [
            show("Naruto Shippuden", ["plex://show/1", "tvdb://79824", "tmdb://31910"], eps(1, range(1, 4)) + eps(0, [12])),
            show("Frieren", ["plex://show/2", "tvdb://424536"], eps(1, range(1, 29)) + eps(2, range(1, 6))),
            show("One Piece", ["com.plexapp.agents.hama://anidb-69?lang=en"], eps(1, [1, 2])),
            show("Some Western Show", ["plex://show/3", "tvdb://999999"], eps(1, [1])),
        ]
        self.movies = [movie("Princess Mononoke", ["plex://movie/1", "tmdb://128"]),
                       movie("Heat", ["plex://movie/2", "tmdb://949"])]
        self.report = Analyzer(datasets()).analyze(self.shows, self.movies)
        self.r = by_mal(self.report)

    def test_counts(self):
        self.assertEqual(self.report.scanned, 6)
        self.assertEqual(self.report.identified, 4)  # 3 anime shows + Mononoke
        self.assertEqual([i.title for i in self.report.unidentified], ["Some Western Show"])

    def test_absolute_main_series_is_owned(self):
        self.assertEqual(self.r["1735"].status, OWNED)
        self.assertIn("absolute", self.r["1735"].detail)

    def test_special_with_known_episode_number(self):
        self.assertEqual(self.r["16870"].status, OWNED)
        self.assertIn("S00E12", self.r["16870"].detail)

    def test_special_without_episode_number_is_unsure(self):
        self.assertEqual(self.r["2472"].status, UNSURE)
        self.assertEqual(self.r["10075"].status, UNSURE)

    def test_complete_and_partial_seasons(self):
        self.assertEqual(self.r["52991"].status, OWNED)
        self.assertEqual(self.r["59978"].status, PARTIAL)
        self.assertEqual(self.r["59978"].have, 5)
        self.assertIn("5 of 10", self.r["59978"].detail)

    def test_missing_franchise_members_with_suggestions(self):
        naruto = self.r["20"]
        self.assertEqual(naruto.status, MISSING)
        self.assertIn("Separate show on TVDB (78857)", naruto.detail)
        mini = self.r["56805"]
        self.assertEqual(mini.status, MISSING)
        self.assertTrue(mini.short)
        self.assertIn("No TVDB/TMDB link", mini.detail)
        self.assertEqual(self.r["99999"].status, UPCOMING)

    def test_legacy_hama_match_and_movie_library(self):
        self.assertEqual(self.r["21"].status, OWNED)
        self.assertEqual(self.r["21"].plex_title, "One Piece")
        self.assertEqual(self.r["164"].status, OWNED)
        self.assertNotIn("Heat", [e.title for e in self.r.values()])

    def test_franchise_grouping(self):
        names = {f.name: {e.mal_id for e in f.entries} for f in self.report.franchises}
        self.assertEqual(names["Naruto"], {"20", "1735", "2472", "16870", "10075"})
        self.assertEqual(names["Sousou no Frieren"], {"52991", "59978", "56805", "99999", "88888"})
        self.assertIn("One Piece", names)  # no related entries -> its own group

    def test_short_clip_does_not_merge_franchises(self):
        names = {f.name: {e.mal_id for e in f.entries} for f in self.report.franchises}
        self.assertEqual(names["Mononoke Hime"], {"164", "88888"})
        self.assertNotIn("52991", names["Mononoke Hime"])

    def test_crossover_titles(self):
        self.assertTrue(_is_crossover("Naruto x Ninkuu"))
        self.assertTrue(_is_crossover("Snickers x Shingeki no Kyojin"))
        self.assertTrue(_is_crossover("Naruto × UT"))
        self.assertFalse(_is_crossover("Hunter x Hunter (2011)"))
        self.assertFalse(_is_crossover("Hunter x Hunter: Greed Island"))
        self.assertFalse(_is_crossover("Sousou no Frieren"))
        self.assertFalse(_is_crossover(None))

    def test_crossover_does_not_merge_franchises(self):
        ds = datasets()
        ds.titles["700"] = fx._t("Ninkuu", "TV", 55, 1995)
        ds.titles["701"] = fx._t("Naruto x Ninkuu", "TV", 1, 2001, duration=None)
        for a, b in (("20", "701"), ("701", "700")):
            ds.titles[a]["rel"].append(b)
            ds.titles[b]["rel"].append(a)
        report = Analyzer(ds).analyze(self.shows, self.movies)
        names = {f.name: {e.mal_id for e in f.entries} for f in report.franchises}
        self.assertIn("Naruto", names)  # not named after the older Ninkuu
        self.assertIn("701", names["Naruto"])
        self.assertNotIn("700", names["Naruto"])

    def test_big_groups_only_list_nearby_entries(self):
        ds = datasets()
        chain = [str(900000 + i) for i in range(12)]  # a long chain of related entries
        for i, m in enumerate(chain):
            ds.titles[m] = fx._t(f"Chain {i}", "OVA", 1, 2000 + i)
        for a, b in zip(chain, chain[1:]):
            ds.titles[a]["rel"].append(b)
            ds.titles[b]["rel"].append(a)
        ds.mapping.append({"type": "OVA", "mal_id": int(chain[0]), "themoviedb_id": {"movie": [42]}})
        an = Analyzer(ds)
        an.graph.BIG_GROUP = 5
        report = an.analyze([], [movie("Chain 0", ["tmdb://42"])])
        ids = {e.mal_id for f in report.franchises for e in f.entries}
        self.assertEqual(ids, set(chain[:1 + an.graph.NEAR_HOPS]))

    def test_missing_season_in_owned_show_names_the_show(self):
        shows = [show("Frieren", ["tvdb://424536"], eps(1, range(1, 29)))]
        r = by_mal(Analyzer(datasets()).analyze(shows, []))
        self.assertEqual(r["59978"].status, MISSING)
        self.assertIn("Season 2", r["59978"].detail)
        self.assertEqual(r["59978"].plex_title, "Frieren")

    def test_specials_missing_when_show_has_no_specials(self):
        shows = [show("Naruto Shippuden", ["tvdb://79824"], eps(1, [1]))]
        r = by_mal(Analyzer(datasets()).analyze(shows, []))
        self.assertEqual(r["2472"].status, MISSING)
        self.assertIn("Specials", r["2472"].detail)
        self.assertEqual(r["16870"].status, MISSING)
        self.assertIn("S00E12", r["16870"].detail)

    def test_absolute_ordering_ignores_seasons(self):
        shows = [show("Frieren", ["tvdb://424536"], eps(1, range(1, 39)), ordering="tvdbAbsolute")]
        r = by_mal(Analyzer(datasets()).analyze(shows, []))
        self.assertEqual(r["59978"].status, OWNED)

    def test_tmdb_ordering_uses_tmdb_seasons(self):
        ds = datasets()
        ds.mapping.append({"type": "TV", "mal_id": 777, "tvdb_id": 5000, "themoviedb_id": {"tv": 6000},
                           "season": {"tvdb": 2, "tmdb": 1}})
        ds.titles["777"] = fx._t("Split Season Show", "TV", 3, 2020)
        s = show("Split", ["tmdb://6000", "tvdb://5000"], eps(1, [1, 2, 3]))
        r = by_mal(Analyzer(ds).analyze([s], [], {"Anime": "tmdbAiring"}))
        self.assertEqual(r["777"].status, OWNED)
        r = by_mal(Analyzer(ds).analyze([s], [], {"Anime": "tvdbAiring"}))
        self.assertEqual(r["777"].status, MISSING)

    def test_old_myanimelist_agent_match(self):
        shows = [show("Frieren", ["net.fribbtastic.coding.plex.myanimelist://52991?lang=en"], eps(1, [1]))]
        r = by_mal(Analyzer(datasets()).analyze(shows, []))
        self.assertEqual(r["52991"].status, OWNED)
        self.assertEqual(r["59978"].status, MISSING)
        self.assertIn("Separate show on TVDB (424536)", r["59978"].detail)


if __name__ == "__main__":
    unittest.main()
