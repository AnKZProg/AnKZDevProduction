#!/usr/bin/env python3
"""
languages.py - render a "most used languages" bar chart as an SVG. Stdlib only.

Replaces the lowlighter/metrics Languages plugin, which needs GitHub's GraphQL
API — and GraphQL does not accept fine-grained personal access tokens (classic
tokens only, see https://docs.github.com/graphql/guides/forming-calls-with-graphql).
This uses the plain REST API instead (`/repos/{owner}/{repo}/languages`), which
fine-grained tokens support fine, so it works with the same token already used
for the stat/repo cards.

    python scripts/languages.py --user AnKZProg -o assets/metrics.languages.svg

A token in $GITHUB_TOKEN raises the rate limit and is required to include
private repos; without one this still works for public repos, just capped at
60 requests/hour.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "languages.py"}
FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#39ff14",
              "text": "#c9d1d9", "muted": "#8b949e", "track": "#21262d"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "title": "#0f7a37",
               "text": "#1f2328", "muted": "#57606a", "track": "#eaeef2"},
}

LANG_COLOR = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "HTML": "#e34c26", "CSS": "#563d7c", "C++": "#f34b7d", "C": "#555555",
    "Java": "#b07219", "Go": "#00ADD8", "Rust": "#dea584", "Shell": "#89e051",
    "PLpgSQL": "#336790", "Vue": "#41b883", "Ruby": "#701516", "PHP": "#4F5D95",
    "Jupyter Notebook": "#DA5B0B", "SCSS": "#c6538c", "Svelte": "#ff3e00",
}
DEFAULT_LANG_COLOR = "#6e7681"


def rest(path: str, token: str | None):
    req = urllib.request.Request("https://api.github.com" + path, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def fetch_language_bytes(user: str, token: str | None) -> dict[str, int]:
    totals: dict[str, int] = {}
    page = 1
    while True:
        try:
            repos = rest(f"/users/{user}/repos?per_page=100&page={page}&type=owner", token)
        except urllib.error.HTTPError as e:
            print(f"  warn: could not list repos ({e.code})", file=sys.stderr)
            break
        for repo in repos:
            if repo["fork"]:
                continue
            try:
                langs = rest(f"/repos/{user}/{repo['name']}/languages", token)
            except urllib.error.HTTPError as e:
                print(f"  warn: skipping {repo['name']} ({e.code})", file=sys.stderr)
                continue
            for lang, n in langs.items():
                totals[lang] = totals.get(lang, 0) + n
        if len(repos) < 100:
            break
        page += 1
    return totals


def render(totals: dict[str, int], theme: str, top_n: int = 6) -> str:
    c = THEMES[theme]
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    total = sum(n for _, n in ranked) or 1

    w, row_h, pad = 480, 26, 20
    h = pad * 2 + 24 + row_h * len(ranked) if ranked else pad * 2 + 40
    bar_x, bar_w = 130, w - 130 - pad

    body = [f'<text x="{pad}" y="34" font-size="14" font-weight="700" '
            f'fill="{c["title"]}">Most used languages</text>']

    if not ranked:
        body.append(f'<text x="{pad}" y="64" font-size="12" fill="{c["muted"]}">'
                     f"no public code yet</text>")
    else:
        y = 58
        for lang, n in ranked:
            pct = 100 * n / total
            color = LANG_COLOR.get(lang, DEFAULT_LANG_COLOR)
            body.append(f'<text x="{pad}" y="{y}" font-size="12" fill="{c["text"]}">{esc(lang)}</text>')
            body.append(f'<rect x="{bar_x}" y="{y - 11}" width="{bar_w}" height="10" rx="5" fill="{c["track"]}"/>')
            fill_w = max(3, bar_w * pct / 100)
            body.append(f'<rect x="{bar_x}" y="{y - 11}" width="{fill_w:.1f}" height="10" rx="5" fill="{color}"/>')
            body.append(f'<text x="{w - pad}" y="{y}" font-size="11" text-anchor="end" '
                        f'fill="{c["muted"]}">{pct:.1f}%</text>')
            y += row_h

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="Most used languages" '
        f'font-family="{FONT}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>'
        f'{"".join(body)}</svg>'
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", required=True)
    p.add_argument("-o", "--out", type=Path, required=True, help="single SVG output path")
    args = p.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    totals = fetch_language_bytes(args.user, token)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(totals, "dark"), encoding="utf-8")
    print(f"wrote {args.out}  ({len(totals)} languages)")


if __name__ == "__main__":
    main()
