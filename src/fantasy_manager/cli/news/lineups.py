"""Read NHL line combinations from DailyFaceoff.

Thin CLI surface over :class:`DailyFaceoffClient`: it fetches the requested teams'
line-combinations pages (all 32 when none are named), then renders them either as
a human-readable per-team report (``--output text``, the default) or as a
machine-readable payload (``--output json|yaml``) for piping to ``jq``/``yq``.

The structured payload adopts the project's shared ``--output`` convention
(:mod:`fantasy_manager.util.output`): a versioned, stable top-level shape built
from the parsed feed. Teams are emitted as an ordered list (the order the slugs
were requested, so output is deterministic), each carrying a ``readable`` flag —
a team whose page couldn't be fetched is kept in the list with ``readable:
false`` rather than silently dropped, so a consumer sees every requested team.

Unlike ``player availability`` (where an unreadable league escalates to a
non-zero exit), a team that fails here does NOT fail the run: skipping a bad page
and serving the rest is the client's designed behavior. Only a total wipeout —
not a single team could be fetched — surfaces as an error (the client raises
``NewsSourceUnavailableError``, caught below into a structured error payload).
"""

import logging
from typing import Any, Optional

from fantasy_manager.cli import command
from fantasy_manager.client.news.dailyfaceoff import (
    DailyFaceoffClient,
    SOURCE,
    TEAM_SLUGS,
)
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import FantasyManagerError, InputError
from fantasy_manager.model.lines import LinesFeed
from fantasy_manager.util.output import (
    OutputFormat,
    error_payload,
    parse_output_format,
)

# The dedicated stdout logger (plain ``%(message)s``); the per-team report is
# data meant for reading/piping, so it goes to stdout rather than the diagnostic
# stderr logger the CLI framing uses. Mirrors ``player availability``.
STDOUT = logging.getLogger("stdout")

# Version of the structured (``--output json|yaml``) payload shape. Emitted as a
# top-level ``version`` field so downstream jq/yq consumers can pin to — and
# branch on — a known schema; bump it on any backwards-incompatible change
# (renamed/removed fields, changed nesting). Additive fields don't require a bump.
SCHEMA_VERSION = 1


def resolve_slugs(teams: list[str]) -> list[str]:
    """The team slugs to fetch: the ones named, else every team DailyFaceoff lists.

    No positional teams means "the whole league" — the client's own default — so
    ``fmgr news lineups`` with no args pulls all 32 pages. Named teams are passed
    through verbatim (an unknown slug simply 404s and comes back ``readable:
    false``), so this stays a thin resolver with no baked-in validation.
    """
    named = [slug.strip() for slug in teams if slug.strip()]
    return named or list(TEAM_SLUGS)


def resolve_workers(workers_arg: Optional[str]) -> int:
    """Parse ``--workers`` into a positive int, falling back to the configured default.

    The default lives in config (``DEFAULT_LINEUPS_WORKERS``) rather than the
    usage string. A non-numeric or non-positive value is a user error, surfaced
    as a clean ``InputError`` instead of a raw ``ValueError`` from ``int()``.
    Mirrors ``player availability``'s ``resolve_workers``.
    """
    raw = (
        workers_arg
        if workers_arg is not None
        else FantasyConfig.DEFAULT_LINEUPS_WORKERS
    )
    try:
        workers = int(raw)
    except (TypeError, ValueError):
        raise InputError(f"--workers must be an integer, got '{raw}'.")
    if workers < 1:
        raise InputError(f"--workers must be at least 1, got {workers}.")
    return workers


def _team_entry(slug: str, team_dump: Optional[dict]) -> dict[str, Any]:
    """One entry of the payload's ``teams`` list.

    A fetched team spreads its JSON-dumped fields under a leading ``slug`` +
    ``readable: true`` (``team_slug`` is dropped — ``slug`` is the canonical key).
    A team that couldn't be fetched is a minimal ``readable: false`` stub, so
    every requested team still appears exactly once, in request order.
    """
    if team_dump is None:
        return {"slug": slug, "readable": False}
    rest = {key: value for key, value in team_dump.items() if key != "team_slug"}
    return {"slug": slug, "readable": True, **rest}


def build_payload(
    feed: LinesFeed, requested_slugs: list[str], stale: bool
) -> dict[str, Any]:
    """Build the versioned structured payload from a parsed feed.

    ``feed.teams`` holds only the teams that parsed; ``requested_slugs`` drives
    the output order and lets us mark anything missing ``readable: false``. The
    feed is dumped with ``mode="json"`` so its ``datetime``/``Enum`` fields become
    JSON/YAML-native primitives (the shared ``serialize`` helper uses a plain
    ``json.dumps``/``yaml.safe_dump`` with no custom encoder).
    """
    dump = feed.model_dump(mode="json")
    teams_by_slug = dump.get("teams", {})
    return {
        "version": SCHEMA_VERSION,
        "source": dump.get("source"),
        "updated_at": dump.get("updated_at"),
        "stale": stale,
        "injuries_status": dump.get("injuries_status"),
        "injuries_updated_at": dump.get("injuries_updated_at"),
        "sport": dump.get("sport"),
        "teams": [
            _team_entry(slug, teams_by_slug.get(slug)) for slug in requested_slugs
        ],
    }


