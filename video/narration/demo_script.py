"""Narration for the live-product demo cut. Each entry is one continuous
narration beat spoken while the browser performs the matching real
interaction (see demo_record.py) -- this is a screen-recorded demo of the
actual deployed site, not a slide deck."""

SCRIPT = [
    ("01_hook", "March ninth, 2023. Silicon Valley Bank collapses in a single day. Roku had half a billion dollars trapped inside. Circle's stablecoin lost its dollar peg, because three point three billion dollars of its reserves were stuck too. Startups couldn't make payroll. And every regulatory capital ratio said the bank was perfectly fine — right up until it wasn't."),
    ("02_search", "This is Marked. It catches this kind of risk months early, for every bank in America, using nothing but public filings. Let's search for Silicon Valley Bank. Marked ranked it number one of four thousand, seven hundred thirteen banks for run risk — five months before it failed. The regulatory Tier one ratio ranked it thirty-five hundred."),
    ("03_charts", "Here are two views of the same bank. This is the mark-to-market equity ratio — it collapses toward zero. This is the regulatory ratio the bank actually reported — flat, even rising, right up until the end."),
    ("04_slider", "This slider simulates a deposit run. At ninety percent of uninsured deposits withdrawn, the model shows balance-sheet insolvency. On March ninth, forty two billion dollars actually left."),
    ("05_backtest", "Every run-driven bank failure since 2019 landed in the top thirty-three of roughly forty-seven hundred banks, five quarters running. A standard machine-learning model, trained the ordinary way, ranks the same bank as completely average — the two lenses catch different failures."),
    ("06_depositflight", "The same score also predicted the 2023 deposit panic across hundreds of banks — an accuracy of point six four, versus point three nine for the regulatory ratio."),
    ("07_2008", "Applied unchanged to the 2008 crisis, it's a real but honestly weaker signal. A different crisis needs a different lens — and that's published here too, not hidden."),
    ("08_luck", "Could this be luck? The odds of four random banks all landing in the top thirty-three of about forty-seven hundred: two times ten to the negative ninth."),
    ("09_rigor", "Here's why this holds up. The scoring formula was frozen in git before any backtest ran — you can check the commit history yourself. Two real bugs were found while building this, and they're documented in the README, not hidden. Every number comes from free, public FDIC filings — no paid data, no black box, and this entire project cost zero dollars to build."),
    ("10_today", "On the Today tab, as of the latest filings, no bank currently matches the SVB pattern."),
    ("11_close", "Forty two billion dollars left Silicon Valley Bank in a single day, and every official number said it was fine. Marked saw it coming five months out. Marked: bank run-risk, computed from public filings. Research prototype, not financial advice. Link in the description."),
]
