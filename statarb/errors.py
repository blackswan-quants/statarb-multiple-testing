"""Domain exceptions."""


class DataFetchError(RuntimeError):
    """A remote source returned an error or unusable payload."""
