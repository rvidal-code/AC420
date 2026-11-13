"""Period-aware SEC companyfacts calculations. No missing values become zero."""
from datetime import date, timedelta

TAGS = {
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "Net income": ["NetIncomeLoss", "ProfitLoss"],
    "Operating income": ["OperatingIncomeLoss"],
    "Interest": ["InterestExpenseNonoperating", "InterestExpenseNonOperating", "InterestAndDebtExpense", "InterestExpense"],
    "Taxes": ["IncomeTaxExpenseBenefit"],
    "D&A": ["DepreciationDepletionAndAmortization", "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment", "DepreciationAmortizationAndAccretionNet"],
    "Operating cash flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "Capital expenditures": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "Cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "Debt": ["LongTermDebtCurrent", "LongTermDebtNoncurrent"],
}


def days(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def facts_for(company, tag, cutoff):
    return [r for r in company.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
            if r.get("form") in ("10-K", "10-Q", "10-K/A", "10-Q/A") and r.get("filed", "9999") <= cutoff]


def latest(rows):
    return max(rows, key=lambda r: (r.get("filed", ""), r.get("accn", "")), default=None)


def value(company, tags, start, end, cutoff, instant=False):
    """Return value and provenance. Quarterly YTD differences require a common start."""
    for tag in tags:
        rows = facts_for(company, tag, cutoff)
        direct = latest([r for r in rows if r.get("end") == end and
                         ((instant and "start" not in r) or (not instant and r.get("start") == start))])
        if direct:
            return direct["val"], [{"tag": tag, **direct}]
        if not instant and 70 <= days(start, end) <= 110:
            previous_end = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
            totals = sorted([r for r in rows if r.get("end") == end and r.get("start", start) < start],
                            key=lambda r: r.get("filed", ""), reverse=True)
            for total in totals:
                prior = latest([r for r in rows if r.get("start") == total["start"] and r.get("end") == previous_end])
                if prior:
                    return total["val"] - prior["val"], [{"tag": tag, **total}, {"tag": tag, **prior}]
    return None, []


def periods(company, mode, cutoff):
    result = set()
    for tag in TAGS["Revenue"] + TAGS["Net income"]:
        for r in facts_for(company, tag, cutoff):
            if not r.get("start"):
                continue
            duration = days(r["start"], r["end"])
            if mode == "Annual" and 350 <= duration <= 380:
                result.add((r["start"], r["end"]))
            elif mode == "Quarterly":
                if 70 <= duration <= 110:
                    result.add((r["start"], r["end"]))
                elif duration > 250:
                    # Q4 = full fiscal year less nine months, including 52/53-week calendars.
                    for p in facts_for(company, tag, cutoff):
                        if p.get("start") == r["start"] and 250 <= days(p["start"], p["end"]) <= 290:
                            start = (date.fromisoformat(p["end"]) + timedelta(days=1)).isoformat()
                            if 70 <= days(start, r["end"]) <= 110:
                                result.add((start, r["end"]))
    return sorted(result, key=lambda p: p[1], reverse=True)


def snapshot(company, period, cutoff):
    start, end = period
    values, sources = {}, {}
    for metric, tags in TAGS.items():
        if metric == "Debt":
            # Do not combine a total-debt tag with a current-debt tag.
            current, a = value(company, ["LongTermDebtCurrent"], start, end, cutoff, True)
            noncurrent, b = value(company, ["LongTermDebtNoncurrent"], start, end, cutoff, True)
            values[metric] = current + noncurrent if current is not None and noncurrent is not None else None
            sources[metric] = a + b
        else:
            values[metric], sources[metric] = value(company, tags, start, end, cutoff, metric == "Cash")
    components = [values.get(k) for k in ("Net income", "Interest", "Taxes", "D&A")]
    values["EBITDA"] = sum(components) if all(x is not None for x in components) else None
    ocf, capex = values["Operating cash flow"], values["Capital expenditures"]
    values["Free cash flow"] = ocf - capex if ocf is not None and capex is not None else None
    values["Net debt"] = values["Debt"] - values["Cash"] if values["Debt"] is not None and values["Cash"] is not None else None
    return {"start": start, "end": end, "values": values, "sources": sources}


def bridge(previous, current):
    if previous["values"].get("EBITDA") is None or current["values"].get("EBITDA") is None:
        return None
    keys = ["Net income", "Interest", "Taxes", "D&A"]
    return {"labels": [previous["end"]] + keys + [current["end"]],
            "values": [previous["values"]["EBITDA"]] + [current["values"][k] - previous["values"][k] for k in keys] + [current["values"]["EBITDA"]]}
