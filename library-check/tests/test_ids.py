import unittest

from anibox_check.ids import external_ids, parse_guid


class ParseGuidTest(unittest.TestCase):
    def test_modern_plex_agent_ids(self):
        self.assertEqual(parse_guid("tvdb://79824"), ("tvdb", "79824"))
        self.assertEqual(parse_guid("tmdb://31910"), ("tmdb", "31910"))
        self.assertEqual(parse_guid("imdb://tt0988824"), ("imdb", "tt0988824"))

    def test_plex_internal_guid_is_ignored(self):
        self.assertIsNone(parse_guid("plex://show/5d9c086c46115600200aa2fe"))
        self.assertIsNone(parse_guid("local://12345"))
        self.assertIsNone(parse_guid(""))
        self.assertIsNone(parse_guid("not a guid"))

    def test_legacy_agents(self):
        self.assertEqual(parse_guid("com.plexapp.agents.thetvdb://78857?lang=en"), ("tvdb", "78857"))
        self.assertEqual(parse_guid("com.plexapp.agents.thetvdb://78857/1/3?lang=en"), ("tvdb", "78857"))
        self.assertEqual(parse_guid("com.plexapp.agents.themoviedb://46260?lang=en"), ("tmdb", "46260"))
        self.assertEqual(parse_guid("com.plexapp.agents.imdb://tt0409591?lang=en"), ("imdb", "tt0409591"))
        self.assertIsNone(parse_guid("com.plexapp.agents.none://abc"))
        self.assertIsNone(parse_guid("com.plexapp.agents.localmedia://12"))

    def test_old_myanimelist_agent(self):
        self.assertEqual(parse_guid("net.fribbtastic.coding.plex.myanimelist://20?lang=en"), ("mal", "20"))

    def test_hama(self):
        self.assertEqual(parse_guid("com.plexapp.agents.hama://anidb-239?lang=en"), ("anidb", "239"))
        self.assertEqual(parse_guid("com.plexapp.agents.hama://anidb3-4880?lang=en"), ("anidb", "4880"))
        self.assertEqual(parse_guid("com.plexapp.agents.hama://tvdb3-79824?lang=en"), ("tvdb", "79824"))
        self.assertEqual(parse_guid("com.plexapp.agents.hama://tmdb-128?lang=en"), ("tmdb", "128"))

    def test_shoko_ids_are_not_external(self):
        self.assertIsNone(parse_guid("com.plexapp.agents.shoko://123?lang=en"))
        self.assertIsNone(parse_guid("com.plexapp.agents.shokorelay://123?lang=en"))

    def test_custom_metadata_providers(self):
        # Examples from Plex's developer documentation.
        self.assertEqual(parse_guid("tv.plex.agents.custom.barkley.tvdb://show/78874"), ("tvdb", "78874"))
        self.assertEqual(parse_guid("tv.plex.agents.custom.johnz.tmdb://movie/tmdb-movie-19934"), ("tmdb", "19934"))
        self.assertEqual(parse_guid("tv.plex.agents.custom.finn.imdb://movie/tt0379786"), ("imdb", "tt0379786"))
        self.assertEqual(parse_guid("tv.plex.agents.custom.someone.myanimelist://show/52991"), ("mal", "52991"))

    def test_external_ids_collects_all(self):
        ids = external_ids(["plex://show/x", "tvdb://1", "tmdb://2", "imdb://tt3", "tvdb://1"])
        self.assertEqual(ids, {"tvdb": {"1"}, "tmdb": {"2"}, "imdb": {"tt3"}})


if __name__ == "__main__":
    unittest.main()
