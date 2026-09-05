"""Generate GitHub profile cards from public GitHub REST API data.

Only the Python standard library and the workflow's GITHUB_TOKEN are needed.
All API requests must succeed before any existing assets are replaced.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
API = "https://api.github.com"
PALETTES = {
    "dark": dict(bg="#0d1117", panel="#161b22", line="#30363d", text="#e6edf3",
                 muted="#9da7b3", accent="#58a6ff", green="#3fb950"),
    "light": dict(bg="#ffffff", panel="#f6f8fa", line="#d1d9e0", text="#1f2328",
                  muted="#59636e", accent="#0969da", green="#1a7f37"),
}
LANGUAGE_COLORS = {"Python": "#3572A5", "C++": "#f34b7d", "C": "#7185af",
                   "MATLAB": "#e16737", "Julia": "#a270ba", "TeX": "#3D9970",
                   "Jupyter Notebook": "#da5b0b", "Shell": "#89a848",
                   "JavaScript": "#c9a227", "HTML": "#e34c26"}


def request_json(path):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "LHappyCureall-profile-stats",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urlopen(Request(API + path, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"GitHub API returned HTTP {exc.code} for {path}") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError(f"GitHub API request failed for {path}") from None
        time.sleep(2 ** (attempt + 1))


def collect(login):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login):
        raise ValueError("Invalid GitHub username")
    user = request_json(f"/users/{login}")
    repos, page = [], 1
    while True:
        batch = request_json(f"/users/{login}/repos?type=owner&per_page=100&page={page}")
        repos.extend(r for r in batch if not r["private"] and
                     r["owner"]["login"].lower() == login.lower())
        if len(batch) < 100:
            break
        page += 1
    sources = [r for r in repos if not r["fork"]]

    def count(kind):
        query = urlencode({"q": f"author:{login} is:{kind} is:public", "per_page": 1})
        result = request_json("/search/issues?" + query)
        if result.get("incomplete_results"):
            raise RuntimeError("Incomplete GitHub search results; keeping previous cards")
        return result["total_count"]

    return {
        "login": user["login"],
        "joined": user["created_at"][:10],
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "public_repos": len(repos), "source_repos": len(sources),
        "stars_received": sum(r["stargazers_count"] for r in repos),
        "forks_received": sum(r["forks_count"] for r in repos),
        "followers": user["followers"], "following": user["following"],
        "pull_requests": count("pr"), "issues": count("issue"),
        "languages": dict(sorted(Counter(r["language"] for r in sources if r["language"]).items(),
                                 key=lambda item: (-item[1], item[0]))),
        "scope": "Public data only. Repository totals include owned forks; source repos exclude forks. "
                 "Stars and forks are received totals across owned public repos. Issues and PRs are "
                 "all-time authored public items (open and closed). Languages count the primary "
                 "language of each non-fork public repo, not code bytes or proficiency.",
    }


def render(data, theme):
    p = PALETTES[theme]
    languages = list(data["languages"].items())
    height = 530 if languages else 405
    if len(languages) > 4:
        languages = languages[:3] + [("Other", sum(n for _, n in languages[3:]))]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{height}" '
             f'viewBox="0 0 860 {height}" role="img" aria-labelledby="title description">',
             f'<title id="title">{escape(data["login"])} — GitHub statistics</title>',
             f'<desc id="description">{escape(data["scope"])} Updated {escape(data["updated"])}.</desc>',
             f'<rect x="0.5" y="0.5" width="859" height="{height - 1}" rx="16" fill="{p["bg"]}" stroke="{p["line"]}"/>',
             '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">']

    def text(x, y, value, size=16, color=None, weight=400, anchor="start"):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or p["text"]}" '
                     f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def line(x1, y1, x2, y2):
        parts.append(f'<path d="M{x1} {y1}H{x2}" stroke="{p["line"]}"/>' if y1 == y2 else
                     f'<path d="M{x1} {y1}V{y2}" stroke="{p["line"]}"/>')

    text(32, 36, "GITHUB / AT A GLANCE", 12, p["muted"], 600)
    text(32, 73, data["login"], 27, p["accent"], 650)
    subtitle = "Member since " + data["joined"] if data.get("joined") else "Public repositories & community activity"
    text(32, 100, subtitle, 14, p["muted"])
    parts.append(f'<circle cx="709" cy="68" r="4" fill="{p["green"]}"/>')
    text(722, 73, "Public profile", 13, p["muted"])
    line(32, 121, 828, 121)
    text(32, 155, "Repositories", 19, p["accent"], 600)
    text(461, 155, "Community & activity", 19, p["accent"], 600)
    line(430, 145, 430, 335)

    left = [("Public repositories", "public_repos"), ("Non-fork repositories", "source_repos"),
            ("Stars received", "stars_received"), ("Forks received", "forks_received")]
    right = [("Followers", "followers"), ("Following", "following"),
             ("Pull requests opened", "pull_requests"), ("Issues opened", "issues")]
    for x, end, rows in [(32, 397, left), (461, 828, right)]:
        for i, (label, key) in enumerate(rows):
            y = 195 + i * 41
            text(x, y, label, 16, p["muted"])
            text(end, y, f'{data[key]:,}', 21, p["text"], 600, "end")

    line(32, 351, 828, 351)
    if languages:
        text(32, 383, "Languages in public source repositories", 16, p["accent"], 600)
        total = sum(n for _, n in languages)
        x = 32
        for i, (language, count) in enumerate(languages):
            color = LANGUAGE_COLORS.get(language, ["#58a6ff", "#a371f7", "#2ea88f", "#8b949e"][i % 4])
            width = 796 * count / total
            parts.append(f'<rect x="{x:.2f}" y="399" width="{width:.2f}" height="9" fill="{color}"/>')
            x += width
            lx = 32 + (i % 2) * 429
            ly = 434 + (i // 2) * 24
            parts.append(f'<circle cx="{lx + 4}" cy="{ly - 5}" r="4" fill="{color}"/>')
            text(lx + 16, ly, f"{language} · {count} {'repo' if count == 1 else 'repos'}", 13, p["muted"])
    footer = "Public data only · Languages by repository count" if languages else "Public data only · Issues / PRs: all time"
    text(32, height - 36, footer, 12, p["muted"])
    text(828, height - 14, "Updated " + data["updated"], 12, p["muted"], anchor="end")
    parts.extend(["</g>", "</svg>"])
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=os.environ.get("PROFILE_USER", "LHappyCureall"))
    parser.add_argument("--snapshot", type=Path, help="Render an existing JSON snapshot without API access")
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else collect(args.user)
    assets = ROOT / "assets"
    outputs = {f"github-stats-{theme}.svg": render(data, theme) for theme in PALETTES}
    outputs["github-stats.json"] = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    assets.mkdir(exist_ok=True)
    for name, content in outputs.items():
        temporary = assets / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(assets / name)
    print("Updated profile assets: " + ", ".join(outputs))


if __name__ == "__main__":
    main()
