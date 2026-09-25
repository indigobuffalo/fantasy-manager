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
| `LOG_LEVEL`         | no         | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` (defaults to `INFO`).        |
| `FANTASY_SEASON`    | no         | Season directory under `config/data/season` (defaults to `2026_2027`).   |
| `YEAR`              | no         | Defaults to `2026`.                                                      |

Yahoo app tokens grant read-only access, so **writes** (add/drop/replace,
waivers, lineups) impersonate a logged-in browser session using `YAHOO_COOKIE`
and `YAHOO_CRUMB`. These are harvested manually from the browser and expire
periodically — see `docs/hybrid-auth-plan.md`.

# Examples

See scripts under the scripts directory

## Misc

Update _current_leagues.py symbolic link each year to ensure current league data is used.

```
cd config/data/leagues
ln -sf 2025_2026.py _current_leagues.py
```


## TODO

- Used argparse to enforce cli arg types
- Check inputs 30 seconds before execution time to save time.
