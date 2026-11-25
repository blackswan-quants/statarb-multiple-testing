"""Step 4: Quandl WIKI prices (frozen March 2018) from the Kaggle mirror."""

from __future__ import annotations

import logging

import kagglehub
import pandas as pd
from dotenv import load_dotenv

from statarb.config import DATA, ROOT, START, setup_logging
from statarb.io import load, record_raw, save

log = logging.getLogger(__name__)

HANDLE = "marketneutral/quandl-wiki-prices-us-equites"
URL = f"https://www.kaggle.com/datasets/{HANDLE}"
COLUMNS = ["ticker", "date", "open", "high", "low", "close", "volume", "ex-dividend", "split_ratio"]


def to_wiki(ticker: str) -> str:
    """Map an index symbol to WIKI's convention (share classes use '_': BRK.B -> BRK_B)."""
    return ticker.replace(".", "_")


def download() -> pd.DataFrame:
    """Download WIKI_PRICES.csv into ``data/raw/wiki`` and return unadjusted prices from `START`.

    Returns
    -------
    pd.DataFrame
        Columns ``ticker, date, open, high, low, close, volume, div_cash, split_factor``.

    Notes
    -----
    Credentials come from ``.env`` (``KAGGLE_API_TOKEN`` or ``KAGGLE_USERNAME``/``KAGGLE_KEY``). The adj_*
    columns are dropped: returns are rebuilt from raw prices, dividends and splits (step 6). All tickers are
    kept, not only index members, because WIKI uses 2018 symbols and some index stays are matched by hand.
    """
    load_dotenv(ROOT / ".env")
    folder = kagglehub.dataset_download(HANDLE, output_dir=str(DATA / "raw" / "wiki"))
    path = next((DATA / "raw" / "wiki").glob("*.csv"))
    log.info("kaggle files in %s", folder)
    record_raw(path, URL)
    df = pd.read_csv(path, usecols=COLUMNS, engine="pyarrow")
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= START].rename(columns={"ex-dividend": "div_cash", "split_ratio": "split_factor"})
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def main() -> None:
    """Save WIKI prices from 2006 and log how many index stays they cover."""
    setup_logging()
    wiki = download()
    save(wiki, "wiki_prices", stage="interim")
    span = wiki.groupby("ticker")["date"].agg(first="min", last="max")
    cov = load("tiingo_coverage", stage="interim").assign(wiki=lambda d: d["ticker"].map(to_wiki))
    cov = cov.join(span, on="wiki")
    open_ = cov[cov["status"] != "ok"]
    log.info(
        "WIKI: %d tickers, %s -> %s; open Tiingo stays with a WIKI series: %d of %d",
        len(span),
        wiki["date"].min().date(),
        wiki["date"].max().date(),
        open_["first"].notna().sum(),
        len(open_),
    )


if __name__ == "__main__":
    main()
