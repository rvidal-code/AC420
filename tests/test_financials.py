import unittest
from lens.financials import value, periods, snapshot, bridge


def company(rows, tag="Revenues"):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": rows}}}}}


def row(start, end, val, filed="2025-02-01"):
    return {"start": start, "end": end, "val": val, "form": "10-K", "filed": filed, "accn": "test"}


class FinancialTests(unittest.TestCase):
    def test_q4_subtracts_nine_months(self):
        c = company([row("2024-01-01", "2024-12-31", 400), row("2024-01-01", "2024-09-30", 280)])
        self.assertIn(("2024-10-01", "2024-12-31"), periods(c, "Quarterly", "2025-02-01"))
        self.assertEqual(value(c, ["Revenues"], "2024-10-01", "2024-12-31", "2025-02-01")[0], 120)

    def test_cash_flow_quarter_is_not_ytd(self):
        c = company([row("2024-01-01", "2024-06-30", 90), row("2024-01-01", "2024-03-31", 40)], "NetCashProvidedByUsedInOperatingActivities")
        self.assertEqual(value(c, ["NetCashProvidedByUsedInOperatingActivities"], "2024-04-01", "2024-06-30", "2025-02-01")[0], 50)

    def test_future_restatement_excluded(self):
        c = company([row("2024-01-01", "2024-03-31", 40), row("2024-01-01", "2024-03-31", 99, "2026-01-01")])
        self.assertEqual(value(c, ["Revenues"], "2024-01-01", "2024-03-31", "2025-02-01")[0], 40)

    def test_mismatched_ytd_starts_not_subtracted(self):
        c = company([row("2024-01-01", "2024-06-30", 90), row("2024-01-02", "2024-03-31", 40)])
        self.assertIsNone(value(c, ["Revenues"], "2024-04-01", "2024-06-30", "2025-02-01")[0])

    def test_missing_components_not_zero(self):
        s = snapshot(company([]), ("2024-01-01", "2024-03-31"), "2025-02-01")
        self.assertIsNone(s["values"]["EBITDA"])
        self.assertIsNone(bridge(s, s))

    def test_bridge_reconciles(self):
        a = {"end": "2024-03-31", "values": {"Net income": 10, "Interest": 2, "Taxes": 3, "D&A": 5, "EBITDA": 20}}
        b = {"end": "2024-06-30", "values": {"Net income": 20, "Interest": 1, "Taxes": 4, "D&A": 7, "EBITDA": 32}}
        data = bridge(a, b)
        self.assertEqual(sum(data["values"][:-1]), data["values"][-1])


if __name__ == "__main__":
    unittest.main()
