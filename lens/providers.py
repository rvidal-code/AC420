"""Free public data adapters. Network errors remain explicit to the UI."""
import ipaddress
import socket
import threading
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import streamlit as st

_SEC_LOCK = threading.Lock()
_SEC_LAST = 0.0


def sec_get(url, user_agent):
    global _SEC_LAST
    if not user_agent or "@" not in user_agent:
        raise ValueError("Set SEC_USER_AGENT to an app name and contact email in Secrets.")
    with _SEC_LOCK:
        time.sleep(max(0, 0.15 - (time.monotonic() - _SEC_LAST)))
        response = requests.get(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}, timeout=35)
        _SEC_LAST = time.monotonic()
    response.raise_for_status()
    return response


@st.cache_data(ttl=86400, show_spinner=False)
def companies(user_agent):
    return list(sec_get("https://www.sec.gov/files/company_tickers.json", user_agent).json().values())


@st.cache_data(ttl=3600, show_spinner=False)
def company_data(cik, user_agent):
    root = f"https://data.sec.gov"
    facts = sec_get(f"{root}/api/xbrl/companyfacts/CIK{int(cik):010d}.json", user_agent).json()
    submissions = sec_get(f"{root}/submissions/CIK{int(cik):010d}.json", user_agent).json()
    return facts, submissions, datetime.now(timezone.utc).isoformat()


def filing_list(submissions, cik):
    recent = submissions.get("filings", {}).get("recent", {})
    result = []
    for i, form in enumerate(recent.get("form", [])):
        if form not in ("10-Q", "10-K"):
            continue
        accn = recent["accessionNumber"][i]
        result.append({"form": form, "filed": recent["filingDate"][i], "end": recent["reportDate"][i],
                       "accn": accn, "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{recent['primaryDocument'][i]}"})
    return result


@st.cache_data(ttl=86400, show_spinner=False)
def filing_html(url, user_agent):
    return sec_get(url, user_agent).text


@st.cache_data(ttl=900, show_spinner=False)
def prices(ticker, start, end):
    import yfinance as yf
    frame = yf.Ticker(ticker.replace(".", "-")).history(start=start, end=end, auto_adjust=False)
    if frame.empty:
        return []
    return [{"date": str(idx.date()), "close": float(row["Close"])} for idx, row in frame.iterrows()]


def public_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.port not in (None, 443):
        raise ValueError("Only public HTTPS article URLs are supported.")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Non-public article address.")


def article_text(url):
    """Bounded fetch; validate every redirect. Never bypass article access controls."""
    for _ in range(4):
        public_url(url)
        with requests.get(url, timeout=8, allow_redirects=False, stream=True,
                          headers={"User-Agent": "FinancialLens educational research"}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", ""):
                return ""
            chunks, length = [], 0
            for chunk in response.iter_content(65536):
                chunks.append(chunk)
                length += len(chunk)
                if length >= 800000:
                    break
            soup = BeautifulSoup(b"".join(chunks), "lxml")
            for node in soup(["script", "style", "nav", "footer", "header"]):
                node.decompose()
            main = soup.find("article") or soup.find("main") or soup
            return " ".join(p.get_text(" ", strip=True) for p in main.find_all("p"))[:6000]
    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def news(name, start, end):
    # GDELT DOC has limited recent coverage; do not silently substitute current news.
    earliest = date.today() - timedelta(days=89)
    effective_start = max(date.fromisoformat(start), earliest)
    if date.fromisoformat(end) < earliest:
        return [], "News window is outside the free recent-news coverage. Filing evidence remains available."
    query_name = name.replace('"', '').replace("/", " ")
    response = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
        "query": f'"{query_name}" sourcelang:english', "mode": "artlist", "format": "json", "maxrecords": 8,
        "sort": "datedesc", "startdatetime": effective_start.strftime("%Y%m%d000000"),
        "enddatetime": date.fromisoformat(end).strftime("%Y%m%d235959")}, timeout=25)
    response.raise_for_status()
    articles = response.json().get("articles", [])
    result, seen = [], set()
    for article in articles:
        url = article.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        published = article.get("seendate", "")  # GDELT discovery timestamp, not claimed publication date.
        text = ""
        if len(result) < 3:
            try:
                text = article_text(url)
            except (requests.RequestException, ValueError, OSError):
                pass
        result.append({"title": article.get("title", "Article"), "url": url,
                       "observed": published, "text": text, "kind": "article" if len(text) > 200 else "headline only"})
    note = "News uses GDELT discovery dates; confirm publication dates in the linked articles."
    if effective_start.isoformat() != start:
        note += f" Coverage begins {effective_start}; earlier news in your window is unavailable."
    return result, note
