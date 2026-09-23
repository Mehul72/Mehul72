#!/usr/bin/env python3
"""Renders assets/activity-{dark,light}.svg for the profile README.

Runs every day in GitHub Actions (.github/workflows/activity.yml) with only the
standard library. With GITHUB_TOKEN set it reads the GraphQL API; without one it
reads the public contributions page and REST API instead, which is enough for a
local run.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "Mehul72")
HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
FONTS = HERE / "fonts"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        name
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Used only by the tokenless fallback, which cannot ask GitHub for colours.
LINGUIST = {
    "Swift": "#F05138", "TypeScript": "#3178C6", "Go": "#00ADD8", "Python": "#3572A5",
    "JavaScript": "#F1E05A", "Shell": "#89E051", "CSS": "#663399", "HTML": "#E34C26",
    "Java": "#B07219", "Makefile": "#427819", "Dockerfile": "#384D54", "Rust": "#DEA584",
    "Kotlin": "#A97BFF", "C": "#555555", "C++": "#F34B7D", "Ruby": "#701516",
}


def fetch(url: str, token: str | None = None, body: dict | None = None) -> bytes:
    headers = {"User-Agent": f"{USER}-profile-activity", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def from_graphql(token: str) -> tuple[list[tuple[dt.date, int]], int, dict[str, tuple[int, str]]]:
    payload = json.loads(fetch("https://api.github.com/graphql", token, {"query": QUERY, "variables": {"login": USER}}))
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    user = payload["data"]["user"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        (dt.date.fromisoformat(day["date"]), day["contributionCount"])
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    languages: dict[str, tuple[int, str]] = {}
    for repo in user["repositories"]["nodes"]:
        if repo["name"].lower() == USER.lower():
            continue
        for edge in repo["languages"]["edges"]:
            name, color = edge["node"]["name"], edge["node"]["color"] or "#8B949E"
            languages[name] = (languages.get(name, (0, color))[0] + edge["size"], color)
    return days, calendar["totalContributions"], languages


def from_public_pages() -> tuple[list[tuple[dt.date, int]], int, dict[str, tuple[int, str]]]:
    page = fetch(f"https://github.com/users/{USER}/contributions").decode()
    dates = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', page))
    by_id = {cell_id: date for date, cell_id in dates.items()}
    counts: dict[str, int] = {}
    for cell_id, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        match = re.match(r"\s*(\d+) contribution", html.unescape(label))
        counts[cell_id] = int(match.group(1)) if match else 0
    days = sorted((dt.date.fromisoformat(by_id[i]), counts.get(i, 0)) for i in by_id)
    total_match = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    total = int(total_match.group(1).replace(",", "")) if total_match else sum(c for _, c in days)

    languages: dict[str, tuple[int, str]] = {}
    repos = json.loads(fetch(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner"))
    for repo in repos:
        if repo["fork"] or repo["name"].lower() == USER.lower():
            continue
        for name, size in json.loads(fetch(repo["languages_url"])).items():
            languages[name] = (languages.get(name, (0, ""))[0] + size, LINGUIST.get(name, "#8B949E"))
    return days, total, languages


def streaks(days: list[tuple[dt.date, int]]) -> tuple[int, int]:
    longest = run = 0
    for _, count in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    tail = days[:-1] if days and days[-1][1] == 0 else days  # today may simply not have started yet
    for _, count in reversed(tail):
        if not count:
            break
        current += 1
    return current, longest


def num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def mix(stops: list[str], t: float) -> str:
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    a, b = (tuple(int(c[k:k + 2], 16) for k in (1, 3, 5)) for c in (stops[i], stops[i + 1]))
    return "#" + "".join(f"{round(x + (y - x) * f):02X}" for x, y in zip(a, b))


def font_face(family: str, file: str) -> str:
    data = base64.b64encode((FONTS / file).read_bytes()).decode()
    return f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{data}) format('woff2')}}"


SANS_FALLBACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def text(x, y, s, family, size, fill, anchor="start", spacing=0.0, opacity=1.0) -> str:
    extra = f' text-anchor="{anchor}"' if anchor != "start" else ""
    extra += f' letter-spacing="{num(spacing)}"' if spacing else ""
    extra += f' fill-opacity="{num(opacity)}"' if opacity != 1 else ""
    return (
        f'<text x="{num(x)}" y="{num(y)}" font-family="{family},{SANS_FALLBACK}" font-size="{num(size)}" '
        f'fill="{fill}"{extra}>{esc(s)}</text>'
    )


def render(theme: str, days, total: int, languages, today: dt.date) -> str:
    dark = theme == "dark"
    W, H = 1280, 432
    ink = "#F5F5F7" if dark else "#1D1D1F"
    muted = "#9A9AA3" if dark else "#6E6E73"
    faint = "#fff" if dark else "#000"
    aurora = ["#A78BFA", "#60A5FA", "#22D3EE"] if dark else ["#7C3AED", "#2563EB", "#0891B2"]
    px, py, pw, ph = 16, 10, W - 32, H - 26
    out = []

    # Panel
    defs = (
        f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{"#17171E" if dark else "#FFFFFF"}"/>'
        f'<stop offset="1" stop-color="{"#0F0F14" if dark else "#FAFAFC"}"/></linearGradient>'
        f'<radialGradient id="glow" cx="{px + 120}" cy="{py}" r="520" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#8B5CF6" stop-opacity="{".26" if dark else ".12"}"/>'
        f'<stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="big" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{aurora[0]}"/>'
        f'<stop offset=".55" stop-color="{aurora[1]}"/><stop offset="1" stop-color="{aurora[2]}"/></linearGradient>'
        f'<clipPath id="panel"><rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="32"/></clipPath>'
        f'<clipPath id="bar"><rect x="436" y="300" width="796" height="12" rx="6"/></clipPath>'
    )
    shadow = "" if dark else ' filter="url(#lift)"'
    if not dark:
        defs += (
            '<filter id="lift" x="-10%" y="-10%" width="120%" height="130%"><feGaussianBlur in="SourceAlpha" stdDeviation="6"/>'
            '<feOffset dy="4"/><feComponentTransfer><feFuncA type="linear" slope=".07"/></feComponentTransfer>'
            '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        )
    out.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="32" fill="url(#bg)"{shadow}/>')
    out.append(f'<g clip-path="url(#panel)"><rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="url(#glow)"/></g>')
    out.append(
        f'<rect x="{px + .5}" y="{py + .5}" width="{pw - 1}" height="{ph - 1}" rx="31.5" stroke="{faint}" '
        f'stroke-opacity="{".09" if dark else ".08"}"/>'
    )

    # Totals and streaks
    current, longest = streaks(days)
    best_date, best = max(days, key=lambda d: (d[1], d[0]))
    active = sum(1 for _, c in days if c)
    out.append(text(56, 74, "CONTRIBUTIONS", "semi", 14, muted, spacing=2.6))
    out.append(text(52, 166, f"{total:,}", "display", 92, "url(#big)", spacing=-3))
    out.append(text(56, 202, "in the last year", "medium", 19, muted))
    out.append(f'<rect x="56" y="232" width="324" height="1" fill="{faint}" fill-opacity=".08"/>')
    rows = [
        ("Current streak", plural(current, "day")),
        ("Longest streak", plural(longest, "day")),
        ("Best day", f"{best} on {best_date.day} {best_date:%b}"),
        ("Active days", plural(active, "day")),
    ]
    for i, (label, value) in enumerate(rows):
        y = 272 + i * 38
        out.append(text(56, y, label, "medium", 17, muted))
        out.append(text(380, y, value, "semi", 17, ink, anchor="end"))

    # Calendar
    gx, gy, pitch, cell = 436, 96, 15.02, 11.6
    first = days[0][0]
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    nonzero = sorted(c for _, c in days if c)
    cuts = [nonzero[int(len(nonzero) * q)] for q in (0.25, 0.5, 0.75)] if nonzero else [1, 2, 3]
    columns: dict[int, list[str]] = {}
    last_label_col = -9
    for date, count in days:
        col = (date - start).days // 7
        row = (date.weekday() + 1) % 7
        x, y = gx + col * pitch, gy + row * pitch
        if count:
            level = 1 + sum(count > c for c in cuts)
            fill = mix(aurora, col / 52)
            opacity = (0.3, 0.52, 0.76, 1.0)[level - 1]
        else:
            fill, opacity = faint, 0.07 if dark else 0.06
        columns.setdefault(col, []).append(
            f'<rect x="{num(x)}" y="{num(y)}" width="{cell}" height="{cell}" rx="3.2" fill="{fill}" fill-opacity="{num(opacity)}"/>'
        )
        if date.day <= 7 and row == 0 and col - last_label_col > 3 and col < 52:
            out.append(text(x, gy - 14, f"{date:%b}", "medium", 14, muted))
            last_label_col = col
    for col, cells in sorted(columns.items()):
        out.append(f'<g class="c" style="animation-delay:{num(0.2 + col * 0.018)}s">{"".join(cells)}</g>')
    last_date = days[-1][0]
    lc, lr = (last_date - start).days // 7, (last_date.weekday() + 1) % 7
    tx, ty = gx + lc * pitch + cell / 2, gy + lr * pitch + cell / 2
    out.append(
        f'<circle class="ping" cx="{num(tx)}" cy="{num(ty)}" r="{cell / 2 + 1}" stroke="{aurora[2]}" stroke-width="2"/>'
    )

    legend_y = gy + 7 * pitch + 22
    lx = gx + 53 * pitch - 5 * 16 - 40
    out.append(text(lx - 10, legend_y + 10, "Less", "medium", 13, muted, anchor="end"))
    for i, opacity in enumerate((0.07 if dark else 0.06, 0.3, 0.52, 0.76, 1.0)):
        fill = faint if i == 0 else mix(aurora, 0.85)
        out.append(
            f'<rect x="{num(lx + i * 16)}" y="{num(legend_y)}" width="11.6" height="11.6" rx="3.2" fill="{fill}" '
            f'fill-opacity="{num(opacity)}"/>'
        )
    out.append(text(lx + 5 * 16 + 4, legend_y + 10, "More", "medium", 13, muted))
    out.append(text(gx, legend_y + 10, f"Updated {today.day} {today:%b %Y}", "medium", 13, muted))

    # Languages
    ranked = sorted(languages.items(), key=lambda kv: -kv[1][0])
    grand = sum(size for size, _ in languages.values()) or 1
    top = ranked[:6]
    other = grand - sum(size for _, (size, _) in top)
    segments = [(name, size, color) for name, (size, color) in top] + ([("Other", other, "#8B949E")] if other > 0 else [])
    out.append(text(gx, 282, "TOP LANGUAGES", "semi", 14, muted, spacing=2.6))
    bx = gx
    bar = []
    for name, size, color in segments:
        width = 796 * size / grand
        bar.append(f'<rect x="{num(bx)}" y="300" width="{num(max(width - 2, 1))}" height="12" fill="{color}"/>')
        bx += width
    out.append(f'<g clip-path="url(#bar)">{"".join(bar)}</g>')
    for i, (name, size, color) in enumerate(segments[:6]):
        x = gx + i * (796 / 6)
        out.append(f'<circle cx="{num(x + 6)}" cy="344" r="6" fill="{color}"/>')
        out.append(text(x + 20, 350, name, "semi", 16, ink))
        out.append(text(x + 20, 372, f"{100 * size / grand:.1f}%", "medium", 15, muted))

    css = (
        font_face("display", "inter-display-digits.woff2")
        + font_face("semi", "inter-semibold.woff2")
        + font_face("medium", "inter-medium.woff2")
        + "text{font-kerning:normal}"
        ".c{opacity:0;animation:in .6s ease-out forwards}"
        "@keyframes in{from{opacity:0}to{opacity:1}}"
        ".ping{transform-box:fill-box;transform-origin:50% 50%;animation:ping 2.2s ease-out infinite}"
        "@keyframes ping{0%{transform:scale(1);opacity:.9}80%,100%{transform:scale(2.2);opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.c{animation:none;opacity:1}.ping{animation:none}}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">'
        f"<style>{css}</style><defs>{defs}</defs>{''.join(out)}</svg>\n"
    )


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    days, total, languages = from_graphql(token) if token else from_public_pages()
    if len(days) < 300 or not languages:
        sys.exit(f"refusing to render: got {len(days)} days and {len(languages)} languages")
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=10))).date()
    ASSETS.mkdir(exist_ok=True)
    for theme in ("dark", "light"):
        path = ASSETS / f"activity-{theme}.svg"
        path.write_text(render(theme, days, total, languages, today))
        print(f"wrote {path.relative_to(HERE.parent)} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
