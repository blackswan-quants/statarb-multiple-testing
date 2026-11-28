# CLAUDE.md

Stat arb PCA (Avellaneda-Lee) + multiple testing (DSR, PBO). Data plan: S&P 500 point-in-time 2006-2025 + 12 ETF,
Tiingo as main source, Quandl WIKI as cross-check, literature proxies for spread/sector/delisting.

## Programming guidelines (full text: `programming-guidelines.pdf`)
Strong recommendations, not hard rules.

- **Docs & types**: NumPy-style docstrings on public functions (Parameters, Returns, Raises, Notes for non-obvious
  choices). PEP 8, full type hints with precise types (`pd.DataFrame`, `date`, dataclasses), `from __future__ import annotations`.
- **Lint**: ruff + mypy, run by pre-commit.
- **Design**: no premature abstraction, explicit code. Config via `pydantic-settings` from `.env`, fail fast on missing keys.
- **Errors**: custom domain exceptions (`DataFetchError`, ...) in `statarb/errors.py`, never bare `Exception`.
- **Invariants**: `assert` in code for financial/logical invariants, not comments.
- **Testing**: end-to-end asserts in notebooks + pytest for math/parsing functions.
- **Temporal discipline**: explicit `as_of: date` in pricing/classification/hedging functions; filter `trade_date <= as_of`
  first; no implicit "today". No look-ahead (rolling windows end at t-1).
- **Checkpoints**: raw / interim / processed stages saved to disk (parquet) so each stage re-runs without re-fetching.
  Raw data is immutable, logged in `data/raw/manifest.csv` (date, url, sha256). SQLite for inspectable outputs (QA).
- **Env**: Python 3.12 + uv, exact pins in `uv.lock`; a clean checkout needs only `uv sync` and `.env`.
- **Git**: conventional commits (`feat:`, `fix:`, `chore:` ...).
- **Logging**: `logging.getLogger(__name__)` in every module, rich handler, no `print` outside CLI/notebook display.
- **Presentation**: clean tables/output; Plotly for charts, PySide6 for raw table views.

## Style (project owner preference)
- Lean, compact code that reads like a human wrote it. No defensive checks unless needed.
- Few targeted tests (math, parsing), not exhaustive suites.
- Work step by step; show results and wait for approval before the next step.

## Layout
- `statarb/` flat modules, each with `main()` → `uv run python -m statarb.<module>`.
- `reference/` versioned hand-made lists (ticker overrides, delistings).
- `data/` is gitignored (note: `.gitignore` ignores every folder named `data/`, so no `statarb/data/` package).

## Commands
```
uv sync
uv run python -m statarb               # rebuild processed tables from raw files (add --download to refetch)
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_qa.ipynb
uv run ruff check . && uv run ruff format --check . && uv run mypy statarb && uv run pytest
```
