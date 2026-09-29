# Marked

**Every US bank, ranked on run risk, using only public filings.**

Five months before Silicon Valley Bank failed, Marked ranked it **#1 of 4,713 banks**.
The regulatory capital ratio — the number banks report as "well capitalized," the
number most public tools show — ranked it **#3,500**.

Live site: **[link to be added on deploy]**
Demo video: **[link to be added]**

> Research prototype built for the Global Innovation Build Challenge V2. Not
> financial advice, not a regulatory or diagnostic tool, and not an assertion
> that any currently operating bank will fail. See [Limits](#limits) below.

---

## The problem

When interest rates rise, bonds a bank bought earlier lose market value. Banks
are allowed to book some of those bonds as "held to maturity," which lets them
carry them at original cost — the loss never appears in the bank's official
capital ratio unless the bank is forced to sell.

Deposits above $250,000 aren't covered by FDIC insurance. If a large share of
uninsured depositors gets nervous and tries to withdraw at once, a bank can be
forced to sell those bonds, crystallizing the hidden loss exactly when it can
least afford it. That's what happened to Silicon Valley Bank. Roku had roughly
$487M there ([its own 8-K filing](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=roku)
says so). Circle had $3.3B of USDC reserves at SVB, which briefly broke the
stablecoin's dollar peg. $42B left SVB in a single day; the FDIC closed it the
next morning.

Every capital ratio regulators and the press cite is the *regulatory* ratio —
the one that let SVB carry that loss off the books. Marked computes the other
number: what the bank's capital looks like if that bond loss is marked to
market, set against how much of its deposit base is uninsured and could run.

## The number

Using only data that would have been publicly filed by each date (see
[Look-ahead discipline](#look-ahead-discipline)):

| Bank | Failed | Quarters before | Marked's rank | Tier 1 capital rank |
|---|---|---|---|---|
| Silicon Valley Bank | 2023-03-10 | 5 months (T-2) | **#1 of 4,713** | #3,500 |
| Signature Bank | 2023-03-12 | 5 months (T-2) | **#24 of 4,713** | #1,924 |
| First Republic Bank | 2023-05-01 | 5 months (T-2) | **#33 of 4,713** | #2,205 |
| Republic Bank | 2024-04-26 | 5 months (T-2) | **#1 of 4,583** | #1,696 |

All four run-driven bank failures since 2019 land in the **top 33 of roughly
4,700 banks**, across every one of the five quarters before they failed. The
odds of that happening to four randomly chosen banks by chance: **2.0×10⁻⁹**
(closed-form; confirmed by a 200,000-trial simulation — see
`results/REPORT.md`, section D1).

Republic Bank failed in **April 2024** — more than a year after this project's
underlying theory was published (Jiang, Matvos, Piskorski & Seru, NBER working
paper, March 2023). It's a genuine out-of-sample case, not something the
formula could have been shaped around.

**The formula was frozen before any backtest ran.** See
[Not hindsight](#not-hindsight-the-formula-was-frozen-first) below —
this is checkable in the git history, not just asserted.

### The run threshold matches what actually happened

At the end of 2022, Marked's model says SVB could absorb **$38.49B** of
uninsured-deposit withdrawals using cash and available-for-sale securities
before it would have to start selling held-to-maturity bonds at a loss. On
March 9, 2023, **$42B** actually left. A further ~$100B was reportedly queued
for the next morning before the FDIC stepped in. (Outflow figures are from
contemporary reporting — Reuters, the Financial Times — not from FDIC filings;
see `results/REPORT.md` section E.)

### A standard ML model, trained the ordinary way, misses SVB entirely

To check this isn't just "any reasonable model catches SVB," `pipeline/classic.py`
trains a logistic regression on CAMELS-style ratios (equity, ROA, charge-offs,
loan/deposit ratio, brokered-deposit reliance) against every bank failure from
2008–2012 — the standard approach most bank-failure ML work uses. Applied to
Q3 2022:

- **Silicon Valley Bank: ranked #2,678 of 4,813** — squarely average, not flagged.
- **First Republic Bank: ranked #3,465 of 4,813** — among the *safest*-looking banks.
- **Citizens Bank (Sac City), which failed from ordinary credit losses in 2023:
  ranked #26 of 4,813** — correctly flagged.

The two lenses catch different things. That's the point: SVB's failure wasn't
a credit story, it was an accounting-gap story, and a model trained the usual
way doesn't see it.

## Not hindsight: the formula was frozen first

`pipeline/score.py` was committed in its own commit, **before** the historical
backtest was ever run (`git log --follow pipeline/score.py` — the first commit
predates `results/backtest.json`). It has two inputs, both plain accounting
ratios, with no fitted weights:

```
run_risk_score = uninsured_deposit_share / mark_to_market_equity_ratio
```

- `mark_to_market_equity_ratio` = (book equity − unbooked held-to-maturity
  bond loss) / total assets
- `uninsured_deposit_share` = uninsured deposits / total deposits

We also show what each input does **alone**, so the combined score isn't
presented as the only choice that happens to work (`results/REPORT.md`,
section D):

| | SVB rank | of |
|---|---|---|
| mark-to-market equity ratio alone | #13 | 4,713 |
| uninsured share alone | #9 | 917 (reporting banks) |
| **combined score** | **#1** | 917 |

## Does it generalize, or is this just SVB?

We applied the **same frozen formula, unchanged**, to the 2008 financial
crisis — a completely different era with a completely different failure
mechanism (widespread subprime credit losses, not a rate-driven accounting
gap) — and checked it against IndyMac and Washington Mutual, the two largest
run-driven failures of that crisis.

**Honest result: it's a much weaker signal there.** IndyMac ranked #273 and
WaMu #395 of ~8,500 banks (top 4–6%, not top 1%). For WaMu, the *regulatory*
Tier 1 ratio actually did better in several quarters (#36–120) than Marked did
(#249–395). We looked into why: FDIC's API reports held-to-maturity fair
value as unavailable for both banks throughout 2006–2008, so the
mark-to-market half of the formula can't be computed for that era — the score
there is really just uninsured share. We're not hiding this: **Marked's claim
is that it catches the specific 2022–23 accounting-gap mechanism, not that
it's a general-purpose bank failure predictor across every era and every
failure type.** See `pipeline/depth.py` and `results/d2_depth.json`.

## Does it predict the broader 2023 panic, not just four banks?

We tested whether the Q3 2022 score predicted which banks lost the most
deposits in the run quarter (Q4 2022 → Q1 2023), across the full population —
not just the four that failed.

`run_risk_score` can only be computed for banks that report uninsured
deposits to the FDIC (roughly $1B+ in assets, ~900 of ~4,700 banks that
quarter) — it's structurally undefined for smaller banks, not zero, and we
don't pretend otherwise.

On those ~900 reporting banks:

| | AUC | Top-decile lift |
|---|---|---|
| **Marked's score** | **0.637** | **2.02×** |
| Tier 1 regulatory ratio (same banks) | 0.391 (worse than random) | 0.9× |
| Marked, seasonally adjusted* | 0.554 | 1.34× |
| Tier 1, all 4,636 banks (context) | 0.418 | — |

\* subtracting each bank's typical Q1 deposit swing from the prior year, to
net out ordinary seasonality rather than treat every winter dip as a warning
sign.

Among the top 50 banks flagged in Q3 2022, all four eventual failures appear,
plus 46 survivors — several of which had real, serious deposit flight anyway:
**Silvergate Bank lost 76% of deposits** (voluntarily wound down in early
2023), Charles Schwab entities lost 10–20%, Comerica and Zions lost mid-single
digits. These weren't false alarms; they were banks under real stress that
didn't ultimately fail. Full list in `results/REPORT.md`, section C.

## Limits

We're publishing what this doesn't do, not just what it does:

- **Fraud and credit failures are invisible by design.** Heartland Tri-State
  Bank failed from fraud in 2023; this model never flagged it, and shouldn't
  be read as a general bankruptcy predictor. `classic.py`'s standard ML model
  is the intended lens for credit-driven failures — it independently catches
  Citizens Bank (Sac City) at #26.
- **Banks under roughly $1B in assets don't report uninsured deposits** in a
  way the free FDIC API exposes. They show as "not reported," never as "safe."
- **Across all ~4,700 banks**, the deposit-flight test above only works on the
  ~900 reporting banks — it isn't a claim about every bank.
- **First Republic's losses were mostly in low-rate mortgages, not bonds.**
  This model only marks bond losses, so First Republic likely ranks lower
  than its true risk. We checked whether the free FDIC API exposes
  loan-maturity/repricing detail (Call Report Schedule RC-C) to fix this —
  it doesn't, beyond aggregate categories — so this is a stated limit, not a
  silently patched gap. Same finding for AFS amortized-cost history (needed
  for a forward rate-shock projection) and FHLB unused-borrowing capacity
  (only drawn amounts are exposed).
- **A data-integrity bug was found and fixed while building this**: when
  held-to-maturity fair value is missing (not zero), an earlier version of
  the code defaulted it to zero, which manufactured a phantom 100% loss on
  that bank's bond book. Fixed to treat a missing value as "unknown, treated
  as no loss" — conservative, documented, and covered by a regression test
  (`tests/test_score.py::TestBranchFilter`, plus the `depth.py` docstring for
  where this surfaced). A second bug — an `is not None` check on a pandas
  column that's always true for `NaN` — silently merged two supposedly
  different backtest populations; also fixed, with the fix's own comment in
  `pipeline/backtest.py`. Both are left in the code as comments, not scrubbed
  from history, because a rigor claim that hides its own mistakes isn't one.
- **This is a research prototype**, not financial advice, not a regulatory
  tool, and not a guarantee about any bank. It reads public accounting data;
  it doesn't know about off-balance-sheet hedges, parent-company support, or
  private information a bank hasn't filed.

## Prior art

This project didn't invent the idea that mark-to-market losses and uninsured
deposits matter — it built a specific thing nobody else had published:

- **Jiang, Matvos, Piskorski & Seru**, "Monetary Tightening and U.S. Bank
  Fragility in 2023" (NBER Working Paper 31048, *Journal of Financial
  Economics* 2024) — the academic source for the mark-to-market /
  uninsured-deposit mechanism. Aggregate, retrospective, not a per-bank
  backtested tool.
- **FAU Banking Initiative** — separate public screeners for unrealized
  securities losses (152 banks >$10B) and uninsured deposit share (1,028
  banks >$1B). Doesn't combine the two into a single run-risk score, doesn't
  backtest against failure dates, and doesn't model a dollar run threshold.
- **BankHealthData** — a composite bank health score. Doesn't publish a
  reproducible historical backtest against the regulatory ratio.

Marked's contribution: combining both inputs into one score, freezing it
before testing, backtesting it against every bank failure since 2019 and the
2008 crisis with an explicit look-ahead guard, comparing it against both the
regulatory ratio and an independent ML baseline, and modeling a dollar run
threshold checked against what actually happened at SVB.

## How it works

See the site's **"How it works & limits"** tab for the plain-language version.
Technical version: `pipeline/score.py` is fully documented inline.

## Reproduce it

```bash
uv sync
uv run pipeline/fetch.py          # pulls every FDIC quarterly filing 2001-2026 (~15 min, cached to data/raw/)
uv run pytest tests/ -q           # 13 tests: formula math, look-ahead guard, branch filter
uv run python -m pipeline.classic # trains & sanity-checks the classic ML baseline
uv run python -m pipeline.backtest        # writes results/backtest.json + results/REPORT.md
uv run python -m pipeline.depth           # D1/D2 depth checks -> results/d2_depth.json
uv run python -m pipeline.export_site_data # writes site/data/*.json for the static site
```

Every number in this README and in `site/` comes from `results/REPORT.md` —
none are typed by hand anywhere else.

To view the site locally: `cd site && python3 -m http.server 8000`.

## Data source

[FDIC BankFind Suite API](https://banks.data.fdic.gov/docs/) — free, public,
no key required. Quarterly Call Report financials, 2001–2026, and the full
FDIC bank-failures list.

## Look-ahead discipline

Every quarter used to score a bank at a given as-of date must have its
`REPDTE` at least 30 days in the past relative to that date (Call Reports
aren't public the day a quarter ends). Enforced in
`pipeline/backtest.py::usable_asof` and tested in
`tests/test_score.py::TestLookaheadGuard`.

Failed banks are kept in the historical panel at every quarter up to their
failure (no survivorship bias) — their last known filings are loaded from the
same source as any surviving bank's.

Foreign-bank US branches, which often report zero or negative equity and
aren't meaningfully comparable on an equity-ratio basis, are filtered out
(`tests/test_score.py::TestBranchFilter`) — this filter was added after the
initial spike found several of them topping naive rankings ahead of SVB.

## Built with

Python (pandas, scikit-learn, pyarrow), the FDIC BankFind Suite API, vanilla
HTML/CSS/JavaScript (no frontend framework, no build step, no charting
library — the line charts are ~60 lines of hand-written SVG in
`site/chart.js`), GitHub Pages.

**AI tool disclosure:** built with Claude Code (Anthropic). All research
questions (rules, prior art, past-winner analysis), pipeline code, the
scoring formula's initial design, the static site, and this README were
written with Claude Code as an active collaborator under my direction. All
numeric claims were independently re-verified by running the actual pipeline
against the live FDIC API, not taken on faith from the AI's output — see the
two real bugs documented in [Limits](#limits) above, which were caught during
that verification.

## License

MIT. See `LICENSE`.
