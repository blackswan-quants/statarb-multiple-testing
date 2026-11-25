"""Step 5: one price row per (date, ticker) by source priority, plus cross-source return checks."""

from __future__ import annotations

import logging

import pandas as pd

from statarb.config import setup_logging
from statarb.io import load, save
from statarb.returns import total_return

log = logging.getLogger(__name__)

THRESHOLD = 0.01  # daily return gap that sends a day to manual review (fixed before looking at the data)
COLS = [
    "date",
    "ticker",
    "symbol",
    "source",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "div_cash",
    "split_factor",
]


def wiki_rows(grid: pd.DataFrame, wiki: pd.DataFrame) -> pd.DataFrame:
    """Attach WIKI prices to the symbol grid through each day's WIKI symbol."""
    x = grid[["date", "ticker", "wiki"]].merge(wiki.rename(columns={"ticker": "wiki"}), on=["date", "wiki"])
    return x.rename(columns={"wiki": "symbol"}).assign(source="wiki")[COLS]


def sp500data_rows(grid: pd.DataFrame, sp: pd.DataFrame) -> pd.DataFrame:
    """Attach sp500-data prices to the grid; their symbols already match the index file.

    Notes
    -----
    Yahoo closes there are split-adjusted, so their split factor is set to 1; the other sources are as
    traded and keep the recorded split (0 there means no split). The original source is kept after the
    ``sp500data:`` prefix.
    """
    x = grid[["date", "ticker"]].merge(sp, on=["date", "ticker"])
    yahoo = x["source"].str.startswith("yahoo")
    x["split_factor"] = x["stock_splits"].where((x["stock_splits"] > 0) & ~yahoo, 1.0)
    x["source"] = "sp500data:" + x["source"]
    return x.rename(columns={"dividends": "div_cash", "label": "symbol"})[COLS]


def compare(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare daily returns of two sources on their common (date, ticker) rows.

    Returns
    -------
    tuple of pd.DataFrame
        Per-ticker summary (``days, corr, max_abs_diff, days_over``) and the days whose return gap
        exceeds `THRESHOLD`, for manual review.
    """
    x = a.merge(b, on=["date", "ticker"], suffixes=("_a", "_b")).dropna(subset=["ret_a", "ret_b"])
    x["diff"] = x["ret_a"] - x["ret_b"]
    g = x.groupby("ticker")
    summary = pd.DataFrame(
        {
            "days": g.size(),
            "corr": g.apply(lambda d: d["ret_a"].corr(d["ret_b"])),
            "max_abs_diff": g["diff"].apply(lambda s: s.abs().max()),
            "days_over": g["diff"].apply(lambda s: (s.abs() > THRESHOLD).sum()),
        }
    )
    flagged = x.loc[x["diff"].abs() > THRESHOLD, ["date", "ticker", "source_b", "ret_a", "ret_b", "diff"]]
    return summary.sort_values("days_over", ascending=False), flagged.reset_index(drop=True)


def assemble(grid: pd.DataFrame, *sources: pd.DataFrame) -> pd.DataFrame:
    """Keep, for each (date, ticker) of the grid, the row of the first source that has it.

    Parameters
    ----------
    grid : pd.DataFrame
        Symbol grid (``date, ticker, in_index``).
    *sources : pd.DataFrame
        Price rows with a ``ret`` column, in priority order.

    Returns
    -------
    pd.DataFrame
        ``COLS + ret + in_index``, one row per covered (date, ticker).
    """
    rows = pd.concat([s.assign(rank=i) for i, s in enumerate(sources)])
    rows = rows.sort_values("rank").drop_duplicates(["date", "ticker"]).drop(columns="rank")
    out = rows.merge(grid[["date", "ticker", "in_index"]], on=["date", "ticker"])
    assert len(out) == len(rows), "price rows outside the symbol grid"
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def main() -> None:
    """Build ``prices.parquet`` (WIKI > sp500-data until Tiingo is downloaded) and the WIKI cross-check."""
    setup_logging()
    grid = load("universe_symbols", stage="interim")
    wiki = wiki_rows(grid, load("wiki_prices", stage="interim"))
    sp = sp500data_rows(grid, load("sp500data_prices", stage="interim"))
    wiki["ret"], sp["ret"] = total_return(wiki), total_return(sp)

    other = sp[sp["source"] != "sp500data:wiki"]  # their WIKI rows are the same file
    summary, flagged = compare(wiki, other)
    save(summary.reset_index(), "recon_wiki_vs_sp500data", stage="interim")
    save(flagged, "recon_wiki_vs_sp500data_flagged", stage="interim")
    log.info(
        "WIKI vs sp500-data: %d tickers, %d common days, median corr %.4f, %d days over %.0f%% in %d tickers",
        len(summary),
        summary["days"].sum(),
        summary["corr"].median(),
        len(flagged),
        100 * THRESHOLD,
        (summary["days_over"] > 0).sum(),
    )

    prices = assemble(grid, wiki, sp)
    save(prices, "prices")
    idx = prices[prices["in_index"]]
    log.info("index days by source:\n%s", idx["source"].value_counts().to_string())


if __name__ == "__main__":
    main()
