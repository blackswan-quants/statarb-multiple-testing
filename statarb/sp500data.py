"""Fill for delisted names: prices from github.com/Johnbrick123/sp500-data (mostly CRSP-derived).

The repository has no license and most delisted rows come from CRSP, so every row keeps its ``source``
label and the report must state where those prices come from.
"""

from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from statarb.config import END, START, setup_logging
from statarb.errors import DataFetchError
from statarb.io import save, save_raw

log = logging.getLogger(__name__)

TAG = "snapshot-2026-11"  # pinned release, the repo is rebuilt nightly
URL = f"https://github.com/Johnbrick123/sp500-data/releases/download/{TAG}/{{}}"


def _get(name: str) -> pd.DataFrame:
    url = URL.format(name)
    resp = requests.get(url, timeout=600)
    if resp.status_code != 200:
        raise DataFetchError(f"{url} -> HTTP {resp.status_code}")
    save_raw(resp.content, f"sp500data/{TAG}/{name}", url)
    return pd.read_parquet(io.BytesIO(resp.content))


def download() -> pd.DataFrame:
    """Download the release and keep prices on the days each label was an index member.

    Returns
    -------
    pd.DataFrame
        ``date, ticker, label, open, high, low, close, volume, dividends, stock_splits, source`` where
        ``ticker`` is the label without the ``-YYYYMM`` suffix the repo gives to dead companies.

    Raises
    ------
    DataFetchError
        If a release file cannot be downloaded.

    Notes
    -----
    Membership spans are [start, end). Restricting to them avoids picking up a recycled symbol's later
    company. ``close`` is as the source stores it: as traded for CRSP, Tiingo and WIKI, split-adjusted
    for Yahoo, so returns must be built per source (CRSP rows only have ``close``).
    """
    prices = _get("prices.parquet").rename(columns={"ticker": "label"})
    spans = _get("membership_intervals.parquet").rename(columns={"ticker": "label"})
    prices = prices[(prices["date"] >= START) & (prices["date"] <= END) & prices["close"].notna()]
    x = prices.merge(spans, on="label")
    x = x[(x["date"] >= x["start"]) & (x["end"].isna() | (x["date"] < x["end"]))]
    x = x.drop(columns=["start", "end", "adj_close"]).drop_duplicates(["date", "label"])
    x.insert(1, "ticker", x["label"].str.replace(r"-\d{6}$", "", regex=True))
    return x.sort_values(["ticker", "date"]).reset_index(drop=True)


def main() -> None:
    """Save member-day prices to ``data/interim/sp500data_prices.parquet``."""
    setup_logging()
    df = download()
    save(df, "sp500data_prices", stage="interim")
    log.info("rows by source:\n%s", df["source"].value_counts().to_string())


if __name__ == "__main__":
    main()
