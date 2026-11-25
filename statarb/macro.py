"""Step 10: FRED series (T-bill, VIX) and Kenneth French daily factors."""

from __future__ import annotations

import io
import logging
import zipfile

import pandas as pd
import requests

from statarb.config import END, START, setup_logging
from statarb.errors import DataFetchError
from statarb.io import save, save_raw

log = logging.getLogger(__name__)

FRED_SERIES = ["DTB3", "VIXCLS"]
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
FRENCH_FILES = ["F-F_Research_Data_5_Factors_2x3_daily", "F-F_Momentum_Factor_daily"]


def _get(url: str, name: str) -> bytes:
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        raise DataFetchError(f"{url} -> HTTP {resp.status_code}")
    save_raw(resp.content, name, url)
    return resp.content


def fetch_fred() -> pd.DataFrame:
    """Download FRED series for the project window (no API key needed).

    Returns
    -------
    pd.DataFrame
        Indexed by ``date``: ``DTB3`` (3M T-bill, annual %, discount basis) and ``VIXCLS``.
        Holidays are NaN, as published.
    """
    cols = []
    for sid in FRED_SERIES:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}&coed={END}"
        raw = _get(url, f"fred/{sid}.csv")
        s = pd.read_csv(io.BytesIO(raw), index_col=0, parse_dates=True, na_values=".")[sid]
        cols.append(s)
    return pd.concat(cols, axis=1).rename_axis("date")


def parse_french(text: str) -> pd.DataFrame:
    """Parse a French-library daily CSV: keep rows starting with a YYYYMMDD date, convert % to decimals.

    Notes
    -----
    The files have a free-text header and footer around the table, so data lines are picked by their
    8-digit date instead of fixed row offsets, which change between releases.
    """
    lines = text.splitlines()
    header = next(line for line in lines if line.startswith(","))
    rows = [line for line in lines if line[:8].isdigit()]
    df = pd.read_csv(io.StringIO("\n".join([header, *rows])), index_col=0)
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m%d").rename("date")
    df.columns = df.columns.str.strip()
    return df / 100


def fetch_french() -> pd.DataFrame:
    """Download Fama-French 5 factors and momentum (daily, decimals) for the project window."""
    parts = []
    for name in FRENCH_FILES:
        raw = _get(FRENCH_URL.format(name), f"french/{name}.zip")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            parts.append(parse_french(z.read(z.namelist()[0]).decode("latin-1")))
    return pd.concat(parts, axis=1, join="inner").loc[START:END]


def main() -> None:
    """Save ``macro.parquet`` (FRED) and ``factors.parquet`` (French)."""
    setup_logging()
    fred, ff = fetch_fred(), fetch_french()
    assert ff.abs().max().max() < 0.5, "factor returns look like percent, not decimals"
    save(fred, "macro")
    save(ff, "factors")
    log.info(
        "FRED %s -> %s, missing: %s", fred.index[0].date(), fred.index[-1].date(), fred.isna().sum().to_dict()
    )
    log.info("French %s -> %s, columns %s", ff.index[0].date(), ff.index[-1].date(), list(ff.columns))


if __name__ == "__main__":
    main()
