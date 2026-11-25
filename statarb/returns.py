"""Step 6: daily total returns from unadjusted prices, dividends and splits."""

from __future__ import annotations

import pandas as pd

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
