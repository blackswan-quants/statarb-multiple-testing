# Project phases

Summaries and presentations of each week of the project, collected in one place. The plan, the timeline and the
roles are in the main presentation: [`main-presentation.pdf`](main-presentation.pdf).

```
phases/
├── main-presentation.pdf      # project brief: papers, proposal, six-week timeline, week 1 tasks
├── week-1/                    # F0 · setup and data (23-29 Nov 2026)
│   ├── data-protocol/         # person A · data and protocol
│   ├── infrastructure/        # person B · repo, C++ build, CI, trial logger
│   └── model/                 # person C · OU prototype, s-score
├── week-2/
└── ...
```

## Conventions

- **One folder per week**, one subfolder per workstream (never name it `data/`: `.gitignore` drops every `data/` folder). Each subfolder has a `README.md` and, if there is one,
  the presentation of that work.
- **README**: what was done and why, main results, limits, what is still open. Written for someone reading it for
  the first time, with links to the code and to `docs/` instead of copying details.
- **Presentations**: export to PDF next to the source file (`.pptx`, `.key`), so anyone can read them on GitHub.
- **No data**: the repo is public. Do not add Tiingo, CRSP or sp500-data prices, or tables derived from them.
  Aggregated results (Sharpe, DSR, PBO, PnL charts) are fine.

Technical method notes stay in `docs/` (e.g. `docs/data_choices.md`, `docs/trials.md`).
