# AniBox Library Check

A report that shows which **seasons, OVAs, specials and movies** are missing from your anime library in Plex,
grouped by franchise, with links to MyAnimeList and AniDB.

- **Read-only.** It only *reads* from your Plex server. Your matches, metadata, watch history and settings stay
  exactly as they are. (The tests check that only read requests are ever sent.)
- **Uses your existing matches.** Whatever Plex matched each show to (TVDB, TMDB, IMDb, or an older AniDB/HAMA
  or MyAnimeList agent) is the starting point. Nothing gets re-matched.
- **No accounts, no API keys, no Jikan.** It uses two free public datasets that are downloaded once a week:
  [Fribb/anime-lists](https://github.com/Fribb/anime-lists) (links MyAnimeList ↔ AniDB ↔ TVDB ↔ TMDB, including
  which special number a movie or OVA has) and the
  [anime-offline-database](https://github.com/cedya77/anime-offline-database) (titles, episode counts, related entries).
- **Runs whenever you want** on any computer in your home network (Windows, Mac, Linux, Raspberry Pi).
  Nothing has to stay running. The Shield wakes up when the report asks Plex for data.

## What the report tells you

| Status | Meaning |
|---|---|
| **Have** | Every episode of this entry is in your library. |
| **Incomplete** | Some episodes are there, e.g. "Season 2 (S02E01–E10): 4 of 10 episodes". |
| **Missing** | Not in your library. "Where in Plex" says where it would go, e.g. "Would go in Specials (S00E12)", "Would go in Season 4 (S04E17–E28)", or "Separate show on TVDB". |
| **Check** | It sits in the show's Specials (Season 0), you have some specials, but the exact special number isn't known. Look at it once by hand. |
| **Not out yet** | Announced but not released. |

"Where in Plex" uses the same numbering as Plex's built-in agents (TVDB/TMDB). Name a file like that
(`Show Name - S00E12.mkv` in the show's `Specials` folder, or `S04E17` in `Season 04`) and Plex puts it in the right place.

Short clips (commercials, music videos, promo videos under 5 minutes) are hidden by default. A checkbox shows them.

You get two files: `AniBox-Report-<date>.html` (opens in your browser) and `AniBox-Report-<date>.csv`
(the same list for Excel or LibreOffice).

## Setup (once)

1. **Python 3.9 or newer.** On Windows, install it from [python.org](https://www.python.org/downloads/) and tick
   **"Add python.exe to PATH"** in the installer. Nothing else needs to be installed.
2. **Get the AniBox folder** onto your computer (download the repository as a ZIP from GitHub and unpack it, or `git clone`).
3. **Find the Shield's address.** On the Shield: Settings → Device Preferences → About → Status → IP address.
   Plex listens on port 32400, so the address is like `http://192.168.178.50:32400`.
4. **Find your Plex token** (see below).

### Finding your Plex token

The token is how Plex knows the request comes from you. It's like a password: don't share it or post it anywhere.

1. Open Plex Web (app.plex.tv) and sign in.
2. Open any show or movie in your library.
3. Click **⋯** (More) → **Get Info** → **View XML**.
4. A new tab opens. At the end of its address is `X-Plex-Token=...`. Copy the part after the `=`.

Plex's own help page for this: [Finding an authentication token / X-Plex-Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

## Running it

**Windows:** double-click `run-check.bat` in the `library-check` folder.

**Mac / Linux / Raspberry Pi:** in a terminal, `./run-check.sh` in the `library-check` folder.

The first time, it asks for the Plex address and the token, and whether to remember them (saved in your user
folder under `AniBox/settings.json`, not in the AniBox folder). Then it lists your libraries and asks which to check.
Pick your anime libraries, including an anime movie library if you have one. The first run downloads about 70 MB
of anime data, which is reduced to about 15 MB and reused for a week.

### Options

```
run-check.bat --library "Anime" --library "Anime Movies"   check these libraries without asking
run-check.bat --posters        show small cover images (loaded from MyAnimeList's image server)
run-check.bat --out D:\Reports write the report files to another folder
run-check.bat --refresh-data   download the anime data again now
run-check.bat --offline        don't download anything, use the data from last time
```

`python -m anibox_check --help` lists everything.

## Good to know

- **Not found in the anime lists** at the bottom of the report lists shows that aren't anime, or that Plex
  matched without any TVDB/TMDB/IMDb ID. They're skipped.
- **Franchises** come from the "related anime" links in the offline database. Crossovers and commercials
  ("Naruto x Ninkuu", "Snickers x Shingeki no Kyojin") are listed, but they never merge two franchises into one.
  A few very old franchises are linked by crossovers into huge groups (Lupin III / Detective Conan, Doraemon).
  There the report only lists entries within 3 links of something you own.
- **MyAnimeList counts differently than Plex.** MAL lists each season, part and OVA as its own entry. Plex (TVDB/TMDB)
  puts them into seasons and Specials. The report translates between the two using Fribb's mapping. If the mapping is
  wrong for a show, corrections belong upstream in [Anime-Lists/anime-lists](https://github.com/Anime-Lists/anime-lists).

## For developers

```
python -m unittest discover -s tests -t .
```

The tests run a fake Plex server that refuses anything but GET requests.

Code layout: `anibox_check/plex.py` (read-only Plex client), `ids.py` (Plex GUID parsing for modern, legacy, HAMA,
MyAnimeList and custom-provider matches), `datasets.py` (download and cache), `analyze.py` (matching and franchises),
`report.py` (HTML/CSV), `cli.py`.
