"""Steps 6-7: daily total returns from unadjusted prices, dividends and splits, plus delistings."""

from __future__ import annotations

import logging

import pandas as pd

from statarb.config import ROOT, setup_logging
from statarb.io import load, save

log = logging.getLogger(__name__)

SERIES = ["ticker", "source", "symbol"]  # a return is only computed inside one source's series


def total_return(df: pd.DataFrame) -> pd.Series:
    """Compute r_t = (C_t + D_t) * k_t / C_{t-1} - 1 within each (ticker, source, symbol) series.

    Parameters
    ----------
    df : pd.DataFrame
        Rows with ``date, ticker, source, symbol, close, div_cash, split_factor`` (``split_factor`` = new
        shares per old share on the ex-date, 1 otherwise; ``div_cash`` per share on the ex-date).

    Returns
    -------
    pd.Series
        Total return aligned with ``df``; NaN on the first row of each series.

    Notes
    -----
    The previous close is the ticker's previous row, used only if it belongs to the same source and symbol.
    So the day after a switch has no return instead of a spurious jump between two price scales (e.g.
    split-adjusted Yahoo vs as-traded CRSP), and a one-day patch from another source never produces a
    two-day return.
    """
    d = df.sort_values(["ticker", "date"])
    key = d[SERIES]
    same = (key == key.shift()).all(axis=1)
    r = (d["close"] + d["div_cash"]) * d["split_factor"] / d["close"].shift().where(same) - 1
    return r.reindex(df.index)


def no_trade(p: pd.DataFrame) -> pd.Series:
    """Flag halted or stale days: zero volume, or a flat bar (high == low) at the previous close.

    Notes
    -----
    Such days carry a price but no real trade (e.g. SVB 2023-03-10..14 at 106.04). Their zero return is
    not a calm day, so volatility screens and fills must skip them. Rows without volume (CRSP) are only
    flagged by the flat-bar rule.
    """
    d = p.sort_values(["ticker", "date"])
    prev = d.groupby("ticker")["close"].shift()
    flag = (d["volume"] == 0) | ((d["high"] == d["low"]) & (d["close"] == prev))
    return flag.reindex(p.index)


def apply_delistings(r: pd.DataFrame, delistings: pd.DataFrame) -> pd.DataFrame:
    """Book each hand-listed delisting return on its date and drop the ticker's later rows.

    Parameters
    ----------
    r : pd.DataFrame
        Returns with ``date, ticker, ret, source``.
    delistings : pd.DataFrame
        ``ticker, date, ret`` from ``reference/delistings.csv``.

    Returns
    -------
    pd.DataFrame
        ``r`` with the delisting returns (``source = "delisting"``) and nothing after them.

    Notes
    -----
    Only firms whose price stops being real while they are still in the index need this (failures
    halted before removal). Cash acquisitions end at a close near the offer price and need nothing.
    """
    for ticker, day, ret in zip(delistings["ticker"], delistings["date"], delistings["ret"], strict=True):
        hit = (r["ticker"] == ticker) & (r["date"] == day)
        assert hit.sum() == 1, f"{ticker} has no row on {day:%Y-%m-%d}"
        r.loc[hit, ["ret", "source"]] = [ret, "delisting"]
        r = r[~((r["ticker"] == ticker) & (r["date"] > day))]
    return r


def main() -> None:
    """Save ``returns.parquet``: total returns with delisting returns and the no-trade flag."""
    setup_logging()
    p = load("prices")
    p["no_trade"] = no_trade(p)
    dl = pd.read_csv(ROOT / "reference" / "delistings.csv", parse_dates=["date"])
    r = apply_delistings(p[["date", "ticker", "ret", "source", "in_index", "no_trade"]].copy(), dl)
    save(r, "returns")
    idx = r[r["in_index"]]
    log.info(
        "%d rows; index days with a return %.2f%%, no-trade index days %d, delistings booked %d",
        len(r),
        100 * idx["ret"].notna().mean(),
        idx["no_trade"].sum(),
        (r["source"] == "delisting").sum(),
    )


if __name__ == "__main__":
    main()
