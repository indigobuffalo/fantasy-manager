from enum import Enum


class AvailabilityStatus(Enum):
    """Stable ownership status for a player in a league's availability report.

    The values are the machine-readable strings that land in structured
    (``--output json|yaml``) output, so they're intentionally terse and stable
    even as the human-readable text rendering evolves.
    """

    ROSTERED = "ROSTERED"
    FREE_AGENT = "FREE_AGENT"
    WAIVERS = "WAIVERS"
    # A query that matched a player row whose ownership cell couldn't be parsed.
    UNKNOWN = "UNKNOWN"
    # A query that returned no player rows at all.
    NO_MATCH = "NO_MATCH"
    # The league itself couldn't be read (stale/logged-out cookie, failed request).
    UNREADABLE = "UNREADABLE"
