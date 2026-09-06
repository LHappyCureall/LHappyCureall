# Profile statistics

The profile embeds repository-hosted SVG cards in light and dark themes. The
`Update profile statistics` workflow refreshes them daily at approximately
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

No personal access token, paid service, or third-party statistics server is
required. The script uses Python's standard library and the workflow's built-in
`GITHUB_TOKEN`. The workflow only needs `contents: write` to save its own assets.

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

Private repositories and private activity are excluded. Coding hours and visitor
counts are not inferred from GitHub data.

## Maintenance

Data comes from the official [GitHub REST API](https://docs.github.com/en/rest):
`GET /users/{login}`, paginated `GET /users/{login}/repos`, and
`GET /search/issues` with `author:`, `is:public`, and `is:pr` / `is:issue` filters.
`assets/github-stats.json` records the public aggregate snapshot and its timestamp.
Failed requests or incomplete search results fail the run and leave the previous
published cards in place.

To fetch fresh data locally, optionally set `GITHUB_TOKEN` in your environment and
run `python .github/scripts/update_profile.py`. Never put a token in a file.
To render the last saved snapshot without network access:

```sh
python .github/scripts/update_profile.py --snapshot assets/github-stats.json
```
