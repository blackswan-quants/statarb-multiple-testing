"""Steps 2-3: Tiingo ticker coverage check and EOD downloader."""

from __future__ import annotations

import io
import logging
import zipfile

import pandas as pd
import requests

from statarb.config import ETFS, ROOT, setup_logging
from statarb.errors import DataFetchError
from statarb.io import load, save, save_raw

log = logging.getLogger(__name__)

SUPPORTED_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
OVERRIDES = ROOT / "reference" / "ticker_overrides.csv"
TOLERANCE = pd.Timedelta(days=7)  # slack between index dates and Tiingo first/last price


def to_tiingo(ticker: str) -> str:
    """Map an index symbol to Tiingo's convention (share classes use '-': BRK.B -> BRK-B)."""
    return ticker.replace(".", "-")


def fetch_supported() -> pd.DataFrame:
    """Download Tiingo's list of supported tickers, keeping USD stocks and ETFs.

    Returns
    -------
    pd.DataFrame
        Columns ``ticker, exchange, assetType, startDate, endDate``; a symbol can appear more than once
        when Tiingo has reused it for different securities.

    Raises
    ------
    DataFetchError
        If the file cannot be downloaded.
    """
    resp = requests.get(SUPPORTED_URL, timeout=120)
    if resp.status_code != 200:
        raise DataFetchError(f"{SUPPORTED_URL} -> HTTP {resp.status_code}")
    save_raw(resp.content, "tiingo/supported_tickers.zip", SUPPORTED_URL)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        df = pd.read_csv(z.open("supported_tickers.csv"), parse_dates=["startDate", "endDate"])
    keep = (df["priceCurrency"] == "USD") & df["assetType"].isin(["Stock", "ETF"]) & df["startDate"].notna()
    return df.loc[keep].drop(columns="priceCurrency").reset_index(drop=True)


def load_overrides() -> pd.DataFrame:
    """Read the hand-reviewed map ``(ticker, start) -> tiingo`` from ``reference/ticker_overrides.csv``."""
    if not OVERRIDES.exists():
        return pd.DataFrame(columns=["ticker", "start", "tiingo", "note"])
    return pd.read_csv(OVERRIDES, parse_dates=["start"])


def check_coverage(intervals: pd.DataFrame, supported: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Compare each index stay with the Tiingo series that overlaps it most.

    Parameters
    ----------
    intervals : pd.DataFrame
        Index stays ``ticker, start, end`` (from `statarb.universe.membership_intervals`).
    supported : pd.DataFrame
        Output of `fetch_supported`.
    overrides : pd.DataFrame
        Tiingo symbol to use for given stays (from `load_overrides`).

    Returns
    -------
    pd.DataFrame
        One row per stay with the matched Tiingo dates and a ``status``: ``ok``, ``missing`` (no Tiingo
        series), ``starts_late`` (series begins after index entry: reused ticker or partial history) or
        ``ends_early`` (series stops while the stock is still in the index: delisting or rename).

    Notes
    -----
    ``starts_late`` is the plan's reused-ticker flag. It does not catch a reuse where Tiingo's series is
    older than the index stay (e.g. a symbol that passed to another company before 2006); those surface in
    the Tiingo vs WIKI reconciliation.
    """
    iv = intervals.merge(overrides[["ticker", "start", "tiingo"]], on=["ticker", "start"], how="left")
    iv["tiingo"] = iv["tiingo"].fillna(iv["ticker"].map(to_tiingo))
    m = iv.merge(supported, left_on="tiingo", right_on="ticker", how="left", suffixes=("", "_t"))
    overlap = m[["end", "endDate"]].min(axis=1) - m[["start", "startDate"]].max(axis=1)
    m["overlap_days"] = overlap.dt.days.fillna(-1)
    best = m.sort_values("overlap_days").drop_duplicates(["ticker", "start"], keep="last")
    best["status"] = "ok"
    best.loc[best["endDate"] < best["end"] - TOLERANCE, "status"] = "ends_early"
    best.loc[best["startDate"] > best["start"] + TOLERANCE, "status"] = "starts_late"
    best.loc[best["startDate"].isna() | (best["overlap_days"] < 0), "status"] = "missing"
    cols = ["ticker", "start", "end", "tiingo", "exchange", "startDate", "endDate", "status"]
    return best[cols].sort_values(["status", "ticker"]).reset_index(drop=True)


def suggest_renames(cov: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Propose a Tiingo symbol for uncovered stays that look like a ticker change.

    Parameters
    ----------
    cov : pd.DataFrame
        Output of `check_coverage`.
    overrides : pd.DataFrame
        Already reviewed stays; they are never suggested again.

    Returns
    -------
    pd.DataFrame
        Columns ``ticker, start, tiingo, note`` ready to append to the overrides file.

    Notes
    -----
    Before 2019 the index file carries Norgate's 2019 symbols back in time, so renames are invisible there
    and an exit/entry pair is a real replacement. From 2019 a rename shows up as the old symbol leaving and
    the new one entering within days: if exactly one such entrant has a Tiingo series already covering the
    old stay, it is taken to be the same company (Tiingo files renamed stocks under their latest symbol).
    It is still a guess (a failed company replaced by an older one looks the same), hence the review.
    """
    seen = set(zip(overrides["ticker"], overrides["start"], strict=True))
    todo = cov[(cov["status"] != "ok") & (cov["end"] >= "2019-01-01")]
    rows = []
    for ticker, start, end in zip(todo["ticker"], todo["start"], todo["end"], strict=True):
        entrants = cov[(cov["start"] > end) & (cov["start"] <= end + TOLERANCE)]
        same = entrants[entrants["startDate"] <= start + TOLERANCE]
        if len(same) == 1 and (ticker, start) not in seen:
            rows.append((ticker, start, same["tiingo"].iloc[0], "auto: rename"))
    return pd.DataFrame(rows, columns=["ticker", "start", "tiingo", "note"])


def main() -> None:
    """Run the coverage check, add rename suggestions to the overrides file, save the result."""
    setup_logging()
    supported = fetch_supported()
    intervals = load("membership_intervals")
    overrides = load_overrides()
    cov = check_coverage(intervals, supported, overrides)
    new = suggest_renames(cov, overrides)
    if len(new):
        overrides = pd.concat([overrides, new]).sort_values(["ticker", "start"])
        overrides.to_csv(OVERRIDES, index=False, date_format="%Y-%m-%d")
        log.info("%d rename suggestions added to %s (review them)", len(new), OVERRIDES.name)
        cov = check_coverage(intervals, supported, load_overrides())
    save(cov, "tiingo_coverage", stage="interim")
    log.info("index stays by status:\n%s", cov["status"].value_counts().to_string())
    etf = supported[supported["ticker"].isin(ETFS) & (supported["assetType"] == "ETF")]
    log.info("ETFs on Tiingo:\n%s", etf[["ticker", "startDate", "endDate"]].to_string(index=False))


if __name__ == "__main__":
    main()
