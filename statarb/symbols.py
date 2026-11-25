"""Map index symbols to Tiingo / WIKI symbols by date and measure how much of the universe each covers."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from statarb.config import HISTORY_DAYS, ROOT, setup_logging
from statarb.io import load, save
from statarb.universe import trading_days

log = logging.getLogger(__name__)

OVERRIDES = ROOT / "reference" / "ticker_overrides.csv"


def load_overrides() -> pd.DataFrame:
    """Read the hand-made map ``(ticker, start, end) -> tiingo, wiki`` (``reference/ticker_overrides.csv``).

    Notes
    -----
    A blank ``tiingo`` or ``wiki`` cell means "same as the index symbol", ``-`` means "not in this source"
    (used when the source has the symbol but for another company). Rows of one ticker must not overlap;
    two rows on the same stay split it between two securities (e.g. old and new Fox).
    """
    return pd.read_csv(OVERRIDES, parse_dates=["start", "end"], dtype={"tiingo": str, "wiki": str})


def map_symbols(membership: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Attach the Tiingo and WIKI symbol to each (date, ticker) membership row.

    Parameters
    ----------
    membership : pd.DataFrame
        Daily ``date, ticker`` rows.
    overrides : pd.DataFrame
        Output of `load_overrides`.

    Returns
    -------
    pd.DataFrame
        ``membership`` plus ``tiingo`` and ``wiki`` columns.

    Notes
    -----
    Without an override the symbol is converted to each source's share-class convention:
    BRK.B -> BRK-B (Tiingo), BRK_B (WIKI).
    """
    hit = membership.merge(overrides, on="ticker")
    hit = hit[(hit["date"] >= hit["start"]) & (hit["date"] <= hit["end"])]
    assert not hit.duplicated(["date", "ticker"]).any(), "overlapping override rows"
    m = membership.merge(hit[["date", "ticker", "tiingo", "wiki"]], on=["date", "ticker"], how="left")
    m["tiingo"] = m["tiingo"].fillna(m["ticker"].str.replace(".", "-"))
    m["wiki"] = m["wiki"].fillna(m["ticker"].str.replace(".", "_"))
    return m


def covered(m: pd.DataFrame, spans: pd.DataFrame, col: str) -> pd.Series:
    """Flag rows whose date falls inside a ``first``-``last`` span of the source symbol in ``col``."""
    x = m[["date", col]].reset_index().merge(spans, left_on=col, right_on="symbol")
    inside = x.loc[(x["date"] >= x["first"]) & (x["date"] <= x["last"]), "index"]
    return pd.Series(m.index.isin(inside), index=m.index)


def runs(m: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Collapse daily membership rows into runs with the same ticker and source symbols.

    Notes
    -----
    A new run starts when the ticker or a source symbol changes, or a trading day is skipped (the stock
    left the index and came back).
    """
    m = m.sort_values(["ticker", "date"])
    keys = m[["ticker", "tiingo", "wiki"]]
    skip = np.diff(days.get_indexer(pd.DatetimeIndex(m["date"])), prepend=-1) != 1
    new = (keys != keys.shift()).any(axis=1) | skip
    out = m.groupby(new.cumsum()).agg(
        ticker=("ticker", "first"),
        tiingo=("tiingo", "first"),
        wiki=("wiki", "first"),
        start=("date", "min"),
        end=("date", "max"),
    )
    return out.reset_index(drop=True).rename_axis("run").reset_index()


def extend(runs: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Expand runs to daily rows from `HISTORY_DAYS` before entry to exit, flagging the index days.

    Parameters
    ----------
    runs : pd.DataFrame
        Output of `runs`.
    days : pd.DatetimeIndex
        Trading days of the project window.

    Returns
    -------
    pd.DataFrame
        ``date, ticker, run, tiingo, wiki, in_index``: one row per (date, ticker).

    Notes
    -----
    The pre-entry history feeds the rolling windows (sector R², PCA) on the first days in the index. Where a
    history day overlaps another run of the same ticker, the run that is in the index that day wins.
    """
    i0 = days.searchsorted(runs["start"] - pd.Timedelta(days=HISTORY_DAYS))
    i1 = days.searchsorted(runs["end"], side="right")
    n = i1 - i0
    pos = np.repeat(i0, n) + np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    g = runs.loc[runs.index.repeat(n)].reset_index(drop=True)
    g.insert(0, "date", days[pos])
    g["in_index"] = g["date"] >= g["start"]
    g = g.sort_values("in_index", ascending=False).drop_duplicates(["date", "ticker"])
    return g.drop(columns=["start", "end"]).sort_values(["ticker", "date"]).reset_index(drop=True)


def main() -> None:
    """Build the symbol grid with per-source coverage flags and log coverage on index days."""
    setup_logging()
    sup = load("tiingo_supported", stage="interim")
    tiingo_spans = sup.rename(columns={"ticker": "symbol", "startDate": "first", "endDate": "last"})
    wiki = load("wiki_prices", stage="interim")
    wiki_spans = wiki.groupby("ticker")["date"].agg(first="min", last="max").rename_axis("symbol")
    sp = load("sp500data_prices", stage="interim")[["date", "ticker"]].assign(hit=True)

    days = trading_days()
    g = extend(runs(map_symbols(load("membership"), load_overrides()), days), days)
    g["in_tiingo"] = covered(g, tiingo_spans, "tiingo")
    g["in_wiki"] = covered(g, wiki_spans.reset_index(), "wiki")
    g["in_sp500data"] = g.merge(sp, on=["date", "ticker"], how="left")["hit"].notna().to_numpy()
    save(g, "universe_symbols", stage="interim")

    idx = g[g["in_index"]]
    any_ = idx["in_tiingo"] | idx["in_wiki"] | idx["in_sp500data"]
    log.info(
        "%d rows (%d index days): Tiingo %.2f%%, +WIKI %.2f%%, +sp500-data %.2f%%; %d index days missing",
        len(g),
        len(idx),
        100 * idx["in_tiingo"].mean(),
        100 * (idx["in_tiingo"] | idx["in_wiki"]).mean(),
        100 * any_.mean(),
        (~any_).sum(),
    )


if __name__ == "__main__":
    main()
