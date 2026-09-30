"""Narration for the live-product demo cut. Each entry is one continuous
narration beat spoken while the browser performs the matching real
interaction (see demo_record.py) — this is a screen-recorded demo of the
actual deployed site, not a slide deck."""

SCRIPT = [
    ("01_hook", "On March ninth, 2023, forty two billion dollars left Silicon Valley Bank in a single day. Every regulatory capital ratio said the bank was fine. This is Marked — it ranks every U.S. bank on run risk, using only public filings."),
    ("02_search", "Let's search for it. Marked ranked Silicon Valley Bank number one of four thousand, seven hundred thirteen banks for run risk — five months before it failed. The regulatory Tier one ratio ranked it thirty-five hundred."),
    ("03_charts", "Here are two views of the same bank. This is the mark-to-market equity ratio — it collapses toward zero. This is the regulatory ratio the bank actually reported — flat, even rising, right up until the end."),
    ("04_slider", "This slider simulates a deposit run. At ninety percent of uninsured deposits withdrawn, the model shows balance-sheet insolvency. On March ninth, forty two billion dollars actually left."),
    ("05_backtest", "Every run-driven bank failure since 2019 landed in the top thirty-three of roughly forty-seven hundred banks, five quarters running. A standard machine-learning model, trained the ordinary way, ranks the same bank as completely average — the two lenses catch different failures."),
    ("06_depositflight", "The same score also predicted the 2023 deposit panic across hundreds of banks — an accuracy of point six four, versus point three nine for the regulatory ratio."),
    ("07_2008", "Applied unchanged to the 2008 crisis, it's a real but honestly weaker signal. A different crisis needs a different lens — and that's published here too, not hidden."),
    ("08_luck", "Could this be luck? The odds of four random banks all landing in the top thirty-three of about forty-seven hundred: two times ten to the negative ninth."),
    ("09_today", "On the Today tab, as of the latest filings, no bank currently matches the SVB pattern."),
    ("10_close", "Two real bugs were found and fixed while building this, documented in the README, not hidden. Marked: bank run-risk, computed from public filings. Research prototype, not financial advice. Link in the description."),
]
