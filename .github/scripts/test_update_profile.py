"""Regression checks for commit attribution, aggregation, and private-data handling."""

from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
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
            before = snapshot.read_bytes()
            with patch.object(stats, "ROOT", root), patch.object(stats, "collect", return_value=current), patch("sys.argv", ["update_profile.py"]):
                with self.assertRaises(RuntimeError):
                    stats.main()
            self.assertEqual(before, snapshot.read_bytes())
            self.assertFalse((root / "assets/github-stats-light.svg").exists())


if __name__ == "__main__":
    unittest.main()
