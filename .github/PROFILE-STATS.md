# Profile statistics

The profile embeds repository-hosted SVG cards in light and dark themes. The
README uses direct `raw.githubusercontent.com` image URLs with a shared `?v=`
version derived from the first 16 hexadecimal characters of SHA-256 over the
rendered dark SVG followed by the light SVG. A change in either card changes all
three image references, avoiding stale image URLs. Direct raw URLs avoid the
GitHub `/raw/` redirect, which removes query parameters. The same snapshot also
supplies a small text line with the three commit totals and its UTC update time,
so the numbers remain readable while an image is loading or cached. Unavailable
totals are labeled `unavailable`, never zero.

The `Update profile statistics` workflow refreshes them daily at approximately
08:23 Asia/Macau and can be run manually from the Actions tab. GitHub can delay
scheduled runs and disables scheduled workflows in public repositories after
60 days without repository activity; re-enable the workflow if that happens.

A Scheduled task in the desktop app also checks the published snapshot every day
at 08:35 Asia/Macau. When today's update is missing and no statistics job is
running, it requests a refresh by committing a new timestamp to
`.github/profile-refresh-request.json`. This path is a push trigger for the same
workflow, so the task can use ordinary Git authentication without a personal
access token or additional Actions API permissions. The request file contains no
statistics; the workflow still fetches all numbers directly from GitHub.
The desktop app and computer must be running for this local backup check.

Public metrics use Python's standard library and the workflow's built-in
`GITHUB_TOKEN`. The three commit totals also use the read-only
`PROFILE_STATS_TOKEN` secret to access owned private repositories. The workflow
continues to use its separate built-in token with `contents: write` only to save
assets and the managed README block in this profile repository. No paid service or third-party statistics
server is used.

## What the numbers mean

- **Public repositories:** repositories owned by this account, including forks.
- **Non-fork repositories:** owned public repositories excluding forks.
- **Stars / forks received:** summed across owned public repositories. These are
  different from repositories the account has starred or forked.
- **Followers / following:** public account counts.
- **Pull requests / issues opened:** all-time public items authored by the account,
  including both open and closed items. GitHub Search may take time to index changes.
- **Languages:** number of public non-fork repositories with each primary language,
  excluding repositories for which GitHub has not detected a language. This is
  not a code-byte percentage or a measure of proficiency. More than four languages
  are displayed as the top three plus Other.

The repository, star, fork, follower, issue, PR, and language figures above remain
public-only. Only the following three metrics include private activity:

- **Total commits · 365 days:** unique commits authored by this GitHub account in
  the rolling last 365 days across owned repositories accessible to the token.
- **Of which private · 365 days:** the subset of those unique commits found in at
  least one owned private repository.
- **Total commits · 30 days:** unique authored commits in the rolling last 30 days
  across the same public and private repositories.

Each repository's default branch is used, including owned forks. Identical commit
SHAs across repositories count once in the total. A commit present in both a
public and a private repository counts once in the total and once in the private
subset. Attribution uses the GitHub-linked **author**, excluding other authors
and automation bots. Dates use the **committer timestamp** in UTC with inclusive
window boundaries. These are commit counts, not GitHub contribution-calendar
counts; unmerged branches and commits not linked to this account are excluded.

All requests and pagination must finish before results are published. Missing
private access initially displays dashes, never zero. An invalid/expired token,
inaccessible repository, incomplete response, or subsequently removed secret
fails the run and retains the last complete snapshot. When the authenticated user
API supplies account repository totals, the script checks them against the
repository list to detect incomplete token access. Otherwise the scope remains
the repositories visible to the token; choose **All repositories** to cover all
personal repositories, including repositories created later.

No private repository name, URL, commit SHA, message, email, or source code is
written to the SVG, JSON, README, or logs. API paths and error response bodies are omitted
from error messages. Private data is aggregated in memory. Coding hours and
visitor counts are not inferred.

## Enable private commit statistics (one-time setup)

1. Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new)
   for resource owner **LHappyCureall**, with **All repositories** and repository
   permission **Contents: Read-only**. Metadata read access is implicit. Leave
   write permissions disabled and choose an expiration appropriate for you.
2. In this profile repository's [Actions secrets](https://github.com/LHappyCureall/LHappyCureall/settings/secrets/actions),
   add a repository secret named **PROFILE_STATS_TOKEN**, with that token as the
   value. Paste it directly into GitHub; never send it in chat or commit it.
3. From Actions, manually run **Update profile statistics**, or let the next
   daily run refresh the card. Merely adding a secret does not trigger a run.

On token expiry, replace the secret and rerun the workflow. The public profile
exposes only the three aggregate numbers; the private repositories remain private.

## Maintenance

Data comes from the official [GitHub REST API](https://docs.github.com/en/rest):
`GET /users/{login}`, paginated `GET /users/{login}/repos`, and
`GET /search/issues` with `author:`, `is:public`, and `is:pr` / `is:issue` filters.
Commit metrics additionally use authenticated `GET /user`, paginated
`GET /user/repos?affiliation=owner&visibility=all`, and paginated repository commit
lists with explicit author, default branch, and time-window filters.
`assets/github-stats.json` records the aggregate snapshot, the three commit
counts, and their UTC window boundaries. It contains no per-repository private
records. Its exported keys are allowlisted.
Failed requests or incomplete search results fail the run and leave the previous
published cards and README in place.

Keep exactly one `<!-- PROFILE-STATS:START -->` marker followed by exactly one
`<!-- PROFILE-STATS:END -->` marker in `README.md`. The generator replaces only
their contents; all bytes outside the markers, including line endings, are
preserved. Edit surrounding profile content normally. Edits inside the managed
block will be overwritten. The image URLs target this repository's `main` branch;
update the generator if the repository is renamed or the default branch changes.
All output is rendered and the markers validated before any file is written.
The README is saved last, and the workflow commits it together with the three
assets. README and asset changes are not workflow push triggers, avoiding a loop.
Missing private access preserves the previous complete snapshot and README.

To fetch fresh data locally, set `GITHUB_TOKEN` for public metrics and optionally
`PROFILE_STATS_TOKEN` for private commit totals in your environment, then run
`python .github/scripts/update_profile.py`. Never put a token in a file.
To render the last saved snapshot without network access:

```sh
python .github/scripts/update_profile.py --snapshot assets/github-stats.json
```

This offline command also refreshes the managed README block. To run regression
checks without API access, use `python -m unittest discover -s .github/scripts -p 'test_*.py'`.
