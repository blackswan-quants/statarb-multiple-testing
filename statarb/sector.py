"""Step 8: sector proxy = the sector ETF with the highest R² on the past 252 daily returns (up to t-1)."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

from statarb.config import END, SECTOR_ETFS, setup_logging
from statarb.io import load, save
from statarb.returns import total_return

log = logging.getLogger(__name__)

WINDOW = 252
MIN_OBS = 126  # a stock needs half a window of returns to get a sector


def etf_returns() -> pd.DataFrame:
    """Daily total returns of the sector ETFs and SPY from the Tiingo download, wide (date x ETF)."""
    t = load("tiingo_prices", stage="interim").rename(columns={"symbol": "ticker"})
    t = t[t["ticker"].isin([*SECTOR_ETFS, "SPY"])].assign(source="tiingo", symbol="")
    t["ret"] = total_return(t)
    return t.pivot(index="date", columns="ticker", values="ret")


def assign_sectors(stocks: pd.DataFrame, etfs: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Give each stock, on each day up to ``as_of``, the sector ETF that best explains its past returns.

    Parameters
    ----------
    stocks : pd.DataFrame
        Daily returns, wide (date x ticker).
    etfs : pd.DataFrame
        Daily ETF returns, wide (date x ETF); only `SECTOR_ETFS` columns are used.
    as_of : date
        Last day to classify; inputs after it are dropped first.

    Returns
    -------
    pd.DataFrame
        Long ``date, ticker, sector, r2``; days without enough history are left out.

    Notes
    -----
    R² of a one-factor regression is the squared correlation. Each window ends at t-1 (``shift(1)``), so
    the sector on day t uses no information from day t. An ETF competes only once it has a full window,
    so XLRE (2015) and XLC (2018) enter by themselves a year after launch.
    """
    stocks = stocks.loc[: pd.Timestamp(as_of)]
    etfs = etfs.loc[: pd.Timestamp(as_of)].reindex(stocks.index)
    r2 = []
    for e in SECTOR_ETFS:
        c = stocks.rolling(WINDOW, min_periods=MIN_OBS).corr(etfs[e]) ** 2
        full = etfs[e].rolling(WINDOW).count() == WINDOW
        r2.append(c.where(full, axis=0).shift(1).to_numpy())
    cube = np.stack(r2)  # (etf, date, ticker)
    ok = ~np.isnan(cube).all(axis=0)
    best = np.nanargmax(np.where(np.isnan(cube), -1.0, cube), axis=0)
    rows, cols = np.nonzero(ok)
    out = pd.DataFrame(
        {
            "date": stocks.index[rows],
            "ticker": stocks.columns[cols],
            "sector": np.array(SECTOR_ETFS)[best[rows, cols]],
            "r2": cube[best[rows, cols], rows, cols],
        }
    )
    assert out["date"].max() <= pd.Timestamp(as_of)
    return out


def main() -> None:
    """Save ``sector.parquet`` for index days and log the sector mix."""
    setup_logging()
    r = load("returns")
    r = r[~r["no_trade"]]  # a stale zero is not a return
    stocks = r.pivot(index="date", columns="ticker", values="ret")
    sec = assign_sectors(stocks, etf_returns(), date.fromisoformat(END))
    sec = sec.merge(r.loc[r["in_index"], ["date", "ticker"]], on=["date", "ticker"])
    save(sec, "sector")
    last = sec[sec["date"] == sec["date"].max()]
    log.info("index days with a sector: %d; median R² %.2f", len(sec), sec["r2"].median())
    log.info("sector mix on %s:\n%s", last["date"].iloc[0].date(), last["sector"].value_counts().to_string())


if __name__ == "__main__":
    main()
