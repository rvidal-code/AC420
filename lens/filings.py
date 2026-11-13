"""Read inline XBRL dimensions without asking a language model to invent numbers."""
import re
import warnings
from collections import defaultdict
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


def local(tag):
    return tag.name.split(":")[-1].lower() if tag.name else ""


def readable(name):
    text = name.split(":")[-1]
    text = re.sub(r"(Member|Axis)$", "", text)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)


def parse_inline(html):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    contexts = {}
    for node in soup.find_all(lambda t: local(t) == "context"):
        find = lambda name: node.find(lambda t: local(t) == name)
        end = find("enddate") or find("instant")
        start = find("startdate")
        dims = [(m.get("dimension", ""), m.get_text(strip=True)) for m in node.find_all(lambda t: local(t) == "explicitmember")]
        if end:
            contexts[node.get("id")] = {"start": start.get_text(strip=True) if start else None,
                                        "end": end.get_text(strip=True), "dims": dims}
    units = {}
    for unit in soup.find_all(lambda t: local(t) == "unit"):
        units[unit.get("id")] = unit.get_text(strip=True).lower()
    result = []
    for node in soup.find_all(lambda t: local(t) == "nonfraction"):
        context = contexts.get(node.get("contextref"))
        if not context or units.get(node.get("unitref"), "").split(":")[-1] != "usd":
            continue
        if node.get("format", "").split(":")[-1].lower() not in ("", "num-dot-decimal", "numdotdecimal"):
            continue
        try:
            raw = node.get_text("", strip=True).replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
            number = float(raw) * 10 ** int(node.get("scale", "0")) * (-1 if node.get("sign") == "-" else 1)
        except (ValueError, OverflowError):
            continue
        result.append({**context, "tag": node.get("name", ""), "value": number})
    for node in soup(["script", "style"]):
        node.decompose()
    # Prioritize MD&A and relevant notes over the cover page and table of contents.
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "div"]) if len(p.get_text(" ", strip=True)) > 100]
    keywords = re.compile(r"revenue|operating income|cash flow|maturit|interest expense|segment|depreciation|demand|margin", re.I)
    selected, seen = [], set()
    for p in paragraphs:
        if len(p) < 2500 and keywords.search(p) and p not in seen:
            selected.append(p)
            seen.add(p)
    def relevance(text):
        return sum(bool(re.search(pattern, text, re.I)) for pattern in [r"due to|driven by|primarily", r"increased|decreased|declined|grew", r"compared (with|to)", r"revenue|margin|cash flow"]) - int(bool(re.search(r"may adversely|could adversely", text, re.I)))
    selected.sort(key=relevance, reverse=True)
    return result, "\n".join(selected)[:18000]


def segments(facts, start, end, total):
    """Choose a single revenue tag/axis; require reconciliation with consolidated revenue."""
    if total is None or total <= 0:
        return []
    candidates = defaultdict(dict)
    for f in facts:
        tag = f["tag"].split(":")[-1].lower()
        if f["start"] != start or f["end"] != end or len(f["dims"]) != 1 or not any(k in tag for k in ("revenue", "netsales")):
            continue
        axis, member = f["dims"][0]
        if not any(k in axis.lower() for k in ("segment", "product", "geograph", "business")):
            continue
        if f["value"] > 0:
            candidates[(f["tag"], axis)][member] = f["value"]
    # Prefer operating/product segmentation to geography when both reconcile.
    ordered = sorted(candidates.items(), key=lambda item: ("geograph" in item[0][1].lower(), item[0]))
    for (tag, axis), members in ordered:
        if len(members) >= 2 and abs(sum(members.values()) - total) <= max(1, total * 0.015):
            return [{"segment": readable(k), "value": v, "axis": readable(axis), "tag": tag} for k, v in members.items()]
    return []


def maturities(facts, end):
    # Restrict to standard consolidated long-term debt repayment tags.
    suffixes = {"NextTwelveMonths": "Next 12 months", "YearTwo": "Year 2", "YearThree": "Year 3", "YearFour": "Year 4", "YearFive": "Year 5", "AfterYearFive": "After year 5"}
    found = {}
    for f in facts:
        if f["end"] != end or f["dims"]:
            continue
        tag = f["tag"].split(":")[-1]
        for suffix, label in suffixes.items():
            expected = "LongTermDebtMaturitiesRepaymentsOfPrincipal" + (suffix if suffix == "AfterYearFive" else "In" + suffix)
            if tag == expected:
                found[label] = f["value"]
    # Partial schedules are not presented as a complete repayment profile.
    return [{"maturity": label, "value": found[label]} for label in suffixes.values()] if len(found) == 6 else []
