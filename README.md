# Setup

## Local Development

Setup python environment:
```
brew install uv

# setup virtual environment and install dependencies
uv venv
uv sync --dev

# install the project in editable mode for local development
uv pip install -e .
```

## Configuration

Configuration is loaded from environment variables (via `dotenv`). Copy the
template and fill in your values:

```
cp .env.example .env
```

`.env` is git-ignored, so your secrets stay local.

| Variable            | Required   | Purpose                                                                 |
|---------------------|------------|-------------------------------------------------------------------------|
| `YAHOO_CREDS_FILE`  | yes        | Path to the Yahoo OAuth2 credentials file. Used for **reads** (rosters, teams, player lookups). |
| `YAHOO_COOKIE`      | for writes | Browser-harvested cookie header for the cookie write transport.         |
| `YAHOO_CRUMB`       | for writes | Browser-harvested crumb form token for the cookie write transport.      |
| `YAHOO_FORCE_COOKIE_READS` | no  | Truthy (`1`/`true`/`yes`/`on`) to skip the startup OAuth read probe and route **reads** straight to the cookie transport. Use when OAuth reads are known-gated by Yahoo. |
| `LOG_LEVEL`         | no         | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` (defaults to `INFO`).        |
| `FANTASY_SEASON`    | no         | Season directory under `config/data/season` (defaults to `2026_2027`).   |
| `YEAR`              | no         | Defaults to `2026`.                                                      |
| `BLUESKY_HANDLE`    | for news   | Bluesky handle for the news-monitor source account.                     |
| `BLUESKY_APP_PASSWORD` | for news | Bluesky app password for the news-monitor source account.               |
| `BLUESKY_LIST_URI`  | for news   | `at://` URI of the Bluesky list to monitor for player news.             |
| `SMTP_HOST`         | for news   | SMTP server host for emailed news alerts.                               |
| `SMTP_PORT`         | for news   | SMTP server port (e.g. `587`).                                          |
| `SMTP_USERNAME`     | for news   | SMTP auth username for emailed news alerts.                             |
| `SMTP_PASSWORD`     | for news   | SMTP auth password for emailed news alerts.                             |
| `NEWS_ALERT_EMAIL`  | for news   | Recipient address for emailed news alerts.                              |

### Hybrid auth: OAuth for reads, cookie for writes

Yahoo now grants app OAuth2 tokens **read-only** access, so this tool uses two
transports behind one client:

- **Reads** (rosters, teams, player lookups) use the **OAuth2** API
  (`YAHOO_CREDS_FILE`), with an automatic fallback to the cookie transport when
  Yahoo gates OAuth reads at the app level.
- **Writes** (add/drop/replace, waivers, lineups) impersonate a logged-in
  browser session using `YAHOO_COOKIE` and `YAHOO_CRUMB`, POSTing to Yahoo's
  HTML form endpoints. **OAuth alone cannot write** — without a valid
  cookie/crumb, every mutating command fails.

The cookie and crumb are harvested manually from the browser and expire
periodically, so writes need a periodic re-harvest (see below). For the full
rationale and transport internals, see `docs/hybrid-auth-plan.md`.

### Yahoo app registration

Reads authenticate through a Yahoo app registered in the [Yahoo Developer
Network](https://developer.yahoo.com/apps/):

| Field              | Value                                   |
|--------------------|-----------------------------------------|
| App name           | `draft-tracker`                         |
| Description        | Monitoring and Interacting with Live Drafts |
| Homepage URL       | `https://localhost`                     |
| Redirect URI       | `https://localhost`                     |
| OAuth client type  | Confidential Client                     |
| API permissions    | Fantasy Sports (Read); OpenID Connect (Email, Profile) |

The app's **Client ID** and **Client Secret** map to `consumer_key` and
`consumer_secret` in the OAuth2 credentials JSON pointed to by
`YAHOO_CREDS_FILE`. Keep that file outside any git worktree (e.g.
`~/.config/fantasy-manager/yahoo_oauth2.json`) so cached tokens are shared
across worktrees and survive teardown.

### Harvesting the cookie & crumb

Writes replay a logged-in browser session, so you must harvest `YAHOO_COOKIE`
and `YAHOO_CRUMB` by hand. Both come from a normal Yahoo Fantasy browser
session and expire periodically — when writes start failing with an auth error,
re-harvest them.

1. Log into Yahoo Fantasy in your browser and open one of your fantasy teams
   (e.g. `https://hockey.fantasysports.yahoo.com/hockey/<league>/<team>`).
2. Open DevTools → **Network**, then reload the team page.
3. Click the top (document) request, find **Request Headers**, and copy the
   entire `cookie:` header value. Paste it into `.env` as `YAHOO_COOKIE` (one
   long line, no surrounding quotes).
4. Grab the `crumb` token. The simplest way: on the team page, trigger any
   roster edit (e.g. open Add/Drop) and inspect the form POST in the Network
   tab — the form body contains a `crumb=<token>` field. (It's also present in
   the page HTML; search the page source for `crumb`.) Copy just the token
   value into `.env` as `YAHOO_CRUMB`.
5. Confirm both transports are healthy — the startup auth self-check logs
   whether OAuth reads **and** the cookie transport are working:

   ```
   ./scripts/read_roster.sh kkupfl               # or: pa
   ```

   If the cookie is stale or logged out, the tool fails loudly with a Yahoo
   auth error; redo steps 1–4 to re-harvest.

> **Note:** The cookie and crumb must come from the **same** logged-in session,
> and the crumb is tied to that cookie — if you re-harvest one, re-harvest both.

# Examples

See scripts under the scripts directory. For example, read a team's roster
end-to-end (a live smoke test of the read path) with:

```
./scripts/read_roster.sh kkupfl               # or: pa
# equivalent to: uv run python scripts/read_roster.py kkupfl
```

## Misc

Update _current_leagues.py symbolic link each year to ensure current league data is used.

```
cd config/data/leagues
ln -sf 2025_2026.py _current_leagues.py
```


## TODO

- Used argparse to enforce cli arg types
- Check inputs 30 seconds before execution time to save time.
