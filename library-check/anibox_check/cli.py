"""Command line entry point: ``python -m anibox_check`` (or double-click run-check.bat on Windows)."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import __version__
from .analyze import Analyzer
from .datasets import default_data_dir, ensure_datasets
from .plex import PlexError, PlexReader, Section
from .report import write_csv, write_html


def settings_path() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AniBox" / "settings.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "anibox" / "settings.json"


def load_settings() -> dict:
    p = settings_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> Path:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anibox-check",
        description="Read-only report of missing anime seasons, OVAs, specials and movies in a Plex library.",
    )
    p.add_argument("--server", help="Plex address, e.g. http://192.168.1.50:32400 (env: PLEX_URL)")
    p.add_argument("--token", help="Your X-Plex-Token (env: PLEX_TOKEN)")
    p.add_argument("--library", action="append", default=[], help="Library name to check (repeatable). Default: ask, or all.")
    p.add_argument("--out", default=".", help="Folder for the report files (default: current folder)")
    p.add_argument("--posters", action="store_true", help="Show small posters in the report (loaded from MAL's image server)")
    p.add_argument("--refresh-data", action="store_true", help="Download the anime lists again even if the copy is fresh")
    p.add_argument("--offline", action="store_true", help="Use only the already downloaded anime lists")
    p.add_argument("--data-dir", help="Where to keep the downloaded anime lists")
    p.add_argument("--no-open", action="store_true", help="Don't open the report in the browser")
    p.add_argument("--save", action="store_true", help="Remember server and token for next time without asking")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def choose_sections(sections: List[Section], wanted: List[str], interactive: bool) -> List[Section]:
    if wanted:
        lower = {w.lower() for w in wanted}
        chosen = [s for s in sections if s.title.lower() in lower]
        missing = lower - {s.title.lower() for s in chosen}
        if missing:
            names = ", ".join(s.title for s in sections)
            raise SystemExit(f"Library not found: {', '.join(sorted(missing))}. Available: {names}")
        return chosen
    if not interactive or len(sections) <= 1:
        return sections
    print("\nLibraries on this server:")
    for i, s in enumerate(sections, 1):
        print(f"  {i}. {s.title} ({'TV shows' if s.type == 'show' else 'Movies'})")
    answer = _ask("Which ones should be checked? Numbers separated by commas, or Enter for all")
    if not answer:
        return sections
    picked = []
    for part in answer.replace(" ", "").split(","):
        if part.isdigit() and 1 <= int(part) <= len(sections):
            picked.append(sections[int(part) - 1])
    return picked or sections


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    interactive = sys.stdin.isatty()
    settings = load_settings()

    server = args.server or os.environ.get("PLEX_URL") or settings.get("server")
    token = args.token or os.environ.get("PLEX_TOKEN") or settings.get("token")
    asked = False
    if not server and interactive:
        print("Plex address: the Shield's IP address on your network, port 32400.")
        server = _ask("Plex address (e.g. http://192.168.178.50:32400)")
        asked = True
    if not token and interactive:
        print("Plex token: see library-check/README.md, section 'Finding your Plex token'.")
        token = getpass.getpass("X-Plex-Token (input hidden): ").strip()
        asked = True
    if not server or not token:
        print("Need --server and --token (or PLEX_URL / PLEX_TOKEN).", file=sys.stderr)
        return 2

    plex = PlexReader(server, token)
    try:
        print(f"Connecting to {plex.base_url} ...")
        ident = plex.identity()
        sections = plex.sections()
    except PlexError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    server_name = ident.get("friendlyName") or plex.base_url

    if args.save or (asked and interactive and _ask("Remember address and token for next time? (y/n)", "y").lower().startswith("y")):
        where = save_settings({"server": server, "token": token})
        print(f"Saved to {where}")

    if not sections:
        print("No TV or movie libraries found.", file=sys.stderr)
        return 1
    chosen = choose_sections(sections, args.library, interactive)

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    try:
        ds = ensure_datasets(data_dir, refresh=args.refresh_data, offline=args.offline)
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    shows, movies, orderings = [], [], {}
    try:
        for s in chosen:
            print(f"Reading '{s.title}' ...")
            items = plex.items(s)
            if s.type == "show":
                orderings[s.title] = plex.section_ordering(s)
                shows.extend(items)
            else:
                movies.extend(items)
    except PlexError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Comparing with the anime lists ...")
    report = Analyzer(ds).analyze(shows, movies, orderings)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    html_path = out_dir / f"AniBox-Report-{stamp}.html"
    csv_path = out_dir / f"AniBox-Report-{stamp}.csv"
    write_html(report, html_path, server_name, posters=args.posters)
    write_csv(report, csv_path)

    missing = sum(1 for f in report.franchises for e in f.entries if e.status == "missing" and not e.short)
    print(f"\nDone. {report.identified} of {report.scanned} items identified, {missing} entries missing.")
    print(f"Report: {html_path.resolve()}")
    print(f"Spreadsheet: {csv_path.resolve()}")
    if not args.no_open and interactive:
        try:
            webbrowser.open(html_path.resolve().as_uri())
        except Exception:
            pass
    return 0
