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
- Which Shield model does the user have (Pro or 2019 tube)?
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
