# Trial log schema

Every backtest run ("trial"), including test runs, is recorded with
`log_trial(config, pnl_gross, pnl_net)`. The log is the source of the number
of trials $N$ used by the Deflated Sharpe Ratio and of the $T \times N$
return matrix used by PBO.

## Storage

Each trial writes two files with the same name, in `trials/`:

```
trials/
├── 20261130T100213123456Z_a3f9c1d2e4b5.json      # metadata
├── 20261130T100213123456Z_a3f9c1d2e4b5.parquet   # daily PnL
└── ...
```

- `trials/` is committed to git: the full log is part of the published results.
- Files are never edited or deleted. A failed or wrong run stays in the log.

## Trial id

`<timestamp>_<first 12 hex chars of config_hash>`, with the timestamp in UTC
as `YYYYMMDDTHHMMSSffffffZ`. Sorting ids alphabetically sorts trials by time.

## Metadata (`.json`)

| Field | Type | Description |
|---|---|---|
| `schema_version` | int | Version of this schema, currently `1` |
| `trial_id` | string | See *Trial id* |
| `config` | object | Full configuration of the run, in canonical JSON |
| `config_hash` | string | SHA-256 of the canonical JSON, 64 hex characters |
| `commit` | string | `git rev-parse HEAD` when the run started |
| `dirty` | bool | `true` if tracked files had uncommitted changes |
| `timestamp_utc` | string | ISO 8601 in UTC, e.g. `2026-11-30T10:02:13.123456Z` |
| `summary` | object | Summary metrics computed from the daily PnL, see *Summary metrics* |

Example:

```json
{
  "schema_version": 1,
  "trial_id": "20261130T100213123456Z_a3f9c1d2e4b5",
  "config": {"factors": "etf", "s_entry": 1.25, "s_exit": 0.5, "window": 60},
  "config_hash": "a3f9c1d2e4b5...",
  "commit": "e6e2ff4...",
  "dirty": false,
  "timestamp_utc": "2026-11-30T10:02:13.123456Z",
  "summary": {
    "n_days": 4780,
    "sharpe_gross": 1.42,
    "sharpe_net": 0.87,
    "max_drawdown_gross": -0.08,
    "max_drawdown_net": -0.12
  }
}
```

## Daily PnL (`.parquet`)

One row per trading day, dates sorted and unique, no missing values
(a day with no positions has PnL $0$).

| Column | Type | Description |
|---|---|---|
| `date` | date | Trading day |
| `pnl_gross` | float64 | Daily portfolio return before costs |
| `pnl_net` | float64 | Daily portfolio return after costs |

PnL is a **return** on the portfolio's reference capital, not dollars, so
Sharpe ratios are comparable across trials:

$$
r^{\text{net}}_{t} = r^{\text{gross}}_{t} - c_{t}, \qquad c_t \ge 0 .
$$

## Summary metrics

Stored in `summary` for quick inspection, computed from the daily PnL
with the definitions below, separately for gross and net returns.

| Field | Description |
|---|---|
| `n_days` | Number of trading days $T$ |
| `sharpe_gross`, `sharpe_net` | Annualized Sharpe ratio |
| `max_drawdown_gross`, `max_drawdown_net` | Maximum drawdown, a number $\le 0$ |

Annualized Sharpe ratio, with sample standard deviation and no risk-free
rate subtracted (the strategy is market neutral):

$$
\widehat{SR} = \sqrt{252}\,\frac{\bar r}{\hat\sigma_r},
\qquad
\bar r = \frac{1}{T}\sum_{t=1}^{T} r_t,
\qquad
\hat\sigma_r = \sqrt{\frac{1}{T-1}\sum_{t=1}^{T}\left(r_t - \bar r\right)^2}.
$$

If $\hat\sigma_r$ is zero or undefined (fewer than two days) the Sharpe
ratio is `null`.

Maximum drawdown, on the compounded equity curve $V_t$ with $V_0 = 1$:

$$
V_t = \prod_{s=1}^{t}\left(1 + r_s\right),
\qquad
\text{MDD} = \min_{t}\left(\frac{V_t}{\max_{s \le t} V_s} - 1\right).
$$

For example, $-0.12$ means the worst peak-to-trough loss was 12%.

## Canonical JSON

The config is serialized with:

- keys sorted alphabetically, at every nesting level;
- no whitespace (separators `,` and `:`);
- UTF-8 encoding;
- no `NaN` or `Infinity`; allowed types are object, array, string,
  integer, float, boolean, null.

Two configs with the same values give the same JSON, whatever the key order.
Types matter: `60` and `60.0` are different values and give different hashes.

The config must contain **everything that can change the PnL**: period,
universe, windows, factor method, s-score thresholds, cost model, seed.
A parameter left out of the config makes two different runs look identical.

## Config hash

$$
\texttt{config\_hash} = \operatorname{SHA\text{-}256}\big(\operatorname{utf8}(\operatorname{canonical\_json}(\texttt{config}))\big)
$$

Same config, same hash. The hash identifies *what* was tried; `trial_id`
identifies *each run*.

## Reading the log

- `load_index()`: one row per trial (metadata, config and summary expanded
  into columns, e.g. `config.window`, `summary.sharpe_net`).
- `load_matrix(kind="net" | "gross")`: $T \times N$ matrix of daily returns,
  dates as rows, `trial_id` as columns.

Further views (e.g. a local SQLite file for queries) are built from these
files and are not committed.

## Test runs

Runs that only check the infrastructure (not attempts at the strategy) set
`"kind": "dummy"` in their config:

```json
{"kind": "dummy", "note": "end-to-end check of the trial logger", "seed": 0}
```

They stay in the log like every other run, but analyses that count trials
(N, DSR, PBO) exclude them explicitly:

```python
index = load_index()
trials = index[index["config.kind"] != "dummy"]
```

Strategy configs never use `kind = "dummy"`.

## Notes

- **One JSON + one parquet per trial**: every run only creates new files with
  a unique name, so two branches that log trials can always be merged
  without conflicts, also from the GitHub merge button.
- **Not SQLite** (the guidelines suggest SQLite for outputs): the log is
  versioned in git and git cannot merge two versions of a binary file, so
  one branch's trials would be lost. A local SQLite view can be rebuilt
  from the files when needed.
- **Daily PnL, not only summary metrics**: PBO (CSCV), the effective number
  of trials and the block bootstrap need the full daily series.
- **Summary metrics are a convenience, not the source of truth**: they are
  derived from the parquet and never updated after the run. DSR, PBO and the
  report always recompute metrics from the daily PnL, so a later change in a
  definition cannot leave stale numbers in the results.
- **Dirty runs are logged, not rejected**: every attempt counts in $N$.
  The `dirty` flag marks runs that the commit alone cannot reproduce.
- **Dummy runs are labelled, not deleted**: the log is append-only, so test
  runs are marked in their config and filtered out by the analyses. The filter
  is explicit, so the trials excluded from $N$ are always visible.
- **Counting $N$**: repeated runs of the same config stay in the log.
  By default all runs count; the reader can keep only the latest per
  `config_hash`. The choice used for the DSR is stated in the report.
- **Size**: about 150 KB per trial (17 years of daily PnL, holdout excluded).
  Fine for hundreds of trials; revisit the format if the log grows beyond ~1000.