def _units_line(label: str, units: list[list[dict]]) -> list[str]:
    """Render numbered units (F1, D2, PP1, ...) as ``<label><n>: a - b - c`` lines."""
    lines = []
    for index, unit in enumerate(units, start=1):
        names = " - ".join(player.get("full", "?") for player in unit)
        lines.append(f"  {label}{index}: {names}")
    return lines


def _render_team_text(entry: dict[str, Any]) -> None:
    """Emit one team's human-readable report to the stdout logger."""
    if not entry.get("readable", False):
        STDOUT.info(
            f"\n{entry['slug']}\n"
            + "=" * len(entry["slug"])
            + "\n  Could not read team page — skipped (see warnings on stderr)."
        )
        return

    name = entry.get("team_name") or entry["slug"]
    abbr = entry.get("team_abbr")
    header = f"{name} ({abbr})" if abbr else name
    updated = entry.get("updated_at")
    STDOUT.info(f"\n{header}  updated_at={updated}\n" + "=" * len(header))

    lines: list[str] = []
    lines += _units_line("F", entry.get("forward_lines", []))
    lines += _units_line("D", entry.get("defense_pairs", []))
    for goalie in entry.get("goalies", []):
        tag = "STARTER" if goalie.get("is_starter") else "backup"
        lines.append(
            f"  G ({tag}): {goalie.get('goalie', {}).get('full', '?')} "
            f"[{goalie.get('confidence')}]"
        )
    lines += _units_line("PP", entry.get("power_play_units", []))
    lines += _units_line("PK", entry.get("penalty_kill_units", []))
    injuries = entry.get("injuries", [])
    if injuries:
        rendered = ", ".join(
            f"{inj.get('player', {}).get('full', '?')} ({inj.get('status')})"
            for inj in injuries
        )
        lines.append(f"  Injuries: {rendered}")
    STDOUT.info("\n".join(lines) if lines else "  (no line data posted)")


class Lineups(command.CliCommand):
    """fantasy-manager news lineups
    Usage:
        fantasy-manager news lineups [--workers=<workers>] [--output=<format>] [<team>...]

    Arguments:
        <team>  DailyFaceoff team slug(s), e.g. edmonton-oilers. When omitted,
                all 32 teams are fetched.

    Options:
        --workers=<workers>  Max concurrent team-page fetches. Defaults to the
                             configured DEFAULT_LINEUPS_WORKERS.
        -o <format>, --output=<format>
                             Output format: text (default), json, or yaml.
                             json/yaml emit a machine-readable payload on stdout
                             for piping to jq/yq."""

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        """Fetch line combinations and build the result for ``--output``.

        The format is resolved up front so an *expected* failure (every requested
        team unreadable → ``NewsSourceUnavailableError``, or a bad ``--workers``)
        still emits a structured ``{"error": {...}}`` payload on stdout for
        json/yaml consumers rather than an empty stream. A bad ``--output`` value
        propagates to the runner (we can't serialize to an unknown format), which
        frames it as plain text; truly unexpected exceptions do likewise.
        """
        output_format = parse_output_format(args.get("--output"))
        try:
            return self._report(args, output_format)
        except FantasyManagerError as err:
            return command.error_result(
                err,
                str(err),
                data={"version": SCHEMA_VERSION, **error_payload(err)},
                output_format=output_format,
            )

    def _report(
        self, args: dict[str, Any], output_format: OutputFormat
    ) -> command.CommandResult:
        """Do the fetch and build the result for ``output_format``."""
        slugs = resolve_slugs(args.get("<team>") or [])
        workers = resolve_workers(args.get("--workers"))

        client = DailyFaceoffClient(max_workers=workers)
        # A total wipeout raises NewsSourceUnavailableError (caught in run); a
        # partial failure just omits those teams from feed.teams, which
        # build_payload marks ``readable: false``.
        feed = client.fetch_lines(slugs=slugs)
        payload = build_payload(feed, slugs, stale=client.is_stale(feed))

        if output_format is OutputFormat.TEXT:
            for entry in payload["teams"]:
                _render_team_text(entry)

        readable = sum(1 for entry in payload["teams"] if entry.get("readable"))
        return command.success_result(
            f"Read lines for {readable}/{len(slugs)} team(s) from {SOURCE}.",
            data=payload,
            output_format=output_format,
        )
