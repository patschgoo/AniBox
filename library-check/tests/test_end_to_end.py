import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anibox_check import cli, plex
from tests.fake_plex import TOKEN, FakePlex
from tests.fixtures import make_fixtures as fx


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        self.out = Path(self.tmp.name) / "out"
        fx.write_datasets(self.data)
        # Keep settings out of the real home folder.
        patcher = mock.patch.object(cli, "settings_path", return_value=Path(self.tmp.name) / "settings.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, server, token, *extra):
        return cli.main(["--server", server, "--token", token, "--offline", "--data-dir", str(self.data),
                         "--out", str(self.out), "--no-open", *extra])

    def test_full_run_is_read_only_and_writes_reports(self):
        with FakePlex() as fake, mock.patch.object(plex, "PAGE_SIZE", 3):  # force several pages
            code = self.run_cli(fake.url, TOKEN, "--library", "Anime", "--library", "Anime Movies")
            methods = {m for m, _ in fake.requests}
            paths = [p for _, p in fake.requests]
        self.assertEqual(code, 0)
        self.assertEqual(methods, {"GET"}, "the report must only ever read from Plex")
        self.assertGreater(sum("type=4" in p for p in paths), 1, "episodes should be fetched in pages")

        html_files = list(self.out.glob("AniBox-Report-*.html"))
        csv_files = list(self.out.glob("AniBox-Report-*.csv"))
        self.assertEqual(len(html_files), 1)
        self.assertEqual(len(csv_files), 1)
        page = html_files[0].read_text(encoding="utf-8")
        self.assertIn("Sousou no Frieren 2nd Season", page)
        self.assertIn("Incomplete", page)
        self.assertIn("Some Western Show", page)
        self.assertIn("SHIELD", page)

        with open(csv_files[0], encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        status = {r["title"]: r["status"] for r in rows}
        self.assertEqual(status["Naruto"], "Missing")
        self.assertEqual(status["The Last: Naruto the Movie"], "Have")
        self.assertEqual(status["Sousou no Frieren 2nd Season"], "Incomplete")
        self.assertEqual(status["Mononoke Hime"], "Have")

    def test_wrong_token_fails_cleanly(self):
        with FakePlex() as fake:
            code = self.run_cli(fake.url, "wrong")
        self.assertEqual(code, 1)
        self.assertFalse(self.out.exists() and any(self.out.iterdir()))

    def test_unknown_library_name(self):
        with FakePlex() as fake:
            with self.assertRaises(SystemExit) as ctx:
                self.run_cli(fake.url, TOKEN, "--library", "Nope")
        self.assertIn("Library not found", str(ctx.exception))

    def test_unreachable_server(self):
        with mock.patch("anibox_check.plex.time.sleep"):
            code = self.run_cli("http://127.0.0.1:9", TOKEN)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
