"""Step 9: bid-ask spread proxy of Abdi and Ranaldo (2017) from daily close, high and low."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

from statarb.config import END, setup_logging
from statarb.io import load, save
from statarb.returns import SERIES, no_trade

log = logging.getLogger(__name__)

WINDOW = 21
MIN_OBS = 15


def ar_terms(p: pd.DataFrame) -> pd.Series:
    """Daily Abdi-Ranaldo terms (c_t - eta_t) * (c_t - eta_{t+1}) inside each source series.

    Parameters
    ----------
    p : pd.DataFrame
        Prices with ``date, ticker, source, symbol, high, low, close, split_factor``.

    Returns
    -------
    pd.Series
        Aligned with ``p``; NaN where a bar is invalid, the next bar is missing or comes from another series.

    Notes
    -----
    c = log close, eta = mid-range (log high + log low) / 2. On a split day eta_{t+1} is put back on the
    pre-split scale (+ log k_{t+1}), otherwise the split would look like a huge spread.
    """
    d = p.sort_values(["ticker", "date"])
    bad = (d["high"] < d["low"]) | (d["close"] > d["high"]) | (d["close"] < d["low"]) | (d["low"] <= 0)
    c = np.log(d["close"]).where(~bad)
    eta = ((np.log(d["high"]) + np.log(d["low"])) / 2).where(~bad)
    key = d[SERIES]
    same_next = (key == key.shift(-1)).all(axis=1)
    eta_next = (eta.shift(-1) + np.log(d["split_factor"].shift(-1))).where(same_next)
    terms: pd.Series = (c - eta) * (c - eta_next)
    return terms.reindex(p.index)


def abdi_ranaldo(terms: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Estimate the spread usable on day t from prices up to t-1 (rolling window).

    Parameters
    ----------
    terms : pd.DataFrame
        Wide (date x ticker) output of `ar_terms`.
    as_of : date
        Last day to estimate; later inputs are dropped first.

    Returns
    -------
    pd.DataFrame
        Wide proportional spread S = 2 * sqrt(max(mean term, 0)).

    Notes
    -----
    The term dated s needs the bar of s+1, so it is known at the end of s+1. Using data up to t-1 means
    terms up to t-2: the rolling mean is shifted by two rows.
    """
    terms = terms.loc[: pd.Timestamp(as_of)]
    mean = terms.rolling(WINDOW, min_periods=MIN_OBS).mean().shift(2)
    return 2 * mean.clip(lower=0).pow(0.5)


def main() -> None:
    """Save ``spread.parquet`` for index days: AR estimate, else same-day sector or market median."""
    setup_logging()
    p = load("prices")
    p = p[~no_trade(p)].copy()
    p["term"] = ar_terms(p)
    wide = abdi_ranaldo(p.pivot(index="date", columns="ticker", values="term"), date.fromisoformat(END))
    s = wide.reset_index().melt(id_vars="date", var_name="ticker", value_name="spread").dropna()

    idx = load("returns").query("in_index")[["date", "ticker"]]
    out = idx.merge(s, on=["date", "ticker"], how="left")
    out = out.merge(load("sector"), on=["date", "ticker"], how="left")
    ar = out["spread"]
    sector_med = out.groupby(["date", "sector"])["spread"].transform("median")
    market_med = out.groupby("date")["spread"].transform("median")
    out["spread"] = ar.fillna(sector_med).fillna(market_med)
    out["spread_source"] = np.select(
        [ar.notna(), sector_med.notna(), market_med.notna()], ["ar", "sector_median", "market_median"], "none"
    )
    out = out[["date", "ticker", "spread", "spread_source"]]
    save(out, "spread")
    ar = out[out["spread_source"] == "ar"]["spread"]
    log.info(
        "index days %d: AR %.1f%%, filled %s; AR spread median %.1f bps, p90 %.1f bps",
        len(out),
        100 * len(ar) / len(out),
        out["spread_source"].value_counts().drop("ar", errors="ignore").to_dict(),
        1e4 * ar.median(),
        1e4 * ar.quantile(0.9),
    )


if __name__ == "__main__":
    main()
