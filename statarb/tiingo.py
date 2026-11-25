"""Tiingo: list of supported tickers (step 2) and EOD downloader (step 3)."""

from __future__ import annotations

import io
import json
import logging
import sys
import zipfile

import pandas as pd
import requests
from rich.progress import Progress

from statarb.config import DATA, END, ETFS, START, Settings, setup_logging
from statarb.errors import DataFetchError
from statarb.io import load, save, save_raw

log = logging.getLogger(__name__)

SUPPORTED_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
PRICES_URL = "https://api.tiingo.com/tiingo/daily/{}/prices"


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


def download(symbols: list[str], key: str) -> None:
    """Save Tiingo EOD responses as-is to ``data/raw/tiingo/prices/<symbol>.json``, skipping files on disk.

    Parameters
    ----------
    symbols : list of str
        Tiingo symbols.
    key : str
        API token.

    Raises
    ------
    DataFetchError
        On any HTTP error other than 404 (e.g. 429 when the hourly or daily quota is used up); the files
        already saved stay, so re-running resumes where it stopped.

    Notes
    -----
    One call per symbol over the whole window. A 404 or an empty list is saved too, so a symbol Tiingo
    does not serve is not asked again.
    """
    folder = DATA / "raw" / "tiingo" / "prices"
    todo = [s for s in symbols if not (folder / f"{s}.json").exists()]
    log.info("%d symbols to download (%d already on disk)", len(todo), len(symbols) - len(todo))
    with Progress() as bar:
        task = bar.add_task("tiingo", total=len(todo))
        for s in todo:
            url = PRICES_URL.format(s)
            resp = requests.get(
                url, params={"startDate": START, "endDate": END}, headers={"Authorization": f"Token {key}"}
            )
            if resp.status_code not in (200, 404):
                raise DataFetchError(f"{s}: HTTP {resp.status_code} {resp.text[:200]}")
            save_raw(resp.content if resp.status_code == 200 else b"[]", f"tiingo/prices/{s}.json", url)
            bar.advance(task)


def load_prices() -> pd.DataFrame:
    """Read all saved Tiingo responses into one table of unadjusted prices.

    Returns
    -------
    pd.DataFrame
        ``date, symbol, open, high, low, close, volume, div_cash, split_factor``; Tiingo's adj* fields are
        dropped because returns are rebuilt from raw prices (step 6).
    """
    parts = []
    for path in sorted((DATA / "raw" / "tiingo" / "prices").glob("*.json")):
        df = pd.DataFrame(json.loads(path.read_text()))
        if len(df):
            parts.append(df.assign(symbol=path.stem))
    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.rename(columns={"divCash": "div_cash", "splitFactor": "split_factor"})
    return df[["date", "symbol", "open", "high", "low", "close", "volume", "div_cash", "split_factor"]]


def main() -> None:
    """``python -m statarb.tiingo``: supported list. ``... prices [SYM ...]``: download (default: all)."""
    setup_logging()
    if sys.argv[1:2] != ["prices"]:
        supported = fetch_supported()
        save(supported, "tiingo_supported", stage="interim")
        etf = supported[supported["ticker"].isin(ETFS) & (supported["assetType"] == "ETF")]
        log.info("ETFs on Tiingo:\n%s", etf[["ticker", "startDate", "endDate"]].to_string(index=False))
        return
    symbols = sys.argv[2:]
    if not symbols:
        grid = load("universe_symbols", stage="interim")
        symbols = sorted(set(grid.loc[grid["in_tiingo"], "tiingo"]) | set(ETFS))
    download(symbols, Settings().tiingo_api_key)  # type: ignore[call-arg]  # read from .env
    prices = load_prices()
    save(prices, "tiingo_prices", stage="interim")
    log.info("%d symbols, %d rows", prices["symbol"].nunique(), len(prices))


if __name__ == "__main__":
    main()
