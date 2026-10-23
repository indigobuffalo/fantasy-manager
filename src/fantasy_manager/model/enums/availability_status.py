from enum import Enum


class AvailabilityStatus(Enum):
    """Stable per-player ownership status in a league's availability report.

    The values are the machine-readable strings that land in structured
    (``--output json|yaml``) output, so they're intentionally terse and stable
    even as the human-readable text rendering evolves.

    This describes an individual *player* result. A league that couldn't be read
    at all (stale/logged-out cookie, failed request) is represented by the
    league-level ``readable`` flag rather than a status here, since the failure
    isn't tied to any one query.
    """

    ROSTERED = "ROSTERED"
    FREE_AGENT = "FREE_AGENT"
    WAIVERS = "WAIVERS"
    # A query that matched a player row whose ownership cell couldn't be parsed.
    UNKNOWN = "UNKNOWN"
    # A query that returned no player rows at all.
    NO_MATCH = "NO_MATCH"
