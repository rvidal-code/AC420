# Financial Lens

A Python / Streamlit class project for visually exploring U.S. SEC-reporting companies, with automatic, cited explanations below each chart.

## Run locally

Python 3.12 or 3.13 recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Copy `secrets.example.toml` to `.streamlit/secrets.toml`. Set `SEC_USER_AGENT` to an application name and real contact email. Set `GROQ_API_KEY` to enable AI. Keep secrets out of Git.

## Deploy to Streamlit Community Cloud

1. Sign in at https://share.streamlit.io and connect your GitHub account.
2. Create an app from `rvidal-code/AC420`, branch `main`, entry point `app.py`.
3. Choose Python 3.13 (or 3.12). Under Advanced settings > Secrets, paste the values from `secrets.example.toml` with your real contact and API key.
4. Deploy. The app receives a `streamlit.app` URL. Future commits update it.

Use a free Groq account without enabling paid billing. Quotas and model availability are provider/account dependent; the app cannot guarantee high or unlimited free usage. Change `GROQ_MODEL` if the default model is unavailable. All chart explanations are batched into one request and cached for 24 hours by chart data, evidence, and model. Rate limits leave the charts usable. Do not enter API keys in chat or commit them.

## Charts

- Prior-period or year-over-year EBITDA waterfall (accounting-component reconciliation).
- Revenue segment treemap, using one disclosed dimension whose members reconcile to consolidated revenue within 1.5% for rounding.
- Daily unadjusted stock closing prices, from period start through filing date.
- Debt principal maturities, only when all six standard consolidated repayment buckets are disclosed.
- Revenue / operating income / net income trends.
- Operating cash flow to free cash flow waterfall.
- Cash, long-term debt including current portion, and net debt trends. Debt does not represent all liabilities or necessarily all short-term borrowings.

## Data and accounting methodology

Financial figures come from SEC Company Facts (US-GAAP USD facts). Available periods respect fiscal calendars. Historical views exclude facts filed after the selected original filing date. Quarter-only values are used when present; otherwise a quarter is derived by subtracting cumulative values with an identical fiscal-year start. Q4 uses the fiscal year less nine months. Provenance downloads include tags, accession numbers, and underlying inputs. Filing links identify the corresponding 10-Q/10-K. A chart may be unavailable when the company uses unsupported tags, non-USD reporting, absent disclosures, or inaccessible data. No missing figure is treated as zero.

EBITDA is net income plus interest expense, tax expense, and reported D&A. It is unadjusted and not standardized across issuers; the selected D&A tags may include depletion/accretion. The bridge reconciles mathematical changes in those components, rather than asserting management-disclosed operational drivers. It is not adjusted EBITDA. FCF is operating cash flow minus purchases of property, plant, and equipment. There are no inferred segment or maturity values. Q4 segment charts may be unavailable because dimensional Q4 values are not derived from separate filings.

Stock prices use yfinance, an unofficial Yahoo Finance client intended for educational/research purposes. This is not an exchange-grade real-time feed; review upstream terms before broader distribution. Errors and throttling produce an unavailable chart. Financial statements update on filings, not tick-by-tick. Current filing history is limited to SEC submissions' recent array (normally sufficient for recent years).

## AI and news

The corresponding filing is parsed for bounded relevant excerpts. GDELT discovers recent English-language news inside the selected window; coverage is limited to roughly recent months. Older periods do not silently receive present-day news. Up to three accessible article bodies are fetched; paywalls and blocked articles are not bypassed. Headlines alone are listed for discovery but never supplied as explanatory evidence. GDELT timestamps indicate discovery and may differ from publication. Retrieval may include irrelevant news and is not comprehensive.

One Groq request generates all selected, available charts' explanations. Instructions distinguish facts, management statements, and inference, and require supplied source IDs. Source-ID validation cannot establish that each AI claim is true: inspect linked evidence. If no filing text or article is accessible, explanations should acknowledge insufficient evidence. Filing excerpts may omit material context. No forecast or trading recommendation is generated.

## Validation

```bash
python -m unittest discover -s tests -v
```

Tests cover cumulative-quarter conversion, Q4, restatement cutoffs, missing data, bridge reconciliation, dimensional parsing, and conservative disclosure availability.

## Source documentation

- SEC APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Groq models/quotas: https://console.groq.com/docs/models and https://console.groq.com/docs/rate-limits
- GDELT: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- yfinance: https://ranaroussi.github.io/yfinance/
- Streamlit: https://docs.streamlit.io/deploy/streamlit-community-cloud
