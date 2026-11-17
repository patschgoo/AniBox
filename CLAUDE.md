# Project context: Private media server (Plex alternative)

Exported from a claude.ai chat (Nov 2026) so Claude Code has the background. Facts about Plex/Jellyfin reflect what was found via web search on 2026-11-15.

## Goal

Build a personal media server setup:
- Multiple HDDs with movies/shows
- Desktop app + Android app
- Streaming both locally and remotely
- More private than Plex, with a custom interface
- Possibly involving an NVIDIA Shield (user mentioned running it "over the Nvidia Shield")

User's timezone is Europe/Berlin. Many German ISPs use DS-Lite (no public IPv4), which matters for remote access.

## Known facts about the user's setup
- **NVIDIA Shield TV Pro (2019)**, so it can run Plex Media Server.
- **Plex Pass lifetime**, so remote streaming through Plex costs nothing extra. This removes Plex's biggest downside from Option A.
- Wants **MyAnimeList metadata**. The old MAL agent no longer works (see "MyAnimeList on Plex" below).
- **The HDDs are plugged into the Shield**, and the Shield is the Plex server. It wakes up by itself when the drives are accessed (e.g. when streaming through Plex).
- **No always-on PC.** There is a **Raspberry Pi 400**, but it hosts the user's game website (play + save data). Don't put extra services on it without asking.
- Consequence: anything that has to run 24/7 next to Plex (Shoko + ShokoRelay, a custom metadata provider) is **out for now**. ShokoRelay would also need Plex moved off the Shield. Tools must be **run-on-demand** from any computer, or be Plex-native.

## Built so far
- **`library-check/` (AniBox Library Check, v0.1.0)**: run-on-demand, **read-only** report of missing seasons/OVAs/specials/movies per franchise. Python ≥ 3.9, stdlib only, Windows launcher `run-check.bat`. Tests: `cd library-check && python -m unittest discover -s tests -t .` (fake Plex server that refuses non-GET; tested on Python 3.9–3.13).
  - Reads each Plex item's existing external IDs (modern `Guid` list, legacy thetvdb/themoviedb/imdb agents, HAMA `anidb-`/`tvdbN-`, Fribb's `net.fribbtastic.coding.plex.myanimelist://<malid>`, custom-provider GUIDs) plus every episode (`/library/sections/{id}/all?type=4`, paged with `X-Plex-Container-Start/Size`). Follows the episode ordering (`showOrdering` on the library prefs or the show: tmdb / tvdb / absolute).
  - Fribb/anime-lists maps each MAL entry to a TVDB/TMDB season and episode offset (season 0 = Specials). That gives Have / Incomplete (x of y) / Missing with the exact place it would go, e.g. "Specials (S00E12)" or "Season 4 (S04E17–E28)". It's "Check" when an entry is somewhere in Specials but the offset is unknown.
  - **Franchises come from anime-offline-database `relatedAnime`, not Fribb's `collections/`**. Fribb's groups chain unrelated films through shared CMs (a Suntory ad merges *Your Name*, *Mirai*, *Weathering with You*). Rules: bidirectional links only; short clips (< 5 min) and crossover/collab titles ("A x B" with A ≠ B, so "Hunter x Hunter" stays) are leaves, not bridges; groups > 100 entries only list entries within 3 hops of owned ones. A franchise is named after the earliest TV series that's owned or directly related to an owned entry.
  - Data cache: `%LOCALAPPDATA%\AniBox\data` or `~/.cache/anibox` (`anime-list-full.json` 7.5 MB + reduced `titles-v2.json` 7 MB, refreshed weekly). Settings with the Plex token: `%APPDATA%\AniBox\settings.json` or `~/.config/anibox/settings.json`.
  - Ideas for later: Plex PIN sign-in instead of copying the token; optional official MAL API for extra titles; a library-level "rename hint" export.

## Current direction (not final)

Exploring **building on Jellyfin** instead of using Plex. The recommended approach from the chat:
**keep the Jellyfin server unmodified and build custom client apps against its API.**

## Key findings

