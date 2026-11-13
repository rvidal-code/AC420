"""Manual integration smoke test. Set SEC_USER_AGENT in the environment."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lens.providers import company_data, filing_list, filing_html
from lens.financials import periods, snapshot
from lens.filings import parse_inline, segments, maturities
from datetime import date

agent = os.environ["SEC_USER_AGENT"]
for cik in (320193, 789019):
    facts, submissions, retrieved = company_data(cik, agent)
    filings = filing_list(submissions, cik)
    for mode in ("Quarterly", "Annual"):
        period = next(p for p in periods(facts, mode, date.today().isoformat()) if any(f["end"] == p[1] for f in filings))
        filing = min((f for f in filings if f["end"] == period[1]), key=lambda f: f["filed"])
        snap = snapshot(facts, period, filing["filed"])
        print(cik, mode, period, snap["values"])
        inline, text = parse_inline(filing_html(filing["url"], agent))
        print("inline facts", len(inline), "excerpt characters", len(text), "segments", segments(inline, *period, snap["values"]["Revenue"]), "maturities", maturities(inline, period[1]))
