"""Make a change to your roster via Free Agency"""
import copy
from typing import Any

from fantasy_manager.cli import command
from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.controller.roster import RosterController
from fantasy_manager.model.team import Team
from fantasy_manager.service.roster import RosterService
from fantasy_manager.util.cli import cli_arg_to_int


def format_args(args: dict[str, Any]) -> dict[str, Any]:
    formatted = copy.deepcopy(args)
    formatted["--add"] = (
        cli_arg_to_int("--add", args["--add"]) if args["--add"] is not None else None
    )
    formatted["--drop"] = (
        cli_arg_to_int("--drop", args["--drop"]) if args["--drop"] is not None else None
    )
    formatted["--faab"] = (
        cli_arg_to_int("--faab", args["--faab"]) if args["--faab"] is not None else None
    )
    return formatted


def add_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, start = args["--add"], args["--start"]
    controller.add_player(add_id=add_id, start=start)
    return command.success_result(f"Succesfully added player {add_id}")


def add_player_claim(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, start, faab = args["--add"], args["--start"], args["--faab"]
    controller.add_player_claim(add_id=add_id, start=start, faab=faab)
    return command.success_result(
        f"Succesfully placed waiver claim for player {add_id}"
    )


def drop_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    drop_id, start, = (
        args["--drop"],
        args["--start"],
    )
    controller.drop_player(drop_id=drop_id, start=start)
    return command.success_result(f"Succesfully dropped player {drop_id}")


def replace_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, drop_id, start = (
        args["--add"],
        args["--drop"],
        args["--start"],
    )
    controller.replace_player(add_id=add_id, drop_id=drop_id, start=start)
    return command.success_result(
        f"Succesfully added player {add_id} and dropped player {drop_id}"
    )


def replace_player_claim(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, drop_id, start, faab = (
        args["--add"],
        args["--drop"],
        args["--start"],
        args["--faab"],
    )
    controller.replace_player_claim(
        add_id=add_id, drop_id=drop_id, start=start, faab=faab
    )
    return command.success_result(
        f"Succesfully placed waiver claim to add player {add_id} and drop player {drop_id}"
    )


def cancel_waiver_claim(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, drop_id = args["--add"], args["--drop"]
    controller.cancel_waiver_claim(add_id=add_id, drop_id=drop_id)
    if drop_id is not None:
        return command.success_result(
            f"Succesfully canceled waiver claim to add player {add_id} and drop player {drop_id}"
        )
    return command.success_result(
        f"Succesfully canceled waiver claim for player {add_id}"
    )


def read_roster(team: Team) -> command.CommandResult:
    """Render the team's current roster (a read-only view of the read path)."""
    lines = [
        f"Team: {team.name}  (team_id={team.team_id}, league={team.league_id})",
        f"Roster ({len(team.roster)} players):",
    ]
    for p in team.roster:
        positions = ",".join(pos.value for pos in p.eligible_positions)
        lines.append(
            f"  - {p.player_id:>6}  {str(p.name):<24}  "
            f"pos={p.selected_position.value:<4} eligible=[{positions}]"
        )
    if not team.roster:
        lines.append(
            "WARNING: roster came back empty — the read path returned no players."
        )
    return command.success_result("\n".join(lines))


class Roster(command.CliCommand):
    """fantasy-manager roster
    Usage:
        fantasy-manager roster read --league=<league_name>
        fantasy-manager roster add --league=<league_name> --add=<player_id> [--start=<start_date>]
        fantasy-manager roster add claim --league=<league_name> --add=<player_id> [--faab=<faab] [--start=<start_date>]
        fantasy-manager roster drop --league=<league_name> --drop=<player_id> [--start=<start_date>]
        fantasy-manager roster replace --league=<league_name> --add=<player_id>  --drop=<player_id> [--start=<start_date>]
        fantasy-manager roster replace claim --league=<league_name> --add=<player_id>  --drop=<player_id> [--faab=<faab>] [--start=<start_date>]
        fantasy-manager roster cancel claim --league=<league_name> --add=<player_id> [--drop=<player_id>]

    Options:
          --league=<league>     Id of the league the team is under.
          --add=<player_id>     Id of player to add.
          --drop=<player_id>    Id of player to drop.
          --faab=<faab>         The amount of faab to bid on a player.
          --start=<start_date>  The date time to execute the transaction. Can use the string 'now' to run immediately."""

    @staticmethod
    def run(args: dict[str, Any]) -> command.CommandResult:
        """Update roster by adding, dropping and/or submitting waiver claims for players"""

        args = format_args(args)

        league_abbr = args["--league"]

        fc = FantasyConfig()
        league = fc.get_league(league_abbr)
        client = ClientFactory.get_fantasy_client(
            platform=league.platform, league=league, config=fc
        )
        team = client.get_team()

        if args["read"]:
            return read_roster(team)

        service = RosterService(config=fc, league=league, team=team, client=client)
        controller = RosterController(service=service)

        match args:
            case args if args["add"] and args["claim"]:
                return add_player_claim(args, controller)
            case args if args["add"]:
                return add_player(args, controller)
            case args if args["drop"]:
                return drop_player(args, controller)
            case args if args["replace"] and args["claim"]:
                return replace_player_claim(args, controller)
            case args if args["replace"]:
                return replace_player(args, controller)
            case args if args["cancel"] and args["claim"]:
                return cancel_waiver_claim(args, controller)
