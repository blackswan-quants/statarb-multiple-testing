"""Domain exceptions."""


class DataFetchError(RuntimeError):
    """A remote source returned an error or unusable payload."""


class InvalidPnLError(ValueError):
    """A daily PnL series passed to the trial logger does not follow ``docs/trials.md``."""
