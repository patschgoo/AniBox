"""Write the report as a self-contained HTML page and a CSV file."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path
from typing import List

from . import __version__
from .analyze import MISSING, OWNED, PARTIAL, UNSURE, UPCOMING, EntryResult, Report

STATUS_LABEL = {
    OWNED: "Have",
    PARTIAL: "Incomplete",
    UNSURE: "Check",
    MISSING: "Missing",
    UPCOMING: "Not out yet",
}
TYPE_LABEL = {"TV": "TV", "MOVIE": "Movie", "OVA": "OVA", "ONA": "ONA", "SPECIAL": "Special", "UNKNOWN": "?"}

CSV_FIELDS = [
    "franchise", "status", "title", "type", "episodes", "have_episodes", "year",
    "where", "plex_item", "short_clip", "mal_url", "anidb_url",
]


def write_csv(report: Report, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel reads umlauts/Japanese
        w = csv.writer(fh)
        w.writerow(CSV_FIELDS)
        for fr in report.franchises:
            for e in fr.entries:
                w.writerow([
                    fr.name, STATUS_LABEL[e.status], e.title, TYPE_LABEL.get(e.type, e.type),
                    e.episodes if e.episodes is not None else "", e.have if e.have is not None else "",
                    e.year or "", e.detail, e.plex_title, "yes" if e.short else "", e.mal_url, e.anidb_url or "",
                ])


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _row(e: EntryResult, posters: bool) -> str:
    cls = f"st-{e.status}" + (" short" if e.short else "")
    img = (
        f'<img class="thumb" loading="lazy" alt="" src="{_esc(e.thumbnail)}">'
        if posters and e.thumbnail else ""
    )
    eps = "" if e.episodes is None else (f"{e.have}/{e.episodes}" if e.status == PARTIAL else str(e.episodes))
    links = f'<a href="{_esc(e.mal_url)}" target="_blank" rel="noopener noreferrer">MAL</a>'
    if e.anidb_url:
        links += f' · <a href="{_esc(e.anidb_url)}" target="_blank" rel="noopener noreferrer">AniDB</a>'
    short = ' <span class="tag">short clip</span>' if e.short else ""
    return (
        f'<tr class="{cls}" data-type="{_esc(e.type)}">'
        f'<td><span class="pill {e.status}">{STATUS_LABEL[e.status]}</span></td>'
        f'<td class="title">{img}<span>{_esc(e.title)}{short}</span></td>'
        f"<td>{_esc(TYPE_LABEL.get(e.type, e.type))}</td>"
        f'<td class="num">{_esc(eps)}</td>'
        f'<td class="num">{_esc(e.year or "")}</td>'
        f'<td class="where">{_esc(e.detail)}</td>'
        f"<td>{links}</td></tr>"
    )


def write_html(report: Report, path: Path, server_name: str, posters: bool = False) -> None:
    gaps = [f for f in report.franchises if f.count(MISSING, PARTIAL, UNSURE)]
    complete = [f for f in report.franchises if not f.count(MISSING, PARTIAL, UNSURE)]
    n_missing = sum(f.count(MISSING) for f in report.franchises)
    n_partial = sum(f.count(PARTIAL) for f in report.franchises)
    n_unsure = sum(f.count(UNSURE) for f in report.franchises)
    n_owned = sum(f.count(OWNED, include_short=True) for f in report.franchises)
    n_short = sum(1 for f in report.franchises for e in f.entries if e.short and e.status == MISSING)

    def section(frs: List, open_default: bool) -> str:
        parts = []
        for fr in frs:
            have = fr.count(OWNED, include_short=True)
            total = len(fr.entries)
            miss = fr.count(MISSING)
            badge = f"{have}/{total} have" + (f" · {miss} missing" if miss else "")
            rows = "".join(_row(e, posters) for e in fr.entries)
            parts.append(
                f'<details class="fr"{" open" if open_default else ""}><summary><span class="name">{_esc(fr.name)}</span>'
                f'<span class="badge">{_esc(badge)}</span></summary>'
                f'<div class="tablewrap"><table><thead><tr><th>Status</th><th>Title</th><th>Type</th><th class="num">Eps</th>'
                f'<th class="num">Year</th><th>Where in Plex</th><th>Links</th></tr></thead>'
                f"<tbody>{rows}</tbody></table></div></details>"
            )
        return "".join(parts)

    unidentified = "".join(
        f"<li>{_esc(i.title)}{f' ({i.year})' if i.year else ''} <span class='muted'>· {_esc(i.section)}"
        f"{' · ' + _esc(i.guid) if i.guid else ''}</span></li>"
        for i in report.unidentified
    )
    gaps_html = section(gaps, False) or '<p class="muted">Nothing missing. Nice.</p>'
    complete_html = section(complete, False) or '<p class="muted">None yet.</p>'
    unidentified_html = unidentified or '<li class="muted">None</li>'
    meta = report.titles_meta
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>AniBox Library Check</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --fg:#1d2330; --muted:#667085; --line:#e4e7ec;
  --have:#1a7f4b; --have-bg:#e3f5ea; --miss:#b42318; --miss-bg:#fdecea; --part:#9a5b00; --part-bg:#fff3d6;
  --chk:#3b5bdb; --chk-bg:#e8edff; --up:#667085; --up-bg:#eef0f3; --accent:#3b5bdb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#11141a; --card:#1a1f29; --fg:#e6e9ef; --muted:#98a2b3; --line:#2a3140;
  --have:#6fd39b; --have-bg:#173826; --miss:#ff8a80; --miss-bg:#3d1c1a; --part:#ffc35c; --part-bg:#3a2d10;
  --chk:#9db0ff; --chk-bg:#1f2847; --up:#98a2b3; --up-bg:#262c38; --accent:#9db0ff; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:24px; margin:0 0 4px; }} h2 {{ font-size:18px; margin:32px 0 12px; }}
.muted {{ color:var(--muted); }} a {{ color:var(--accent); }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:18px 0; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.stat b {{ display:block; font-size:22px; }}
.controls {{ display:flex; flex-wrap:wrap; gap:14px; align-items:center; background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:10px 14px; position:sticky; top:0; z-index:2; }}
.controls label {{ white-space:nowrap; }}
details.fr {{ background:var(--card); border:1px solid var(--line); border-radius:10px; margin:10px 0; overflow:hidden; }}
details.fr > summary {{ cursor:pointer; padding:12px 14px; display:flex; justify-content:space-between; gap:12px; list-style:none; }}
details.fr > summary::-webkit-details-marker {{ display:none; }}
.name {{ font-weight:600; }} .badge {{ color:var(--muted); white-space:nowrap; }}
.tablewrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; }}
th, td {{ text-align:left; padding:7px 10px; border-top:1px solid var(--line); vertical-align:middle; }}
th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }}
td.num, th.num {{ text-align:right; white-space:nowrap; }}
td.title {{ display:flex; align-items:center; gap:10px; min-width:220px; }}
td.where {{ min-width:200px; }}
.thumb {{ width:36px; height:52px; object-fit:cover; border-radius:4px; flex:none; }}
.pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }}
.pill.owned {{ color:var(--have); background:var(--have-bg); }} .pill.missing {{ color:var(--miss); background:var(--miss-bg); }}
.pill.partial {{ color:var(--part); background:var(--part-bg); }} .pill.unsure {{ color:var(--chk); background:var(--chk-bg); }}
.pill.upcoming {{ color:var(--up); background:var(--up-bg); }}
.tag {{ font-size:11px; color:var(--muted); border:1px solid var(--line); border-radius:4px; padding:0 4px; margin-left:6px; }}
body.only-gaps tr.st-owned {{ display:none; }} body.hide-short tr.short {{ display:none; }}
ul.unid {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 12px 12px 32px; }}
footer {{ margin-top:40px; font-size:13px; }}
</style></head>
<body class="only-gaps hide-short"><main>
<h1>AniBox Library Check</h1>
<div class="muted">{_esc(server_name)} · {generated} · read-only: nothing in Plex was changed</div>
<div class="stats">
  <div class="stat"><b>{report.scanned}</b>Plex items scanned</div>
  <div class="stat"><b>{report.identified}</b>identified as anime</div>
  <div class="stat"><b>{n_owned}</b>entries you have</div>
  <div class="stat"><b>{n_missing}</b>missing</div>
  <div class="stat"><b>{n_partial}</b>incomplete</div>
  <div class="stat"><b>{n_unsure}</b>to check</div>
</div>
<div class="controls">
  <label><input type="checkbox" id="gaps" checked> Hide entries I have</label>
  <label><input type="checkbox" id="short" checked> Hide short clips ({n_short} missing)</label>
  <label><input type="checkbox" id="openall"> Expand all</label>
</div>
<h2>Franchises with gaps ({len(gaps)})</h2>
{gaps_html}
<h2>Complete franchises ({len(complete)})</h2>
{complete_html}
<h2>Not found in the anime lists ({len(report.unidentified)})</h2>
<p class="muted">Not anime, or matched without TVDB/TMDB/IMDb IDs. These were skipped.</p>
<ul class="unid">{unidentified_html}</ul>
<footer class="muted">
Made by AniBox Library Check {__version__}. Data: <a href="https://github.com/Fribb/anime-lists">Fribb/anime-lists</a> (ID mapping, franchises) and
<a href="{_esc(meta.get('source') or 'https://github.com/cedya77/anime-offline-database')}">anime-offline-database</a>
({_esc(meta.get('license') or 'ODbL')}, updated {_esc(meta.get('lastUpdate') or '?')}).
"Check" means the entry sits in Specials, but the exact special number isn't known.
</footer>
</main>
<script>
const b=document.body;
document.getElementById('gaps').onchange=e=>b.classList.toggle('only-gaps',e.target.checked);
document.getElementById('short').onchange=e=>b.classList.toggle('hide-short',e.target.checked);
document.getElementById('openall').onchange=e=>document.querySelectorAll('details.fr').forEach(d=>d.open=e.target.checked);
</script>
</body></html>"""
    path.write_text(page, encoding="utf-8")
