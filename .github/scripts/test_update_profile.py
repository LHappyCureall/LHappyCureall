"""Regression checks for commit attribution, aggregation, and private-data handling."""

from datetime import datetime, timedelta, timezone
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import tempfile
import re
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("profile_stats", Path(__file__).with_name("update_profile.py"))
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)
NOW = datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc)
LOGIN = "LHappyCureall"
README = b"Intro \xe4\xbd\xa0\xe5\xa5\xbd  \r\n\n" + stats.README_START + b"\r\nold card\r\n" + stats.README_END + b"\r\n\nResearch  \r\n"


def repo(name, private=False, owner=LOGIN):
    return {"full_name": f"{owner}/{name}", "owner": {"login": owner},
            "private": private, "default_branch": "main"}


def commit(sha, days, author=LOGIN):
    return {"sha": sha, "author": {"login": author} if author else None,
            "commit": {"message": "PRIVATE_MESSAGE_NEVER_EXPORT", "committer": {
                "email": "PRIVATE_EMAIL_NEVER_EXPORT", "date": stats.iso_utc(NOW - timedelta(days=days))}}}


class CommitStatsTests(unittest.TestCase):
    def fake_api(self, repositories, pages, *, identity=None):
        identity = identity or {"login": LOGIN}

        def request(path, token=None):
            self.assertEqual(token, "TEST_TOKEN_NEVER_EXPORT")
            url = urlsplit(path)
            query = parse_qs(url.query)
            if url.path == "/user":
                return identity
            if url.path == "/user/repos":
                self.assertEqual(query["affiliation"], ["owner"])
                page = int(query["page"][0])
                return repositories[(page - 1) * 100:page * 100]
            self.assertEqual(query["sha"], ["main"])
            self.assertEqual(query["author"], [LOGIN])
            self.assertEqual(query["since"], [stats.iso_utc(NOW - timedelta(days=365))])
            self.assertEqual(query["until"], [stats.iso_utc(NOW)])
            data = pages[url.path]
            if isinstance(data, Exception):
                raise data
            page = int(query["page"][0])
            return data[(page - 1) * 100:page * 100]
        return request

    def test_windows_authorship_deduplication_and_no_private_records(self):
        repositories = [repo("public"), repo("PRIVATE_REPO_NEVER_EXPORT", True), repo("excluded", True, "SomeoneElse")]
        pages = {f"/repos/{LOGIN}/public/commits": [commit("shared", 30), commit("year-boundary", 365),
                   commit("old", 366), commit("future", -1), commit("bot", 1, "github-actions[bot]"),
                   commit("unlinked", 1, None)],
                 f"/repos/{LOGIN}/PRIVATE_REPO_NEVER_EXPORT/commits": [commit("shared", 30), commit("private", 31), commit("today", 0)]}
        with patch.object(stats, "request_json", self.fake_api(repositories, pages)):
            result = stats.collect_commit_stats(LOGIN, NOW, "TEST_TOKEN_NEVER_EXPORT")
        self.assertEqual((result["total_365d"], result["private_365d"], result["total_30d"]), (4, 3, 2))
        output = json.dumps(result)
        for marker in ("NEVER_EXPORT", "shared", "SomeoneElse", "today"):
            self.assertNotIn(marker, output)

    def test_repository_and_commit_pagination(self):
        repositories = [repo(str(i), i == 100) for i in range(101)]
        pages = {f"/repos/{LOGIN}/{i}/commits": [] for i in range(101)}
        pages[f"/repos/{LOGIN}/100/commits"] = [commit(str(i), 1) for i in range(101)]
        with patch.object(stats, "request_json", self.fake_api(repositories, pages)):
            result = stats.collect_commit_stats(LOGIN, NOW, "TEST_TOKEN_NEVER_EXPORT")
        self.assertEqual((result["total_365d"], result["private_365d"], result["total_30d"]), (101, 101, 101))

    def test_missing_token_is_unknown_not_zero(self):
        with patch.object(stats, "request_json", side_effect=AssertionError("No API should be called")):
            result = stats.collect_commit_stats(LOGIN, NOW, "")
        self.assertEqual(result["status"], "not_configured")
        self.assertIsNone(result["private_365d"])
        self.assertIsNone(result["total_365d"])
        self.assertIsNone(result["total_30d"])

    def test_wrong_owner_and_incomplete_access_fail(self):
        for identity in ({"login": "SomeoneElse"}, {"login": LOGIN, "owned_private_repos": 2}):
            with self.subTest(identity=identity), patch.object(stats, "request_json", self.fake_api([], {}, identity=identity)):
                with self.assertRaises(RuntimeError):
                    stats.collect_commit_stats(LOGIN, NOW, "TEST_TOKEN_NEVER_EXPORT")

    def test_only_confirmed_empty_repositories_are_zero(self):
        path = f"/repos/{LOGIN}/empty/commits"
        for error in (stats.GitHubAPIError(403), stats.GitHubAPIError(404), stats.GitHubAPIError(409)):
            with patch.object(stats, "request_json", self.fake_api([repo("empty", True)], {path: error})):
                with self.assertRaises(stats.GitHubAPIError):
                    stats.collect_commit_stats(LOGIN, NOW, "TEST_TOKEN_NEVER_EXPORT")
        with patch.object(stats, "request_json", self.fake_api([repo("empty", True)], {path: stats.GitHubAPIError(409, True)})):
            self.assertEqual(stats.collect_commit_stats(LOGIN, NOW, "TEST_TOKEN_NEVER_EXPORT")["total_365d"], 0)

    def test_http_errors_hide_private_path_and_response(self):
        error = HTTPError("https://api.github.com/repos/PRIVATE_REPO_NEVER_EXPORT/commits", 403,
                          "PRIVATE_ERROR_NEVER_EXPORT", {}, io.BytesIO(b'{"message":"PRIVATE_BODY_NEVER_EXPORT"}'))
        with patch.object(stats, "urlopen", side_effect=error):
            with self.assertRaises(stats.GitHubAPIError) as caught:
                stats.request_json("/repos/PRIVATE_REPO_NEVER_EXPORT/commits", token="TEST_TOKEN_NEVER_EXPORT")
        self.assertNotIn("NEVER_EXPORT", str(caught.exception))

    def test_export_allowlist_and_both_theme_layouts(self):
        data = json.loads((stats.ROOT / "assets/github-stats.json").read_text(encoding="utf-8"))
        data["private_repositories"] = ["PRIVATE_REPO_NEVER_EXPORT"]
        data["commit_stats"] = {"status": "complete", "total_365d": 4, "private_365d": 3, "total_30d": 2,
                                "commits": ["PRIVATE_MESSAGE_NEVER_EXPORT"]}
        published = stats.publishable_snapshot(data)
        self.assertNotIn("NEVER_EXPORT", json.dumps(published))
        for state in ("complete", "not_configured"):
            for languages in ({}, {"Python": 1, "C++": 1}):
                published["commit_stats"]["status"] = state
                published["languages"] = languages
                for theme in stats.PALETTES:
                    svg = stats.render(published, theme)
                    root = ET.fromstring(svg)
                    self.assertNotIn("NEVER_EXPORT", svg)
                    self.assertIn("Commit activity", svg)
                    self.assertEqual(root.attrib["height"], "722" if languages else "597")
                    if state == "not_configured":
                        self.assertIn("unavailable values are not zero", svg)

    def test_lost_secret_keeps_existing_files(self):
        original = json.loads((stats.ROOT / "assets/github-stats.json").read_text(encoding="utf-8"))
        previous = {**original, "commit_stats": {"status": "complete", "total_365d": 4,
                                                "private_365d": 3, "total_30d": 2}}
        current = {**original, "commit_stats": {"status": "not_configured"}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "assets").mkdir()
            snapshot = root / "assets/github-stats.json"
            snapshot.write_text(json.dumps(previous), encoding="utf-8")
            (root / "README.md").write_bytes(README)
            for theme in stats.PALETTES:
                (root / f"assets/github-stats-{theme}.svg").write_bytes(b"previous card " + theme.encode())
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(stats, "ROOT", root), patch.object(stats, "collect", return_value=current), patch("sys.argv", ["update_profile.py"]):
                with self.assertRaises(RuntimeError):
                    stats.main()
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()})


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.data = stats.publishable_snapshot(json.loads((stats.ROOT / "assets/github-stats.json").read_text(encoding="utf-8")))
        self.data["commit_stats"] = {"status": "complete", "total_365d": 155, "private_365d": 133, "total_30d": 24}
        self.cards = {f"github-stats-{theme}.svg": stats.render(self.data, theme) for theme in stats.PALETTES}

    def test_three_direct_urls_share_content_version_and_text_matches(self):
        result = stats.render_readme(README, self.data, self.cards).decode()
        versions = re.findall(r'https://raw\.githubusercontent\.com/LHappyCureall/LHappyCureall/main/assets/github-stats-(dark|light)\.svg\?v=([0-9a-f]{16})', result)
        expected = hashlib.sha256((self.cards["github-stats-dark.svg"] + self.cards["github-stats-light.svg"]).encode()).hexdigest()[:16]
        self.assertEqual(versions, [("dark", expected), ("light", expected), ("light", expected)])
        self.assertIn("Commits (365 days): 155 · Of which private: 133 · Commits (30 days): 24", result)
        self.assertIn("Updated " + self.data["updated"], result)
        for theme in stats.PALETTES:
            changed = {**self.cards, f"github-stats-{theme}.svg": self.cards[f"github-stats-{theme}.svg"] + "\n"}
            self.assertNotIn("?v=" + expected, stats.render_readme(README, self.data, changed).decode())

    def test_idempotent_and_preserves_outside_bytes_and_line_endings(self):
        for original in (README, README.replace(b"\r\n", b"\n")):
            result = stats.render_readme(original, self.data, self.cards)
            self.assertEqual(result, stats.render_readme(result, self.data, self.cards))
            self.assertEqual(original.split(stats.README_START)[0], result.split(stats.README_START)[0])
            self.assertEqual(original.split(stats.README_END)[1], result.split(stats.README_END)[1])
            body = result.split(stats.README_START)[1].split(stats.README_END)[0]
            if b"\r\n" in original:
                self.assertNotIn(b"\n", body.replace(b"\r\n", b""))
            else:
                self.assertNotIn(b"\r", body)

    def test_missing_counts_are_unavailable_even_with_stale_values(self):
        self.data["commit_stats"]["status"] = "not_configured"
        result = stats.render_readme(README, self.data, self.cards).decode()
        self.assertEqual(result.count(": unavailable"), 3)
        self.assertNotIn("Commits (365 days): 0", result)
        self.assertNotIn("Of which private: 133", result)

    def test_bad_markers_fail_before_any_file_write(self):
        invalid = [b"no markers", README.replace(stats.README_START, b""),
                   README.replace(stats.README_END, b""), README + stats.README_START,
                   README + stats.README_END, stats.README_END + b"\n" + stats.README_START]
        for readme in invalid:
            with self.subTest(readme=readme), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "assets").mkdir()
                (root / "README.md").write_bytes(readme)
                (root / "assets/github-stats.json").write_text(json.dumps(self.data), encoding="utf-8")
                for theme in stats.PALETTES:
                    (root / f"assets/github-stats-{theme}.svg").write_bytes(b"old card")
                before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                with patch.object(stats, "ROOT", root), patch.object(stats, "collect", return_value=self.data), patch("sys.argv", ["update_profile.py"]), patch.object(Path, "write_text", side_effect=AssertionError("Write before validation")), patch.object(Path, "write_bytes", side_effect=AssertionError("Write before validation")):
                    with self.assertRaises(ValueError):
                        stats.main()
                self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_offline_main_publishes_matching_files_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "assets").mkdir()
            (root / "README.md").write_bytes(README)
            snapshot = root / "assets/github-stats.json"
            snapshot.write_text(json.dumps(self.data), encoding="utf-8")
            with patch.object(stats, "ROOT", root), patch.object(stats, "request_json", side_effect=AssertionError("Offline only")), patch("sys.argv", ["update_profile.py", "--snapshot", str(snapshot)]):
                stats.main()
                first = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                stats.main()
            self.assertEqual(first, {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertEqual(first[Path("README.md")], stats.render_readme(README, self.data, self.cards))
            for name, card in self.cards.items():
                self.assertEqual(first[Path("assets") / name], card.encode())


if __name__ == "__main__":
    unittest.main()
