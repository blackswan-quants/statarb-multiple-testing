"""Fill for delisted names: prices from github.com/Johnbrick123/sp500-data (mostly CRSP-derived).

The repository has no license and most delisted rows come from CRSP, so every row keeps its ``source``
label and the report must state where those prices come from.
"""

from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from statarb.config import DATA, END, HISTORY_DAYS, START, setup_logging
from statarb.errors import DataFetchError
from statarb.io import load, save, save_raw

log = logging.getLogger(__name__)

TAG = "snapshot-2026-11"  # pinned release, the repo is rebuilt nightly
URL = f"https://github.com/Johnbrick123/sp500-data/releases/download/{TAG}/{{}}"


def _get(name: str) -> pd.DataFrame:
    raw = DATA / "raw" / "sp500data" / TAG / name
    if raw.exists():  # pinned release: the raw copy is the same file
        return pd.read_parquet(raw)
    url = URL.format(name)
    resp = requests.get(url, timeout=600)
    if resp.status_code != 200:
        raise DataFetchError(f"{url} -> HTTP {resp.status_code}")
    save_raw(resp.content, f"sp500data/{TAG}/{name}", url)
    return pd.read_parquet(io.BytesIO(resp.content))


def download(index_tickers: set[str]) -> pd.DataFrame:
    """Download the release and keep prices from `HISTORY_DAYS` before each label's index entry to its exit.

    Returns
    -------
    pd.DataFrame
        ``date, ticker, label, open, high, low, close, volume, dividends, stock_splits, source, member``
        where ``ticker`` is the label without the ``-YYYYMM`` suffix the repo gives to dead companies and
        ``member`` flags days inside the label's index span.

    Raises
    ------
    DataFetchError
        If a release file cannot be downloaded.

    Notes
    -----
    Membership spans are [start, end). Cutting to them (plus the pre-entry history) avoids picking up a
    recycled symbol's other company; when two labels share a base ticker on a day, the member one wins.
    Suffixed labels that are themselves index tickers (added back in `statarb.universe`) are kept as is.
    ``close`` is as the source stores it: as traded for CRSP, Tiingo and WIKI, split-adjusted for Yahoo,
    so returns must be built per source (CRSP rows only have ``close``).
    """
    prices = _get("prices.parquet").rename(columns={"ticker": "label"})
    spans = _get("membership_intervals.parquet").rename(columns={"ticker": "label"})
    prices = prices[(prices["date"] >= START) & (prices["date"] <= END) & prices["close"].notna()]
    x = prices.merge(spans, on="label")
    first = x["start"] - pd.Timedelta(days=HISTORY_DAYS)
    x = x[(x["date"] >= first) & (x["end"].isna() | (x["date"] < x["end"]))]
    x["member"] = x["date"] >= x["start"]
    base = x["label"].str.replace(r"-\d{6}$", "", regex=True)
    x.insert(1, "ticker", base.where(~x["label"].isin(index_tickers), x["label"]))
    x = x.sort_values("member", ascending=False).drop_duplicates(["date", "ticker"])
    return (
        x.drop(columns=["start", "end", "adj_close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    )


def main() -> None:
    """Save member-day prices to ``data/interim/sp500data_prices.parquet``."""
    setup_logging()
    df = download(set(load("membership")["ticker"]))
    save(df, "sp500data_prices", stage="interim")
    log.info("rows by source:\n%s", df["source"].value_counts().to_string())


if __name__ == "__main__":
    main()
