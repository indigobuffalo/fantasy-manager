"""Module for custom exceptions"""


class FantasyManagerError(Exception):
    pass


class FantasyManagerSoftError(FantasyManagerError):
    """Error due to bad inputs"""

    def __new__(cls, *args, **kwargs):
        if cls is FantasyManagerSoftError:
            raise TypeError(
                "FantasyManagerSoftError must be inherited; it cannot be thrown directly"
            )
        raise FantasyManagerError.__new__(cls, *args, **kwargs)


class UserAbortError(FantasyManagerError):
    def __init__(self, message: str = "Aborting per user input"):
        self.message = message
        super().__init__(self.message)


class InputError(FantasyManagerError):
    def __init__(self, message: str = "Invalid value"):
        self.message = message
        super().__init__(self.message)


class TimeoutExceededError(FantasyManagerError):
    def __init__(self, message: str = "Operation has timed out."):
        self.message = message
        super().__init__(self.message)


class NotOnRosterError(FantasyManagerError):
    def __init__(self, player: str, message: str = "Player to drop not on roster"):
        self.player = player
        self.message = message
        super().__init__(self.message)


class OnAnotherTeamError(FantasyManagerError):
    def __init__(self, player: str, message: str = "Player to add is on another team."):
        self.player = player
        self.message = message
        super().__init__(self.message)


class AlreadyAddedError(FantasyManagerError):
    def __init__(self, player: str, message: str = "Already added player."):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Player "{self.player}" is already added to roster.'


class InvalidRosterPosition(FantasyManagerError):
    def __init__(
        self, player: str, message: str = "Player is in an invalid roster position."
    ):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Player "{self.player}" is in an invalid roster position:\n\n{self.message}'


class AlreadyPlayedError(FantasyManagerError):
    def __init__(self, player: str, message: str = "Player already played"):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"A player has already played today and is locked."


class MaxAddsError(FantasyManagerError):
    def __init__(self, message: str = "All weekly adds have been used."):
        self.message = message
        super().__init__(self.message)


class UnintendedWaiverAddError(FantasyManagerError):
    def __init__(self, message: str = "Accidentally submitted waiver claim."):
        self.message = message
        super().__init__(self.message)


class FantasyAuthError(FantasyManagerError):
    def __init__(self, message: str = "You're not logged in!"):
        self.message = message
        super().__init__(self.message)


class OnWaiversError(FantasyManagerError):
    def __init__(self, player: str, message: str = "Player on waivers!"):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Player "{self.player}" is still on waivers.'


class FantasyUnknownError(FantasyManagerError):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class InvalidLeagueError(FantasyManagerError):
    def __init__(self, league_id: str):
        self.league_id = league_id
        super().__init__(f"Unknown league: {self.league_id}")
