"""Quality checks of the data plan (section 3): every list goes to ``data/qa.sqlite`` for inspection."""

from __future__ import annotations

import logging
import sqlite3

import pandas as pd
from rich.console import Console
from rich.table import Table

from statarb.config import DATA, setup_logging
from statarb.io import load
from statarb.sector import etf_returns

log = logging.getLogger(__name__)

JUMP = 0.40  # |daily return| above this without a split or a known event goes to manual review
MIN_NAMES = 480
STALE_RUN = 5  # identical closes in a row


def panel() -> pd.DataFrame:
    """Index-day rows of ``returns`` joined with the price columns the checks need."""
    p = load("prices")[["date", "ticker", "close", "volume", "split_factor"]]
    r = load("returns").query("in_index")
    return r.merge(p, on=["date", "ticker"], how="left")


def coverage(x: pd.DataFrame, grid: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Share of index stock-days with a return, and the missing (date, ticker) list."""
    idx = grid.loc[grid["in_index"], ["date", "ticker"]]
    got = x.loc[x["ret"].notna(), ["date", "ticker"]].assign(ok=True)
    m = idx.merge(got, on=["date", "ticker"], how="left")
    missing = m.loc[m["ok"].isna(), ["date", "ticker"]]
    return 1 - len(missing) / len(m), missing.reset_index(drop=True)


def names_per_day(x: pd.DataFrame) -> pd.DataFrame:
    """Count index names with a return on each day."""
    return x[x["ret"].notna()].groupby("date").size().rename("names").reset_index()


def jumps(x: pd.DataFrame) -> pd.DataFrame:
    """Index-day returns beyond ±`JUMP` on days without a split (delisting returns excluded)."""
    hit = (x["ret"].abs() > JUMP) & (x["split_factor"] == 1) & (x["source"] != "delisting")
    return x.loc[hit, ["date", "ticker", "ret", "close", "source"]].reset_index(drop=True)


def split_days(x: pd.DataFrame) -> pd.DataFrame:
    """List returns on split days; they should look like ordinary days."""
    return x.loc[x["split_factor"] != 1, ["date", "ticker", "split_factor", "ret", "source"]].reset_index(
        drop=True
    )


def stale(x: pd.DataFrame) -> pd.DataFrame:
    """List runs of `STALE_RUN`+ identical closes and every no-trade day, on index days."""
    d = x.sort_values(["ticker", "date"])
    change = (d["close"] != d.groupby("ticker")["close"].shift()) | (d["ticker"] != d["ticker"].shift())
    run_len = d.groupby(change.cumsum())["close"].transform("size")
    hit = (run_len >= STALE_RUN) | d["no_trade"]
    return d.loc[hit, ["date", "ticker", "close", "volume", "no_trade"]].reset_index(drop=True)


def suspects(threshold: float = 0.95, days_over: int = 10) -> pd.DataFrame:
    """Tickers whose returns still disagree across sources (possible reused symbol or wrong company)."""
    out = []
    for name in ("tiingo_vs_wiki", "tiingo_vs_sp500data", "wiki_vs_sp500data"):
        s = load(f"recon_{name}", stage="interim")
        out.append(s[(s["corr"] < threshold) & (s["days_over"] > days_over)].assign(check=name))
    return pd.concat(out, ignore_index=True)


def spy_vs_members(x: pd.DataFrame) -> pd.DataFrame:
    """Yearly correlation between SPY and the equal-weight mean return of index members."""
    ew = x[~x["no_trade"]].groupby("date")["ret"].mean()
    both = pd.concat([ew.rename("ew"), etf_returns()["SPY"].rename("spy")], axis=1).dropna()
    corr = both.groupby(pd.DatetimeIndex(both.index).year).apply(lambda d: d["ew"].corr(d["spy"]))
    return corr.rename("corr").rename_axis("year").reset_index()


def run() -> dict[str, pd.DataFrame]:
    """Run all checks, write each table to ``data/qa.sqlite`` and return them with a summary table.

    Returns
    -------
    dict of str to pd.DataFrame
        One table per check plus ``summary`` (check, value, expected).
    """
    x = panel()
    cov, missing = coverage(x, load("universe_symbols", stage="interim"))
    t = {
        "missing": missing,
        "names_per_day": names_per_day(x),
        "jumps": jumps(x),
        "split_days": split_days(x),
        "stale": stale(x),
        "suspects": suspects(),
        "spy_vs_members": spy_vs_members(x),
        "tiingo_vs_wiki_flagged": load("recon_tiingo_vs_wiki_flagged", stage="interim"),
    }
    t["summary"] = pd.DataFrame(
        [
            ("coverage of index stock-days", f"{100 * cov:.3f}%", "> 99%"),
            (
                "names per day (min / median)",
                f"{t['names_per_day']['names'].min()} / {t['names_per_day']['names'].median():.0f}",
                f"~500, min >= {MIN_NAMES}",
            ),
            (f"unexplained |r| > {JUMP:.0%}", str(len(t["jumps"])), "short list"),
            (f"split days with |r| > {JUMP:.0%}", str((t["split_days"]["ret"].abs() > JUMP).sum()), "0"),
            ("stale / no-trade index days", str(len(t["stale"])), "rare"),
            (
                "tickers still disagreeing across sources",
                str(t["suspects"]["ticker"].nunique()),
                "few, listed",
            ),
            ("Tiingo vs WIKI days over 1%", str(len(t["tiingo_vs_wiki_flagged"])), "listed"),
            ("SPY vs members corr (min year)", f"{t['spy_vs_members']['corr'].min():.3f}", "high, stable"),
        ],
        columns=["check", "value", "expected"],
    )
    with sqlite3.connect(DATA / "qa.sqlite") as con:
        for name, df in t.items():
            df.to_sql(name, con, if_exists="replace", index=False)
    return t


def main() -> None:
    """Run the checks and print the summary table."""
    setup_logging()
    t = run()
    table = Table(title="Data QA")
    for col in t["summary"].columns:
        table.add_column(col)
    for row in t["summary"].itertuples(index=False):
        table.add_row(*map(str, row))
    Console().print(table)
    log.info("details in %s", DATA / "qa.sqlite")


if __name__ == "__main__":
    main()
