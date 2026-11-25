# Data choices and limits

Method choices fixed before any backtest (to be logged as trials), and limits to state in the report.
Details and code: `statarb/`, hand-made lists: `reference/`.

## Choices (decided 2026-11-25)

| Topic | Choice | Rejected alternative |
|---|---|---|
| Sector | ETF with max R² on the past 252 daily returns, window ending t-1; ETF eligible after a full window | SIC codes mapped by hand to SPDR sectors |
| Spread | Abdi-Ranaldo (2017), 21-day window ending t-1, split-aware; missing -> same-day sector median, else market median | Validation/calibration on Databento quotes |
| Delisting | Real post-halt OTC price where the stock was halted while in the index (SVB, Signature); cash acquisitions closed at the last close | Fixed literature correction (-30% NYSE / -55% Nasdaq) |
| Source priority | Tiingo > WIKI > sp500-data, returns computed only inside one source and symbol | Splicing price levels across sources |

## Limits to declare

- **Sources**: community lists (fja05680 index file, WIKI) instead of CRSP. Delisted 2006-2012 names come from
  github.com/Johnbrick123/sp500-data, mostly CRSP-derived with no stated license; every row keeps its `source`.
  Coverage: 99.97% of index stock-days.
- **Sector**: statistical rule, not historical GICS; noisy (about 2.9 switches per stock-year) and some odd
  labels (e.g. AAPL -> XLY in 2025).
- **Spread**: estimated from daily bars, not measured; median 23 bps against 2-10 bps quoted spreads for
  S&P 500 names, about 45% of estimates truncated at zero. Read as a conservative cost; report cost sensitivity.
- **Paramount 2019-2025**: proxied by class A (PARAA); the index held class B.
- **CRSP-sourced rows** have no open/high/low/volume: their spread comes from the sector median.
- **Borrow fee**: not observed, assumed parameter.