### Option A: Plex on the NVIDIA Shield (easy, but paid remote access)
- Plex Media Server runs only on the **Shield TV Pro**, not on the 2019 "tube" model.
- Setup is simple: install Plex on the Shield, enable the server, then add libraries from app.plex.tv on a desktop.
- Shield Pro has 2x USB 3.0 ports. For more drives, use a powered USB hub or a multi-bay enclosure, and pick drives with their own power supply. Keep them as portable storage, not adopted internal storage.
- Hardware transcoding: usually 2–3 simultaneous transcodes. Direct play is best; 4K that needs converting is where it struggles.
- Server updates come only through Google Play, so you can't pick a server version.
- **Remote streaming now requires a paid pass** (rolled out across platforms 2025–2026, including third-party clients). Local streaming stays free.
  - Plex Pass: $7/mo, $70/yr, $250 lifetime (US prices)
  - Remote Watch Pass: $2/mo, $20/yr
  - If the server owner has Plex Pass, everyone they share with can stream remotely at no extra cost.

### Option B: Jellyfin-based custom system (preferred direction)
- Jellyfin is GPL-2.0, free, and fully self-hosted, with no external connection or third-party auth. Remote streaming is free.
- **License:** you can use and modify it freely. If you distribute something built on it, it has to be open source under the same license. Personal and family use is fine.
- **Hardware:** the Jellyfin server most likely does NOT run on the Shield, so it needs a PC, mini PC or NAS with the drives attached. The Shield becomes a client/player.
- Current versions: Jellyfin moved from 10.11.x to **12.0** (new versioning), which shipped with server and web security fixes.
- Official desktop app renamed from Jellyfin Media Player to **Jellyfin Desktop** and is being rewritten.

