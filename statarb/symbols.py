"""Map index symbols to Tiingo / WIKI symbols by date and measure how much of the universe each covers."""

from __future__ import annotations

import logging

import pandas as pd

from statarb.config import ROOT, setup_logging
from statarb.io import load, save

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


def segments(m: pd.DataFrame) -> pd.DataFrame:
    """Collapse daily rows into runs with the same ticker and source symbols, with covered-day counts.

    Notes
    -----
    A new run starts when the ticker, either source symbol changes, or the gap from the previous row is more
    than 7 calendar days (the stock left the index and came back).
    """
    m = m.sort_values(["ticker", "date"])
    keys = m[["ticker", "tiingo", "wiki"]]
    new = (keys != keys.shift()).any(axis=1) | (m["date"].diff() > pd.Timedelta(days=7))
    g = m.assign(any=m["in_tiingo"] | m["in_wiki"]).groupby(new.cumsum())
    out = g.agg(
        ticker=("ticker", "first"),
        tiingo=("tiingo", "first"),
        wiki=("wiki", "first"),
        start=("date", "min"),
        end=("date", "max"),
        days=("date", "size"),
        tiingo_days=("in_tiingo", "sum"),
        wiki_days=("in_wiki", "sum"),
        any_days=("any", "sum"),
    )
    return out.assign(missing=out["days"] - out["any_days"]).reset_index(drop=True)


def main() -> None:
    """Map symbols, flag coverage per day, save daily map and per-segment summary."""
    setup_logging()
    sup = load("tiingo_supported", stage="interim")
    tiingo_spans = sup.rename(columns={"ticker": "symbol", "startDate": "first", "endDate": "last"})
    wiki = load("wiki_prices", stage="interim")
    wiki_spans = wiki.groupby("ticker")["date"].agg(first="min", last="max").rename_axis("symbol")

    m = map_symbols(load("membership"), load_overrides())
    m["in_tiingo"] = covered(m, tiingo_spans, "tiingo")
    m["in_wiki"] = covered(m, wiki_spans.reset_index(), "wiki")
    seg = segments(m)
    save(m, "membership_symbols", stage="interim")
    save(seg, "symbol_coverage", stage="interim")
    log.info(
        "stock-days %d: Tiingo %.2f%%, WIKI %.2f%%, either %.2f%%; missing %d in %d segments",
        len(m),
        100 * m["in_tiingo"].mean(),
        100 * m["in_wiki"].mean(),
        100 * (m["in_tiingo"] | m["in_wiki"]).mean(),
        seg["missing"].sum(),
        (seg["missing"] > 0).sum(),
    )


if __name__ == "__main__":
    main()
