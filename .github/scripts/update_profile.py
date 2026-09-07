"""Generate profile cards, publishing only aggregate private commit counts.

Public metrics use GITHUB_TOKEN; commit totals require PROFILE_STATS_TOKEN.
All API requests must succeed before any existing assets are replaced.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import hashlib
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
README_START = b"<!-- PROFILE-STATS:START -->"
README_END = b"<!-- PROFILE-STATS:END -->"
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


class GitHubAPIError(RuntimeError):
    """An API failure that never includes repository paths or response contents."""

    def __init__(self, status, empty_repository=False):
        super().__init__(f"GitHub API request failed (HTTP {status}); previous cards retained.")
        self.status = status
        self.empty_repository = empty_repository


def request_json(path, token=None):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "LHappyCureall-profile-stats",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urlopen(Request(API + path, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            empty_repository = False
            if exc.code == 409:
                try:
                    empty_repository = json.load(exc).get("message", "").lower() == "git repository is empty."
                except (ValueError, AttributeError):
                    pass
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise GitHubAPIError(exc.code, empty_repository) from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("GitHub API connection failed; previous cards retained.") from None
        time.sleep(2 ** (attempt + 1))


def iso_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def collect_commit_stats(login, now, token):
    """Count unique authored SHAs in accessible owned repos' default branches.

    Repository names, commit messages, hashes, and raw API responses stay in memory.
    The returned object contains only the three requested counts and their scope.
    """
    if not token:
        return {"status": "not_configured", "total_365d": None,
                "private_365d": None, "total_30d": None}

    identity = request_json("/user", token=token)
    if identity["login"].lower() != login.lower():
        raise RuntimeError("The statistics token must belong to the profile owner.")
    repos, page = [], 1
    while True:
        batch = request_json(f"/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}", token=token)
        repos.extend(r for r in batch if r["owner"]["login"].lower() == login.lower())
        if len(batch) < 100:
            break
        page += 1

    # Detect limited repository selection when GitHub exposes account totals.
    for field, private in (("public_repos", False), ("owned_private_repos", True)):
        expected = identity.get(field)
        if expected is not None and sum(r["private"] == private for r in repos) != expected:
            raise RuntimeError("Statistics token does not expose every owned repository; totals were not published.")

    start_year, start_month = now - timedelta(days=365), now - timedelta(days=30)
    all_commits, private_commits, month_commits = set(), set(), set()
    for repo in repos:
        page = 1
        while True:
            query = urlencode({"sha": repo["default_branch"], "author": login,
                               "since": iso_utc(start_year), "until": iso_utc(now),
                               "per_page": 100, "page": page})
            try:
                batch = request_json(f'/repos/{repo["full_name"]}/commits?{query}', token=token)
            except GitHubAPIError as exc:
                if exc.empty_repository and page == 1:
                    break
                raise
            for item in batch:
                # GitHub-linked author identity excludes other authors and bots.
                if (item.get("author") or {}).get("login", "").lower() != login.lower():
                    continue
                stamp = datetime.fromisoformat(item["commit"]["committer"]["date"].replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise RuntimeError("Commit timestamp is missing a time zone; totals were not published.")
                if not start_year <= stamp <= now:
                    continue
                sha = item["sha"]
                all_commits.add(sha)
                if repo["private"]:
                    private_commits.add(sha)
                if stamp >= start_month:
                    month_commits.add(sha)
            if len(batch) < 100:
                break
            page += 1
    return {"status": "complete", "total_365d": len(all_commits),
            "private_365d": len(private_commits), "total_30d": len(month_commits),
            "window_end": iso_utc(now), "since_365d": iso_utc(start_year),
            "since_30d": iso_utc(start_month),
            "repository_scope": "owned_repositories_accessible_to_token",
            "branch_scope": "default_branch", "date_basis": "committer_date",
            "deduplication": "commit_sha_across_repositories"}


def collect(login):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login):
        raise ValueError("Invalid GitHub username")
    now = datetime.now(timezone.utc)
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
        "updated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "public_repos": len(repos), "source_repos": len(sources),
        "stars_received": sum(r["stargazers_count"] for r in repos),
        "forks_received": sum(r["forks_count"] for r in repos),
        "followers": user["followers"], "following": user["following"],
        "pull_requests": count("pr"), "issues": count("issue"),
        "languages": dict(sorted(Counter(r["language"] for r in sources if r["language"]).items(),
                                 key=lambda item: (-item[1], item[0]))),
        "commit_stats": collect_commit_stats(login, now, os.environ.get("PROFILE_STATS_TOKEN")),
        "scope": "Repository and community metrics use public data. Commit totals include public and private "
                 "owned repositories accessible to the statistics token, default branches only, deduplicated by SHA, "
                 "filtered to the owner's GitHub-linked author identity and committer dates. "
                 "Only aggregate private counts are published. Repository totals include owned forks; source repos exclude forks. "
                 "Stars and forks are received totals across owned public repos. Issues and PRs are "
                 "all-time authored public items (open and closed). Languages count the primary "
                 "language of each non-fork public repo, not code bytes or proficiency.",
    }


def publishable_snapshot(data):
    """Allowlist exported fields so auxiliary API data can never enter the JSON."""
    public_fields = ("login", "joined", "updated", "public_repos", "source_repos", "stars_received",
                     "forks_received", "followers", "following", "pull_requests", "issues", "languages", "scope")
    result = {key: data[key] for key in public_fields}
    stats = data.get("commit_stats", {"status": "not_configured"})
    fields = ("status", "total_365d", "private_365d", "total_30d", "window_end", "since_365d",
              "since_30d", "repository_scope", "branch_scope", "date_basis", "deduplication")
    result["commit_stats"] = {key: stats[key] for key in fields if key in stats}
    if stats["status"] not in ("complete", "not_configured"):
        raise ValueError("Invalid commit statistics state")
    if stats["status"] == "complete":
        for key in ("total_365d", "private_365d", "total_30d"):
            if type(stats.get(key)) is not int or stats[key] < 0:
                raise ValueError("Incomplete commit statistics")
        if max(stats["private_365d"], stats["total_30d"]) > stats["total_365d"]:
            raise ValueError("Commit subtotals exceed the total")
    return result


def render(data, theme):
    p = PALETTES[theme]
    languages = list(data["languages"].items())
    height = 722 if languages else 597
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
    text(32, 383, "Commit activity", 19, p["accent"], 600)
    stats = data.get("commit_stats", {})
    complete = stats.get("status") == "complete"
    for i, (label, key) in enumerate((("Total commits · 365 days", "total_365d"),
                                    ("Of which private · 365 days", "private_365d"),
                                    ("Total commits · 30 days", "total_30d"))):
        x = 32 + i * 273
        parts.append(f'<rect x="{x}" y="400" width="250" height="98" rx="10" fill="{p["panel"]}"/>')
        text(x + 16, 427, label, 13, p["muted"])
        value = f'{stats[key]:,}' if complete else "—"
        text(x + 16, 473, value, 32, p["text"], 650)
    note = "Owned repos available to the token · Default branches · Unique authored commits"
    if not complete:
        note = "Commit totals await private-repository access; unavailable values are not zero."
    text(32, 524, note, 12, p["muted"])
    line(32, 543, 828, 543)
    if languages:
        text(32, 575, "Languages in public source repositories", 16, p["accent"], 600)
        total = sum(n for _, n in languages)
        x = 32
        for i, (language, count) in enumerate(languages):
            color = LANGUAGE_COLORS.get(language, ["#58a6ff", "#a371f7", "#2ea88f", "#8b949e"][i % 4])
            width = 796 * count / total
            parts.append(f'<rect x="{x:.2f}" y="591" width="{width:.2f}" height="9" fill="{color}"/>')
            x += width
            lx = 32 + (i % 2) * 429
            ly = 626 + (i // 2) * 24
            parts.append(f'<circle cx="{lx + 4}" cy="{ly - 5}" r="4" fill="{color}"/>')
            text(lx + 16, ly, f"{language} · {count} {'repo' if count == 1 else 'repos'}", 13, p["muted"])
    footer = "Private activity: aggregate commit counts only" if complete else "Repository / community metrics: public data"
    text(32, height - 36, footer, 12, p["muted"])
    text(828, height - 14, "Updated " + data["updated"], 12, p["muted"], anchor="end")
    parts.extend(["</g>", "</svg>"])
    return "\n".join(parts) + "\n"


def cards_version(cards):
    """Version the allowlisted rendered output in a fixed theme order."""
    return hashlib.sha256((cards["github-stats-dark.svg"] +
                           cards["github-stats-light.svg"]).encode("utf-8")).hexdigest()[:16]


def render_readme(original, data, cards):
    """Replace only the uniquely marked block, retaining all other bytes."""
    if original.count(README_START) != 1 or original.count(README_END) != 1:
        raise ValueError("README statistics markers must each occur exactly once; no files written.")
    start, end = original.index(README_START), original.index(README_END)
    if start >= end:
        raise ValueError("README statistics markers are reversed; no files written.")
    newline = "\r\n" if original[start + len(README_START):].startswith(b"\r\n") else "\n"
    version = cards_version(cards)
    login = escape(data["login"], quote=True)
    counts = data["commit_stats"]
    complete = counts["status"] == "complete"
    values = [f'{counts[key]:,}' if complete else "unavailable"
              for key in ("total_365d", "private_365d", "total_30d")]
    block = [
        f'<a href="https://github.com/{login}">',
        '  <picture>',
        f'    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-dark-{version}.svg">',
        f'    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-light-{version}.svg">',
        f'    <img alt="{login}\'s GitHub statistics: public repositories and community activity, commits in the last 365 days, private commits in that period, and commits in the last 30 days" src="https://raw.githubusercontent.com/LHappyCureall/LHappyCureall/main/assets/profile-cards/github-stats-light-{version}.svg" width="860">',
        '  </picture>',
        '</a>',
        '',
        f'<sub>Commits (365 days): {values[0]} · Of which private: {values[1]} · Commits (30 days): {values[2]} · Updated {escape(data["updated"])}.</sub>',
    ]
    return (original[:start + len(README_START)] +
            (newline + newline.join(block) + newline).encode("utf-8") + original[end:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=os.environ.get("PROFILE_USER", "LHappyCureall"))
    parser.add_argument("--snapshot", type=Path, help="Render an existing JSON snapshot without API access")
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else collect(args.user)
    data = publishable_snapshot(data)
    assets = ROOT / "assets"
    previous_path = assets / "github-stats.json"
    if not args.snapshot and data["commit_stats"]["status"] != "complete" and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if previous.get("commit_stats", {}).get("status") == "complete":
            raise RuntimeError("Private statistics access is missing; preserving the last complete snapshot.")
    outputs = {f"github-stats-{theme}.svg": render(data, theme) for theme in PALETTES}
    outputs["github-stats.json"] = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    readme_path = ROOT / "README.md"
    readme = render_readme(readme_path.read_bytes(), data, outputs)
    version = cards_version(outputs)
    versioned = {assets / "profile-cards" / f"github-stats-{theme}-{version}.svg":
                 outputs[f"github-stats-{theme}.svg"].encode("utf-8") for theme in PALETTES}
    pending = {}
    for path, content in versioned.items():
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError("Existing versioned card has different content; no files written.")
        else:
            pending[path] = content
    # Finish all rendering, marker and immutability checks before any output writes.
    assets.mkdir(exist_ok=True)
    (assets / "profile-cards").mkdir(exist_ok=True)
    for path, content in pending.items():
        temporary = path.with_suffix(".svg.tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
    for name, content in outputs.items():
        temporary = assets / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(assets / name)
    temporary = readme_path.with_name("README.md.tmp")
    temporary.write_bytes(readme)
    temporary.replace(readme_path)
    print("Updated profile assets and README: " + ", ".join(outputs))


if __name__ == "__main__":
    main()