#### Three levels of customization
1. **Restyle the web UI** with custom CSS or themes in the dashboard. Hours, almost no code.
2. **Build your own client apps** against the stock server. This is the best balance.
3. **Fork the server** (C#/.NET). Only if the API and plugins can't do something. Downside: you'd have to merge upstream updates, including security fixes, yourself.

#### SDKs / starting points
- Kotlin SDK (Android): `org.jellyfin.sdk:jellyfin-core` (see kotlin-sdk.jellyfin.org)
- TypeScript SDK: `@jellyfin/sdk` (MPL-2.0). 0.12–0.13 targets server 10.11.x; 1.0.x targets 12.x
- Community SDKs: Dart (`jellyfin_dart`), Python (`jellyfin-sdk`), Rust (`jellyfin-sdk`)
- Open-source clients to study or fork (check each license):
  - **Fladder** (Flutter, one codebase for Android, iOS, Windows, macOS, Linux and web)
  - **JellyPlay** (Kotlin, Jetpack Compose, Android + Android TV; ExoPlayer/libmpv/LibVLC)
  - Official Jellyfin for Android, Streamyfin, Jellyfin Desktop
- Playback engines: use ExoPlayer/Media3 (Android) or mpv (desktop) instead of writing a player.

#### Remote access
- Most private: VPN, either **Tailscale** (easy setup, works behind DS-Lite) or self-hosted **WireGuard**.
- Alternative: own domain + reverse proxy + TLS (exposes the server to the internet and needs inbound connectivity, which DS-Lite can block on IPv4).

### What's actually hard about recreating Plex (ranked)
1. **Playback compatibility (hardest):** each device supports a different mix of codecs, audio formats (DTS, TrueHD), subtitles and HDR. Per file and device, the server has to choose direct play, remux, or transcode, plus adaptive bitrate. Image-based subtitles (PGS) force burn-in, and HDR→SDR tone mapping is heavy.
2. **Library/metadata:** parsing messy filenames, matching to TMDB and similar, episodes, artwork, and syncing resume positions across devices.
3. **Client polish:** TV remote/D-pad navigation, touch and mouse, offline downloads.
4. **Remote connection:** easy for yourself and family (Tailscale). What's hard is Plex-level seamlessness for non-technical users: central account broker, automatic TLS certs (plex.direct), UPnP port opening, relay fallback (needs your own relay servers).

With Jellyfin, the server already covers 1 (server side, via FFmpeg) and 2, so the custom work is mostly client side.

## Linked sources: what each one gives AniBox (checked 2026-11-16)

The repo name suggests an anime-focused library. These are the sources the user pointed at and how they fit.

### jellyfin/jellyfin (server, GPL-2.0)
- Still the base. Keep it unmodified and run it on a PC, mini PC or NAS with the HDDs attached.
- Anime metadata comes from plugins, not server changes (see the MAL section below).

### plexinc (GitHub org)
- Plex Media Server itself is **closed source**. The org holds side projects (Docker images, old clients, forks of libraries), nothing that turns into a self-hosted server.
- Use it as a reference only. Nothing here replaces Jellyfin.

### Fribb/MyAnimeList.bundle (Plex metadata agent)
- A legacy Plex plug-in (`Contents/Code/*.py`, Plex plug-in framework, Python 2). It **cannot run on Jellyfin**.
- How it works: searches MAL through the **Jikan API** (unofficial MAL API), scores title matches 1–100, pulls synopsis, score, rating, posters, genres, studios, episodes and voice actors. TVDB/TMDB images are optional and need the user's own API keys.
- ID mapping between MAL, AniDB, TVDB and TMDB comes from Fribb's other project, **Fribb/anime-lists** (`anime-list-full.json`). That mapping file is directly useful for AniBox.
- **No LICENSE file** in the repo, so treat the code as reference only and don't copy it. Reimplementing the same approach against Jikan is fine.
- Jellyfin equivalents that already exist (verify each repo's status before installing):
  - **Shokofin + Shoko Server**: the most complete anime setup. Identifies files by AniDB hash, groups series and seasons properly, and can sync watch status to AniDB/MAL/AniList.
  - Official **AniList** plugin (`jellyfin/jellyfin-plugin-anilist`), plus AniDB, Kitsu and AniSearch plugins.
  - Community **MyAnimeList** plugin (`ryandash/jellyfin-plugin-myanimelist`, uses Jikan), and AnimeMultiSource.
  - Watch-progress sync to MAL/AniList: Ani-Sync (`vosmiic/jellyfin-ani-sync`).

### MyAnimeList on Plex: why the bundle stopped working, and the ways around it (checked 2026-11-16)
**Why it broke:**
- MyAnimeList.bundle is a *legacy agent*: Python 2 code running inside Plex's old plug-in framework.
- **On the Shield, Plex removed that framework completely** starting with PMS 1.41.0 (announced 2024-07-25, "all models"). All unofficial plug-ins (custom agents and scanners) stopped working, and so did Plex's own legacy TMDB/TVDB agents. So on a Shield-hosted server the bundle cannot run at all.
- On other platforms, PMS 1.43 hides legacy agents by default (they can still be turned back on), and Plex says it will **remove the legacy agent system from new PMS releases in 2026**. Running PMS on a PC just to keep the bundle is a dead end.
- The bundle itself is barely maintained: last code change 2025-05 (a mapping-file size fix). Earlier breakages came from Jikan API changes (moved to v4 in 2022) and HTTP 429 rate limits.
- And the API it depends on is gone: **the public Jikan API shut down on 2026-10-01** (see "Jikan shutdown" below).

**The replacement: Plex Custom Metadata Providers** (announced 2025-12-09, PMS 1.43.0+)
- A provider is just an **HTTP API** that returns metadata in Plex's format. Any language works, and Plex only needs a URL it can reach. You add it under Plex Web → Settings → Metadata Agents → Custom Metadata Providers, then build an "agent" from one or more providers in priority order (e.g. MAL provider + Plex Local Media).
- Movie and TV libraries only. Current limits: no authentication, no provider-specific preferences, no stream metadata (e.g. subtitles).
- Docs: developer.plex.tv/pms (Metadata Providers section). Official example: **`plexinc/tmdb-example-provider`** (TypeScript, TMDB, TV, alternate episode orders).
- **Not yet confirmed:** that the Shield build of PMS shows the Custom Metadata Providers screen. The user should check under Settings → Metadata Agents.
- The provider has to run on an always-on machine the Shield can reach (PC, NAS, Raspberry Pi, Docker host). It can't sensibly run on the Shield itself.

**Ways to get MAL data back, best first:**
1. **Run a MAL custom provider** on a PC or other always-on box. Existing community ones (all young, low adoption; check before use):
   - `PickledCakes/MyAnimeList-Plex-Metadata-Provider`: MIT, Python/Flask, Windows scripts with autostart, explicitly a replacement for Fribb's bundle. Calls **`api.tenrai.org`** (a third-party MAL mirror), **not Jikan**, and calls itself a "PoC". Last push 2026-08.
   - `Thrathius/plex-anime-metadata-provider`: AniDB HTTP API + MAL via Jikan, self-hostable. **Its MAL part is likely broken** (still calls Jikan, last push 2026-08).
   - `yotsimitsu/hama-modern`, `angu1ss/plex-anime-provider`, `KurtzPT/kizuna`: HAMA successors (AniDB/TVDB/MAL), very new.
   - **`natyusha/ShokoRelay`**: the most mature anime provider (GPL-3.0, actively developed). Needs **Shoko Server**, which is AniDB-based. Uses a symlink virtual file system (VFS) so any folder layout works. Includes watch-state sync and automation.
2. **Build our own MAL provider (fits AniBox)**: a small HTTP service that uses the **official MAL API v2** (free client ID, `X-MAL-CLIENT-ID` header; Jikan is gone) and Fribb/anime-lists for ID mapping, modeled on `plexinc/tmdb-example-provider`. Gives full control and privacy (no third-party mirror), and the same MAL client code can later feed a Jellyfin setup.
3. **Kometa** on top of Plex's built-in TV agent: it adds MAL/AniDB ratings and genres through the Plex API (works with a Shield-hosted server). It doesn't replace titles, episodes or posters with MAL's.
- Known catch for any MAL-based provider: MAL lists each season or sequel as a separate entry, while Plex groups seasons under one show.

### Jikan shutdown (2026-10-01): what it breaks (checked in each project's code, 2026-11-17)
- Timeline: wind-down announced 2026-06-14, brownout from 2026-09-01, public API off on **2026-10-01**. `api.jikan.moe` now hangs or times out (confirmed from this container). The maintainer points to self-hosting jikan-rest. Projects moved to **Tenrai** (`api.tenrai.org/v1`, Jikan-v4 compatible, third party) or the **official MAL API v2**.
- **Not affected:** Shoko Server, ShokoRelay, Shokofin. None of them call Jikan (grep of current source). Shoko's data comes from **AniDB** (plus TMDB). AniDB entries carry MAL links, so MAL IDs are still visible.
- **Already switched:**
  - `ryandash/jellyfin-plugin-myanimelist`: default base URL is now `api.tenrai.org` (updated 2026-11-11).
  - Kometa: MAL lookups go to the mirror `malapi.animemap.dev/v4/` plus the official MAL API (OAuth via its own client).
  - `PickledCakes/MyAnimeList-Plex-Metadata-Provider`: Tenrai.
- **Broken:** Fribb's MyAnimeList.bundle; Thrathius' provider (MAL part). Anything still pointed at `api.jikan.moe`.
- Risk to note: Tenrai and animemap are single third-party mirrors and could disappear the way Jikan did. The official MAL API needs a client ID, but it's the most durable option.
- **Fribb/anime-lists is still updated** (automated update 2026-11-12). It now builds from `cedya77/anime-offline-database` (a fork; manami's repo last commit 2026-07) plus `Anime-Lists/anime-lists`. `anime-list-full.json` has 39,745 entries (TV 9,721 · OVA 4,677 · SPECIAL 11,031 · MOVIE 6,495 · ONA 6,377). Fields: `mal_id, anidb_id, anilist_id, tvdb_id, themoviedb_id, imdb_id, kitsu_id, season, type, …`. `collections/` holds bidirectional "related anime" groups per source.

### Shoko risks unrelated to Jikan
- **AniDB is the single source of truth.** You need an AniDB account. AniDB bans clients that send too many requests (temporary; Shoko throttles requests itself). If AniDB is down, new files don't get matched.
- TvDB support was removed from Shoko (v5); TMDB covers extra images and descriptions.
- ShokoRelay needs a Shoko **daily build** and PMS 1.43+ custom providers, which Plex still calls work in progress.
- The first import **hashes every file completely**, which takes a long time on multi-TB drives.
- **ShokoRelay's VFS is symlinks inside Shoko's managed folders, and Plex must read them through the same paths.** In practice PMS, Shoko and the drives need to be on the same machine (or a NAS with matching paths). Symlinks created by a PC won't resolve for a Shield-hosted PMS reading the Shield's own USB drives. **So ShokoRelay = move PMS to the PC.**
- Safe by default: `RenameOnImport` and `MoveOnImport` are both **false** in Shoko's settings, so it doesn't touch your files unless you turn a renamer on.
- Shoko shows missing-episode counts per type (episodes, specials, credits, trailers, parodies, other), which is how it finds missing OVAs and specials.

### Complete library (OVAs/specials) without changing existing matches: options, easiest first
Ground rule: **never switch the agent on the existing library.** That re-matches everything. Instead, create a **second library** over the same files (or the ShokoRelay VFS) with the new agent, compare, and delete whichever library you don't want later. Plex allows several libraries over the same folders. Watch states don't carry over automatically to a new library.
1. **Read-only completeness report (AniBox tool, nothing in Plex changes):** read the existing library through the Plex API, take each show's TVDB/TMDB IDs from the matches Plex already has, map them to MAL/AniDB IDs with Fribb/anime-lists, then list related OVAs/specials/movies (from `collections/` + `type`) that aren't in the library. Optional: the official MAL API for titles and dates. Works with PMS staying on the Shield, and touches nothing.
2. **Plex built-in agent + Season 00:** name specials `S00Exx` in a `Specials` folder and Plex matches them to TVDB/TMDB specials. No new services, but TVDB/TMDB special lists for anime are often incomplete, and Plex has no "missing episodes" view.
3. **Shoko Server + ShokoRelay (most complete, AniDB numbering):** every OVA/special/credit/trailer is known, missing ones are listed, and files stay untouched (VFS = symlinks). New library on the VFS. Needs PMS on the PC (see VFS note above).
4. **MAL provider (Tenrai or our own on the official MAL API) in a second library:** MAL-style entries (each OVA its own show). Files need to be organized per MAL entry. No missing detection.

### RasenderRentner/frostbox-releases (friend's app; user has full permission to use it)
- The repo holds **only a README and release binaries** (tags v0.6.0 to v1.2.0). The source code is not in it.
- What Frostbox is: a private Windows 10/11 player for series and films **streamed from archive.org**, not a local-library server. UI and docs are in German.
- What v1.2.0 is built from (read from the release zip, not run):
  - .NET 8. `Frostbox.dll` = WPF UI (Windows only). **`Frostbox.Core.dll` targets plain `net8.0`, so it is cross-platform.**
  - Playback: **libmpv** (`libmpv-2.dll`).
  - Storage: SQLite (`Microsoft.Data.Sqlite`), data in `%LOCALAPPDATA%\Frostbox`.
  - Embedded ASP.NET Core / Blazor server + QRCoder + Zeroconf: a phone remote (`RemoteServer`) that you pair by QR code, with mDNS discovery.
  - **Chromecast casting** via Sharpcaster (`CastPlayer`, `ChromecastClient`). The NVIDIA Shield is a Cast receiver.
  - `StreamServer`, `CollectionScanner`, `PlaylistService`, `TerminService` (schedule), `BereichService` (sections), Discord Rich Presence.
  - `Frostbox.Updater.exe`: signed updates ("Echtheitssiegel"), drag-and-drop update zips, automatic rollback if a new version fails to start.
- What it could give AniBox: the mpv playback layer, phone remote with QR pairing, casting to the Shield, the signed updater, and the UI design. Reusing code properly needs **the friend's source repo**. The release ships `.pdb` files, but decompiling is a poor substitute for the real source.

## Open questions / decisions to make
- Can the friend share the Frostbox **source** repo (private repo access or a copy)? This decides whether the desktop client starts from Frostbox (.NET) or from scratch.
- Anime metadata route: Shoko Server + Shokofin (most accurate, one more service to run) or plain Jellyfin + AniList/MAL plugins (simpler)?
- Answered: Shield TV Pro 2019 and Plex Pass lifetime. **Open again: stay on Plex (Shield as server + a MAL custom provider) or still move to Jellyfin?**
- Does the Shield's PMS show "Custom Metadata Providers" under Settings → Metadata Agents? (Only matters if an always-on machine shows up later.)
- Answered: drives are on the Shield; no always-on PC (Pi 400 is busy with the game website).
- Use an existing MAL provider, or build AniBox's own (Jikan + anime-lists)?
- Server hardware: existing PC, a new mini PC, or a NAS? (A mini PC with Intel Quick Sync is a common choice for transcoding.)
- Client tech stack: native Kotlin (Android) + separate desktop app, or Flutter for both, or web tech (Electron/Tauri + TypeScript SDK)? If Frostbox source is available, a .NET desktop client (reusing Frostbox.Core, which is plain net8.0) becomes a fourth option.
- Who will use it: just the user and family, or friends too? This affects how much remote-access polish is needed.
- Which customizations matter most (UI look, features, privacy)?

## Suggested first steps (not yet agreed)
1. Run a Jellyfin server locally (e.g. Docker) with a few test files.
2. Pick the client stack.
3. Prototype the minimal client loop: server login → browse libraries → play a file with resume position.
4. Add remote access via Tailscale.

## Conversation log (condensed)

**Q1:** How hard is it to create my own Plex server that runs on the Nvidia Shield with multiple HDDs, with desktop and Android apps, streaming locally and remotely?
**A:** Easy with a Shield TV Pro (an afternoon, no coding). Plex already has desktop and Android apps. Catches: remote streaming needs a paid pass, router/DS-Lite issues, limited transcoding, server updates only through Google Play. Writing a full Plex-like system yourself would be months of work. Jellyfin is the free open-source option, but its server needs a PC or NAS.

**Q2:** If Jellyfin is open source, why not create something based on it as our own, more private server with a more custom interface?
**A:** Good plan. Keep the server unmodified and build your own apps against the API (SDKs exist; Fladder is a good reference). Fork the server only if necessary. GPL-2.0 is fine for personal use. The server moves to a PC, mini PC or NAS, and the Shield becomes a player. Use Tailscale or WireGuard for remote access.

**Q3:** Is the hardest part about Plex recreating the server remote connection?
**A:** No. Playback compatibility is the hardest, then library/metadata. Remote access is easy for yourself (Tailscale). It's only hard to make it seamless for others the way Plex does. Jellyfin already handles transcoding and metadata, so the remaining work is mainly the client apps.

## Sources
- Plex on Shield limitations: https://support.plex.tv/articles/221099648-limitations-when-running-plex-media-server-on-nvidia-shield/
- Plex on Shield setup: https://support.plex.tv/articles/221099988-setting-up-and-managing-plex-media-server-on-nvidia-shield/
- Plex remote streaming changes: https://plex.tv/blog/important-2025-plex-updates/
- Plex Smart TV remote streaming: https://forums.plex.tv/t/changes-coming-to-remote-streaming-on-smart-tvs/937015
- Plex pricing (Android Authority): https://www.androidauthority.com/plex-remote-viewing-restriction-roku-tv-3619768/
- Jellyfin server repo: https://github.com/jellyfin/jellyfin
- Jellyfin TypeScript SDK: https://typescript-sdk.jellyfin.org
- Jellyfin Kotlin SDK: https://kotlin-sdk.jellyfin.org/guide/getting-started.html
- Jellyfin client overview: https://jellywatch.app/blog/awesome-jellyfin-clients-complete-ecosystem-guide-2026
- State of the Fin (Jellyfin Desktop rewrite): https://jellyfin.org/posts/state-of-the-fin-2026-05-24/
- Plex GitHub org: https://github.com/plexinc
- MyAnimeList Plex agent: https://github.com/Fribb/MyAnimeList.bundle
- Anime ID mapping list: https://github.com/Fribb/anime-lists
- Frostbox releases (friend's app): https://github.com/RasenderRentner/frostbox-releases
- Shokofin guide: https://jellywatch.app/blog/shokofin-jellyfin-anime-plugin-anidb-complete-guide-2026
- Jellyfin anime setup overview: https://jellywatch.app/blog/jellyfin-anime-library-complete-setup-anilist-shoko-2026
- Jellyfin plugins docs: https://jellyfin.org/docs/general/server/plugins
- Plex on Shield drops plug-ins (2024-07-25): https://forums.plex.tv/t/important-information-for-users-running-plex-media-server-on-nvidia-shield-devices/883484
- Plex Custom Metadata Providers announcement (2025-12-09): https://forums.plex.tv/t/announcement-custom-metadata-providers/934384
- Legacy agents hidden/removed thread: https://forums.plex.tv/t/legacy-agents-removed-already-in-pms-1-41-7-9717-2025-04-23/914518
- MAL provider (community): https://github.com/PickledCakes/MyAnimeList-Plex-Metadata-Provider
- ShokoRelay: https://github.com/natyusha/ShokoRelay
- Kometa operations: https://kometa.wiki/en/latest/config/operations/
- Jikan public API discontinuation (2026-10-01): https://github.com/jikan-me/jikan-rest/issues/613
- Example migrations away from Jikan: https://github.com/adrmrt/holobot/issues/235 , https://github.com/jamesgallagher/Stremio_AI_Recommender/pull/54
- Shoko Server: https://github.com/ShokoAnime/ShokoServer (releases: https://github.com/ShokoAnime/ShokoServer/releases)
