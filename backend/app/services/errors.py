class LfgError(Exception):
    """Base domain error."""


class LobbyNotFoundError(LfgError):
    pass


class LobbyNotJoinableError(LfgError):
    pass


class LobbyFullError(LobbyNotJoinableError):
    pass


class NotInLobbyError(LfgError):
    pass


class RankRangeError(LfgError):
    pass


class HostLobbyExistsError(LfgError):
    pass


class SearchBlockedError(LfgError):
    pass


class HostRecreateBlockedError(LfgError):
    pass


class PartyCodeInUseError(LfgError):
    pass


class LobbyEditError(LfgError):
    pass
