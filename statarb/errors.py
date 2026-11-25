"""Domain exceptions."""


class DataFetchError(RuntimeError):
    """A remote source returned an error or unusable payload."""


class ReconciliationError(RuntimeError):
    """Two sources disagree beyond the agreed tolerance."""
