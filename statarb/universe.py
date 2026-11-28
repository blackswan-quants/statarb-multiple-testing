"""Step 1: point-in-time S&P 500 universe from github.com/fja05680/sp500."""

from __future__ import annotations

import io
import logging

import pandas as pd
import pandas_market_calendars as mcal
import requests

from statarb.config import END, ROOT, START, setup_logging
from statarb.errors import DataFetchError
from statarb.io import save, save_raw

log = logging.getLogger(__name__)

# Pinned commit, so the universe does not change silently when the repo is updated.
COMMIT = "a2430f2af0c79ddf0748e91de11bdeb1616ab5a7"
URL = (
    f"https://raw.githubusercontent.com/fja05680/sp500/{COMMIT}/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)


def fetch_snapshots() -> pd.DataFrame:
    """Download the components file and return one row per index change date.

    Returns
    -------
    pd.DataFrame
        Indexed by ``date`` with a ``tickers`` column holding a sorted list of symbols.

    Raises
    ------
    DataFetchError
        If GitHub does not return the file.
    """
    resp = requests.get(URL, timeout=60)
    if resp.status_code != 200:
        raise DataFetchError(f"{URL} -> HTTP {resp.status_code}")
    save_raw(resp.content, f"fja05680/components_{COMMIT[:8]}.csv", URL)
    raw = pd.read_csv(io.BytesIO(resp.content), parse_dates=["date"])
    raw["tickers"] = raw["tickers"].str.split(",").map(sorted)
    return raw.set_index("date").sort_index()


def trading_days(start: str = START, end: str = END) -> pd.DatetimeIndex:
    """Return NYSE trading days between ``start`` and ``end`` (inclusive)."""
    sched = mcal.get_calendar("NYSE").schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(sched.index, name="date")


def build_membership(snapshots: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Expand change-date snapshots to one row per (trading day, ticker).

    Parameters
    ----------
    snapshots : pd.DataFrame
        Output of `fetch_snapshots`.
    days : pd.DatetimeIndex
        Trading days to cover.

    Returns
    -------
    pd.DataFrame
        Columns ``date``, ``ticker``.

    Notes
    -----
    Each day takes the latest snapshot dated on or before it, so composition is carried forward between
    change dates and a change is effective from its own date. The first day needs a snapshot before it.
    """
    assert snapshots.index[0] <= days[0], "no snapshot on or before the first trading day"
    daily = snapshots["tickers"].reindex(days, method="ffill")
    return daily.explode().rename("ticker").reset_index()


def membership_intervals(membership: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Collapse daily membership into contiguous (ticker, start, end) intervals.

    A ticker that leaves and later re-enters the index gets one row per stay.
    """
    m = membership.assign(i=days.get_indexer(pd.DatetimeIndex(membership["date"])))
    m = m.sort_values(["ticker", "i"])
    m["stay"] = (m.groupby("ticker")["i"].diff() != 1).cumsum()
    out = m.groupby(["ticker", "stay"])["date"].agg(start="min", end="max")
    return out.reset_index()[["ticker", "start", "end"]]


def apply_fixes(membership: pd.DataFrame, days: pd.DatetimeIndex, fixes: pd.DataFrame) -> pd.DataFrame:
    """Add or remove hand-checked (ticker, start..end) spans from ``reference/membership_fixes.csv``.

    Notes
    -----
    The index file dropped the ``-YYYYMM`` suffix of dead companies, so where an old and a new company
    shared a symbol on the same day one of them vanished (e.g. old Allergan vs Watson/Actavis, both AGN).
    The suffixed label is added back; it matches the label used by sp500-data.
    """
    m = membership
    for ticker, start, end, action in zip(
        fixes["ticker"], fixes["start"], fixes["end"], fixes["action"], strict=True
    ):
        span = days[(days >= start) & (days <= end)]
        if action == "add":
            m = pd.concat([m, pd.DataFrame({"date": span, "ticker": ticker})])
        else:
            m = m[~((m["ticker"] == ticker) & m["date"].isin(span))]
    assert not m.duplicated(["date", "ticker"]).any(), "a fix adds a name that is already there"
    return m.sort_values(["date", "ticker"]).reset_index(drop=True)


def main() -> None:
    """Build and save membership and intervals for the project window."""
    setup_logging()
    days = trading_days()
    fixes = pd.read_csv(ROOT / "reference" / "membership_fixes.csv", parse_dates=["start", "end"])
    membership = apply_fixes(build_membership(fetch_snapshots(), days), days, fixes)
    intervals = membership_intervals(membership, days)
    save(membership, "membership")
    save(intervals, "membership_intervals")
    per_day = membership.groupby("date").size()
    log.info(
        "%d trading days, %d distinct tickers, %d stays; names per day min %d / median %d / max %d",
        len(days),
        intervals["ticker"].nunique(),
        len(intervals),
        per_day.min(),
        per_day.median(),
        per_day.max(),
    )


if __name__ == "__main__":
    main()
