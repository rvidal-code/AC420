import unittest
from lens.filings import parse_inline, segments, maturities


class FilingTests(unittest.TestCase):
    def test_segment_dimensions_and_scale(self):
        html = '''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
        <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
        <xbrli:context id="a"><xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">co:CloudMember</xbrldi:explicitMember></xbrli:context>
        <ix:nonFraction name="us-gaap:Revenues" contextRef="a" unitRef="usd" scale="6">40</ix:nonFraction></body></html>'''
        facts, _ = parse_inline(html)
        self.assertEqual(facts[0]["value"], 40e6)
        self.assertEqual(facts[0]["start"], "2024-01-01")
        self.assertEqual(facts[0]["dims"][0][1], "co:CloudMember")

    def test_segment_reconciliation_required(self):
        facts = [{"tag": "us-gaap:Revenues", "start": "2024-01-01", "end": "2024-03-31", "dims": [("BusinessSegmentsAxis", member)], "value": value} for member, value in [("A", 40), ("B", 60)]]
        self.assertEqual(len(segments(facts, "2024-01-01", "2024-03-31", 100)), 2)
        self.assertEqual(segments(facts, "2024-01-01", "2024-03-31", 200), [])

    def test_partial_maturities_unavailable(self):
        self.assertEqual(maturities([{"tag": "us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths", "end": "2024-12-31", "dims": [], "value": 10}], "2024-12-31"), [])

    def test_complete_maturity_schedule_includes_after_year_five(self):
        tails = ["InNextTwelveMonths", "InYearTwo", "InYearThree", "InYearFour", "InYearFive", "AfterYearFive"]
        facts = [{"tag": "us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipal" + tail, "end": "2024-12-31", "dims": [], "value": i} for i, tail in enumerate(tails)]
        result = maturities(facts, "2024-12-31")
        self.assertEqual(len(result), 6)
        self.assertEqual(result[-1], {"maturity": "After year 5", "value": 5})
