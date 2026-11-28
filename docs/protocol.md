# Protocol: sealed holdout

The last three years of data, **2023-01-01 to 2025-12-31**, are the holdout. They are used once, at milestone M4,
to evaluate one configuration chosen before looking at them. Sealed on 2026-11-28, git tag `holdout-sealed`.

## Periods

| Period | Dates | Use |
|---|---|---|
| Development | 2006-01-03 to 2022-12-30 | Everything: calibration, grid, ablation, DSR, PBO |
| Holdout | 2023-01-03 to 2025-12-31 | One run at M4 |

The boundary is `HOLDOUT_START` in `statarb/config.py`. Rolling windows on the first holdout days end in 2022,
which is fine: they only use the past.

## Rules until M4

1. No statistic, chart or backtest on dates from 2023-01-01 on, quick looks included (a plot of a residual, a
   correlation, a Sharpe ratio).
2. Files exported for the engine and for the analysis stop on 2022-12-30. The processed tables in
   `data/processed/` still cover 2006-2025: they feed the export, not the analysis.
3. Every trial in `trials/` covers development dates only.
4. Data integrity checks may still run on the full period (the pipeline and `notebooks/01_data_qa.ipynb`:
   coverage, names per day, jumps, stale days, agreement between sources). They fix data errors and say nothing
   about the strategy.

## Opening the holdout at M4

1. Choose the configuration on development results only, write it below with its `config_hash`, commit.
2. Export the holdout, run that configuration once, log it as a trial.
3. Report the result whatever it is. A second run (e.g. after a bug fix) is reported next to the first, not
   instead of it.

## Seen before the seal

The data QA of 2026-11-25 printed full-period summaries, 2023-2025 included: coverage, the largest daily moves
(e.g. SVB and Signature in March 2023, First Republic in May 2023), the yearly correlation between SPY and the
index members, and the distribution of the spread estimate. No strategy output (residuals, s-scores, PnL) has been
computed on any period.
