# statarb-multiple-testing
Analyzes the genuine out-of-sample edge of PCA-based statistical arbitrage after applying corrections for multiple variants tested, fat tails, and trading costs.

## Data

Point-in-time S&P 500 (2006-2025) plus 12 ETFs, built from free sources and one month of Tiingo Power.

```
uv sync                       # Python 3.12, exact pins in uv.lock
cp .env.example .env          # TIINGO_API_KEY, KAGGLE_API_TOKEN
uv run python -m statarb --download
uv run python -m statarb.tiingo prices
uv run python -m statarb      # rebuild processed tables, prints the QA summary
```

Outputs go to `data/` (not versioned): `membership`, `prices`, `returns`, `sector`, `spread`, `macro`, `factors`,
plus `data/qa.sqlite`. Hand-checked fixes live in `reference/`, method choices and limits in
`docs/data_choices.md`, end-to-end checks in `notebooks/01_data_qa.ipynb`.
