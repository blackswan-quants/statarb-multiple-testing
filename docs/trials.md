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

If $\hat\sigma_r = 0$ the Sharpe ratio is `null`.

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

Same config, same