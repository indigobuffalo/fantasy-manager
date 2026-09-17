# Hybrid Auth Plan — restoring write access after Yahoo's read-only token change

## Background

Yahoo changed its app-token policy so that OAuth2 app tokens now grant **read
access only**. The `major_refactor` architecture routed *every* Yahoo
interaction — reads and writes — through the official `yahoo_fantasy_api` +
`yahoo_oauth` OAuth2 flow (`YahooClient._refresh_context`). As a result, all
mutating actions (add / drop / replace players, waiver claims, and lineup
changes) now fail against the API.

The pre-refactor `master` tool wrote to Yahoo by impersonating a logged-in
browser session: a `requests.Session` with a manually harvested `cookie` header
plus a `crumb` form token, POSTing to Yahoo's HTML form endpoints. That path
still works because it acts as the logged-in **user**, who retains full write
access.

## Strategy: one client, two transports

We keep the refactor and reintroduce the cookie transport *behind the existing
client interface* — the abstraction (`BaseFantasyClient` + `client/factory.py` +
`transform/`) was built for exactly this swap.

- **Reads** (`get_team`, `get_player_by_id`, roster reads) → stay on the
  official **OAuth2** API. Still allowed, typed, robust. (Player rankings are
  loaded from local YAML config, not Yahoo, so they're unaffected regardless.)
- **Writes** (`add_player`, `drop_player`, `replace_player`,
  `add_player_claim`, `replace_player_claim`, `cancel_waiver_claim`,
  `set_lineup`) → move to a **cookie + crumb** `requests.Session`.

Nothing above the client layer changes: `service/`, `controller/`, `cli/`,
models, and the retry/timeout loop (`RosterService._execute_with_timeout`) are
untouched. Client write-method signatures stay identical; only the transport
inside them changes.

### Recovered reference implementation

The cookie mechanics are recoverable from git history (pre-refactor
`update_roster.py`, commit `2fe2fa3`):

| Action        | Endpoint (POST, form-encoded)     | Key form fields                                                        |
|---------------|-----------------------------------|-----------------------------------------------------------------------|
| add / replace | `{team_url}/addplayer`            | `stage=3, crumb, stat1=P, stat2=P, apid=<add_id>[, dpid=<drop_id>]`    |
| set lineup    | `{team_url}/editroster`           | `ret=swap, date=<YYYY-MM-DD>, stat1=S, stat2=D, crumb, <position map>` |
| cancel waiver | `{team_url}/editwaiver`           | `stage=2, crumb, claim_id=1_<pid>_0, mode=edit, apid=<pid>, s=Cancel Waiver` |

Response success/failure is determined by scanning the returned HTML for marker
strings, e.g. `player has already played and is no longer` → `AlreadyPlayedError`,
`You have reached the weekly limit` → `MaxAddsError`,
`created%2520a%2520waiver%2520claim%2520for` → unintended-waiver. These map onto
the existing `exceptions.py` types (the same errors `_handle_client_error`
already raises), so the service layer sees no difference.

### Known trade-offs (accepted)

- The cookie + crumb are **harvested manually from the browser** and expire
  periodically. A stale cookie must fail loudly (see auth check below).
- Writes depend on Yahoo's HTML markup, so they can break if Yahoo changes their
  forms — same fragility as the original `master` tool.
- If Yahoo ever restores write access to app tokens, delete the cookie transport
  and the client is pure OAuth again.

---

## Work breakdown (one PR per chunk)

Ordered; each PR is independently reviewable and (2 onward) independently
mergeable. **This document lands in PR 1.**

### PR 1 — Plan (this PR)
- Add `docs/hybrid-auth-plan.md` (this file). No code changes.

### PR 2 — Config & secrets plumbing
- Add `YAHOO_COOKIE` and `YAHOO_CRUMB` to `FantasyConfig` via `dotenv`
  (mirrors existing `YAHOO_CREDS_FILE`).
- Document required env vars in `README.md` / `.env.example`; confirm secrets
  are git-ignored.
- No behavior change — purely foundational.

### PR 3 — Dual-transport scaffolding in `YahooClient`
- In `_refresh_context`, build a second transport alongside `session_context`:
  a cookie-backed `requests.Session` (`cookie` header + stored `crumb`).
- Add `_check_cookie_auth()` — reuse the "are my `locked_players` present in the
  team-page HTML" heuristic so a stale cookie raises `FantasyAuthError` early.
  (Keep the OAuth `_check_locked_players` for the read path.)
- Add a small `_post_write(path, data)` helper (single POST + response-marker
  check → mapped exception). No write methods rewired yet; reads unaffected.

### PR 4 — Add / drop / replace over cookie transport  ← core value
- Rewrite `add_player`, `drop_player`, `replace_player` to POST via
  `_post_write` (`/addplayer` with `crumb`) instead of `team_handle.*`.
- Port the response-marker → exception mapping onto existing `exceptions.py`.
- Client methods stay single-shot; `RosterService._execute_with_timeout`
  keeps owning the poll/retry/timeout loop.
- Update unit tests (`tests/service/test_roster_service.py`,
  `tests/controller/`) to mock the write session instead of `team_handle`.
- **After this PR, add/drop is functional again.**

### PR 5 — Waiver claims over cookie transport
- `add_player_claim`, `replace_player_claim`, `cancel_waiver_claim` →
  `/editwaiver` forms (`cancel_waiver_claim` template exists in `2fe2fa3`;
  claim-placement forms may need reconstruction/verification).
- Split from PR 4 because waivers are less certain and add/drop shouldn't wait
  on them.

### PR 6 — `set_lineup` over cookie transport
- Port `edit_lineup` (`/editroster`, `ret=swap`) — serialize the `Lineup`
  model into Yahoo's per-player position form fields.
- Remove the hardcoded date and commented block currently in
  `YahooClient.set_lineup`.
- Ships last: it's the newest, still-WIP feature.

### PR 7 — Docs & end-to-end verification (optional)
- README refresh: OAuth = reads, cookie = writes; how to harvest cookie/crumb.
- Note in `scripts/yfa_init_oauth_env` that OAuth alone no longer enables writes.
- Verify the full add / drop / replace / lineup flow against a real league.

---

## Dependencies

```
PR1 (plan)
  └─ PR2 (config)
       └─ PR3 (scaffolding)
            └─ PR4 (add/drop/replace)  ← restores core functionality
                 ├─ PR5 (waivers)
                 └─ PR6 (set_lineup)
                      └─ PR7 (docs + e2e verify)
```
