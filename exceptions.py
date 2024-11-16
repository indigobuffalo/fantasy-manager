"""Module for custom exceptions"""


class YahooFantasyError(Exception):
    pass


class UserAbortError(YahooFantasyError):
    def __init__(self, message: str = "Aborting per user input"):
        self.message = message
        super().__init__(self.message)


class NotOnRosterError(YahooFantasyError):
    def __init__(self, player: str, message: str = "Player to drop not on roster"):
        self.player = player
        self.message = message
        super().__init__(self.message)


class AlreadyAddedError(YahooFantasyError):
    def __init__(self, player: str, message: str = "Already added player"):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Player "{self.player}" is already added to roster.'


class AlreadyPlayedError(YahooFantasyError):
    def __init__(self, player: str, message: str = "Player already played"):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'A player has already played today and is locked.'


class MaxAddsError(YahooFantasyError):
    def __init__(self, message: str = "All weekly adds have been used."):
        self.message = message
        super().__init__(self.message)


class UnintendedWaiverAddError(YahooFantasyError):
    def __init__(self, message: str = "Accidentally submitted waiver claim."):
        self.message = message
        super().__init__(self.message)


class FantasyAuthError(YahooFantasyError):
    def __init__(self, message: str = "You're not logged in!"):
        self.message = message
        super().__init__(self.message)


class OnWaiversError(YahooFantasyError):
    def __init__(self, player: str, message: str = "Player on waivers!"):
        self.player = player
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Player "{self.player}" is still on waivers.'


class FantasyUnknownError(YahooFantasyError):
    def __init__(self, player: str, message: str = "Something went wrong."):
        self.player = player
        self.message = message
        super().__init__(self.message)


class InvalidLeagueError(YahooFantasyError):

    def __init__(self, league_id: str):
        self.league_id = league_id
        super().__init__(f"Unknown league: {self.league_id}")
