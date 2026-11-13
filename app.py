"""Streamlit entry point: run with streamlit run app.py."""
import json
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from lens import providers
from lens.analysis import explain
from lens.charts import NAMES, build
from lens.filings import parse_inline, segments, maturities
from lens.financials import periods, snapshot

st.set_page_config(page_title="Financial Lens", page_icon="◈", layout="wide")


def setting(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.environ.get(key, default)


def money(value):
    if value is None:
        return "—"
    return f"${value / 1e9:,.2f}B" if abs(value) >= 1e9 else f"${value / 1e6:,.1f}M"


def main():
    st.caption("FINANCIAL LENS  /  FILING-FIRST COMPANY RESEARCH")
    st.title("See the numbers. Understand the story.")
    st.markdown("Explore a company's financials, then follow the evidence behind each chart.")
    user_agent = setting("SEC_USER_AGENT")
    api_key = setting("GROQ_API_KEY")
    with st.sidebar:
        st.header("Your research desk")
        if not user_agent:
            st.info("Add SEC_USER_AGENT in Streamlit Secrets to connect SEC data.")
            user_agent = st.text_input("SEC contact (app name + email)", placeholder="Financial Lens name@example.com")
        mode = st.radio("Reporting frequency", ["Quarterly", "Annual"], horizontal=True)
        selection = st.multiselect("Chart library", NAMES, default=NAMES[:4])
        ai_enabled = st.toggle("Automatic AI explanations", value=True)
        st.caption("Data refresh: filings hourly · prices every 15 minutes. Prices may be delayed; financials update with filings.")
    if not user_agent:
        st.info("Connect SEC data using the sidebar or app Secrets. No paid financial API is required.")
        with st.expander("What you can explore", expanded=True):
            st.write("EBITDA bridges · Revenue segmentation · Stock prices · Debt maturities · Profitability · Cash flow · Leverage")
            st.write("Every financial chart uses reported USD figures. Unsupported disclosures display ‘Chart unavailable.’")
        return
    try:
        catalog = providers.companies(user_agent)
    except Exception as error:
        st.error("SEC company search is unavailable. Verify your SEC contact and try again.")
        with st.expander("Connection details"):
            st.text(str(error))
        return
    labels = {f"{c['ticker']} — {c['title']}": c for c in catalog}
    default = next((i for i, c in enumerate(catalog) if c["ticker"] == "AAPL"), 0)
    label = st.selectbox("Find a U.S. public company", list(labels), index=default)
    company = labels[label]
    with st.spinner("Reading the latest SEC financial data…"):
        try:
            facts, submissions, retrieved = providers.company_data(company["cik_str"], user_agent)
        except Exception as error:
            st.error(f"Financial data unavailable: {error}")
            return
    filings = providers.filing_list(submissions, company["cik_str"])
    available = periods(facts, mode, date.today().isoformat())
    available = [p for p in available if any(f["end"] == p[1] for f in filings)]
    if not available:
        st.info("Chart unavailable — no supported USD reporting periods were found.")
        return
    c1, c2 = st.columns([2, 1])
    with c1:
        period = st.selectbox("Reporting period", available[:24], format_func=lambda p: f"{p[0]} → {p[1]}")
    with c2:
        comparison = st.selectbox("EBITDA comparison", ["Previous period", "Same period last year"])
    filing = min([f for f in filings if f["end"] == period[1]], key=lambda f: f["filed"])
    cutoff = filing["filed"]
    # Historical views never incorporate facts filed after the selected filing.
    eligible = periods(facts, mode, cutoff)
    history = [snapshot(facts, p, cutoff) for p in eligible if p[1] <= period[1]][:12]
    current = snapshot(facts, period, cutoff)
    earlier = [p for p in eligible if p[1] < period[1]]
    if comparison == "Same period last year":
        earlier = [p for p in earlier if 350 <= (date.fromisoformat(period[1]) - date.fromisoformat(p[1])).days <= 380]
    prior_period = earlier[0] if earlier else None
    if prior_period and comparison == "Previous period" and (date.fromisoformat(period[0]) - date.fromisoformat(prior_period[1])).days != 1:
        prior_period = None
    previous = snapshot(facts, prior_period, cutoff) if prior_period else None
    st.subheader(company["title"])
    st.caption(f"{filing['form']} filed {cutoff} · Period ended {period[1]} · Retrieved {retrieved[:19]} UTC")
    st.link_button("Open corresponding SEC filing ↗", filing["url"])
    cols = st.columns(4)
    for col, key in zip(cols, ["Revenue", "Net income", "EBITDA", "Free cash flow"]):
        col.metric(key, money(current["values"][key]))
    st.caption("EBITDA = net income + reported interest expense + income tax expense + D&A. Unadjusted, non-GAAP calculation; cash-flow D&A can include items beyond depreciation and amortization. FCF = operating cash flow − capital expenditures.")
    with st.sidebar:
        st.divider()
        st.subheader("Evidence window")
        news_start = st.date_input("News from", value=date.fromisoformat(period[0]), max_value=date.today())
        news_end = st.date_input("News through", value=date.fromisoformat(cutoff), max_value=date.today())
        st.caption("Default: reporting period through filing date. Free news coverage is limited to recent months.")
    if news_start > news_end:
        st.error("News start date must precede its end date.")
        return
    inline, filing_text = [], ""
    needs_filing = ai_enabled or any(n in selection for n in ("Revenue segmentation", "Debt maturities"))
    if needs_filing:
        try:
            with st.spinner("Reading filing disclosures…"):
                inline, filing_text = parse_inline(providers.filing_html(filing["url"], user_agent))
        except Exception:
            st.warning("Filing document could not be retrieved. Structured financial data remains available; disclosure charts and filing commentary may be unavailable.")
    seg = segments(inline, *period, current["values"]["Revenue"])
    debt = maturities(inline, period[1])
    price_data = []
    if "Stock price" in selection:
        try:
            price_data = providers.prices(company["ticker"], period[0], (date.fromisoformat(cutoff) + timedelta(days=1)).isoformat())
        except Exception:
            pass
    figures, chart_data = {}, {}
    for name in selection:
        fig, data = build(name, history, current, previous, seg, debt, price_data)
        figures[name] = fig
        if fig is not None:
            chart_data[name] = data
    sources = [{"id": "S1", "title": f"{company['ticker']} {filing['form']} filed {cutoff}", "url": filing["url"],
                "kind": "filing excerpt" if filing_text else "filing metadata only", "text": filing_text}]
    # Include URLs for all facts used, including derived quarters and older comparison periods.
    accession_numbers = {r["accn"] for p in history + [current] + ([previous] if previous else []) for rows in p["sources"].values() for r in rows}
    fact_sources = [{"accn": a, "url": f"https://www.sec.gov/Archives/edgar/data/{int(company['cik_str'])}/{a.replace('-', '')}/{a}-index.html"} for a in sorted(accession_numbers)]
    # Show visuals immediately; news retrieval and AI must not block the charts.
    explanation_slots = {}
    for name in selection:
        with st.container(border=True):
            st.subheader(name)
            if figures[name] is None:
                st.info("Chart unavailable")
                continue
            st.plotly_chart(figures[name], use_container_width=True, key=name)
            if name == "EBITDA bridge":
                st.caption("Accounting-component reconciliation. Bars explain the mathematical change; they do not establish operational causes.")
            if name == "Stock price":
                st.caption("Daily unadjusted closing price via Yahoo Finance / yfinance. Window: period start through filing date. Educational use; not a live quote feed.")
            if name == "Debt maturities":
                st.caption(f"Principal repayment buckets as disclosed at {period[1]}; excludes lease payment schedules.")
            explanation_slots[name] = st.empty()
            if ai_enabled and api_key:
                explanation_slots[name].caption("Preparing the evidence-based explanation…")
    explanations, news_items, news_note = {}, [], ""
    if ai_enabled and api_key and chart_data:
        with st.spinner("Gathering news and explaining your charts…"):
            try:
                news_items, news_note = providers.news(company["title"].split(" INC")[0].split(" CORP")[0], news_start.isoformat(), news_end.isoformat())
            except Exception:
                news_note = "News service unavailable. Explanations use filing evidence and chart figures only."
            for n in news_items:
                if n["kind"] == "article":
                    sources.append({"id": f"S{len(sources) + 1}", **n})
            try:
                # Bound the evidence budget so a public class demo conserves free-tier tokens.
                ai_sources = [{**source, "text": source.get("text", "")[:(4500 if source["id"] == "S1" else 1000)]} for source in sources[:3]]
                payload = {"company": company["title"], "period": period, "filing_date": cutoff,
                           "comparison": prior_period, "charts": chart_data, "sources": ai_sources,
                           "news_window": [news_start.isoformat(), news_end.isoformat()], "news_coverage": news_note}
                explanations = explain(json.dumps(payload, sort_keys=True), setting("GROQ_MODEL", "openai/gpt-oss-20b"), api_key)
            except Exception as error:
                st.warning(f"AI explanations unavailable: {error}")
    elif ai_enabled and not api_key:
        st.info("Charts are ready. Add GROQ_API_KEY in app Secrets to enable automatic explanations.")
    if news_note:
        st.caption(news_note)
    for name in selection:
        if name not in explanation_slots:
            continue
        with explanation_slots[name].container():
            item = explanations.get(name)
            if item:
                st.markdown("**What changed**")
                if name == "EBITDA bridge":
                    data = chart_data[name]
                    st.write(f"EBITDA moved from {money(data['previous_EBITDA_USD'])} ({data['previous_period']}) to {money(data['current_EBITDA_USD'])} ({data['current_period']}).")
                elif name == "Stock price":
                    data = chart_data[name]
                    st.write(f"Closing price moved from ${data['start']['close']:,.2f} ({data['start']['date']}) to ${data['end']['close']:,.2f} ({data['end']['date']}).")
                elif name == "Debt maturities":
                    data = chart_data[name]
                    largest = max(data, key=lambda row: row["value"])
                    st.write(f"At {period[1]}, {money(data[0]['value'])} falls due in the next 12 months. The largest disclosed repayment bucket is {largest['maturity']} ({money(largest['value'])}).")
                elif name == "Revenue segmentation":
                    st.write(f"Reported revenue of {money(current['values']['Revenue'])} is divided into {len(chart_data[name])} disclosed categories for the selected period.")
                elif name == "Free cash flow":
                    st.write(f"Operating cash flow of {money(current['values']['Operating cash flow'])}, less capital expenditures of {money(current['values']['Capital expenditures'])}, gives free cash flow of {money(current['values']['Free cash flow'])}.")
                elif name == "Revenue & profitability":
                    st.write(f"For the selected period, revenue is {money(current['values']['Revenue'])} and net income is {money(current['values']['Net income'])}.")
                elif name == "Liquidity & leverage":
                    st.write(f"At {period[1]}, cash is {money(current['values']['Cash'])} and disclosed long-term debt including its current portion is {money(current['values']['Debt'])}.")
                else:
                    st.write(item["what_changed"])
                st.markdown("**What explains it**")
                st.write(item["explanation"])
                if item.get("supporting_quote"):
                    with st.expander("Supporting source excerpt"):
                        st.write(item["supporting_quote"])
                st.caption(f"AI evidence confidence: {item['confidence']}. Check the underlying sources.")
                for source in sources:
                    if source["id"] in item["source_ids"]:
                        st.link_button(f"[{source['id']}] {source['title']}", source["url"])
            elif ai_enabled and api_key:
                st.caption("No validated AI explanation is available for this chart.")
    with st.expander("Source ledger & downloadable data"):
        st.write("Numbers use SEC standard US-GAAP USD facts available as of the selected filing date. Quarterly cash flows and Q4 may be calculated from cumulative figures. Later restatements are excluded. A missing figure is never assumed to be zero.")
        rows = []
        for p in history:
            for metric, value in p["values"].items():
                rows.append({"start": p["start"], "end": p["end"], "metric": metric, "USD": value})
        st.download_button("Download financial data CSV", pd.DataFrame(rows).to_csv(index=False), f"{company['ticker']}-{mode.lower()}.csv", "text/csv")
        st.download_button("Download fact provenance JSON", json.dumps({"history": history, "current": current, "previous": previous, "filings": fact_sources}, indent=2), "provenance.json", "application/json")
        for f in fact_sources:
            st.link_button(f["accn"], f["url"])
        for n in news_items:
            st.link_button(f"{n['title']} ({n['kind']})", n["url"])
    st.caption("Financial Lens · A class research project · Financial statement data is periodic, not real-time. Chart availability varies by company and filing.")


if __name__ == "__main__":
    main()
