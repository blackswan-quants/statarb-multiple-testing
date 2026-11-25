"""Tiingo: list of supported tickers (step 2) and EOD downloader (step 3)."""

from __future__ import annotations

import io
import logging
import zipfile

import pandas as pd
import requests

from statarb.config import ETFS, setup_logging
from statarb.errors import DataFetchError
from statarb.io import save, save_raw

log = logging.getLogger(__name__)

SUPPORTED_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"


def fetch_supported() -> pd.DataFrame:
    """Download Tiingo's list of supported tickers, keeping USD stocks and ETFs.

    Returns
    -------
    pd.DataFrame
        Columns ``ticker, exchange, assetType, startDate, endDate``. A symbol can appear more than once
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


def main() -> None:
    """Save the supported-tickers table to ``data/interim/tiingo_supported.parquet``."""
    setup_logging()
    supported = fetch_supported()
    save(supported, "tiingo_supported", stage="interim")
    etf = supported[supported["ticker"].isin(ETFS) & (supported["assetType"] == "ETF")]
    log.info("ETFs on Tiingo:\n%s", etf[["ticker", "startDate", "endDate"]].to_string(index=False))


if __name__ == "__main__":
    main()
