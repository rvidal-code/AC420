import os
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class AppTests(unittest.TestCase):
    def test_setup_screen_without_secrets(self):
        with patch.dict(os.environ, {"SEC_USER_AGENT": "", "GROQ_API_KEY": ""}):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Connect SEC data" in item.value for item in app.info))

    def test_populated_dashboard_without_network(self):
        from lens import providers
        catalog = [{"ticker": "TEST", "title": "Test Company", "cik_str": 123}]
        rows = [{"start": "2024-01-01", "end": "2024-03-31", "val": 100e6, "form": "10-Q", "filed": "2024-05-01", "accn": "0000000123-24-000001"}]
        facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": rows}}}}}
        submissions = {"filings": {"recent": {"form": ["10-Q"], "accessionNumber": ["0000000123-24-000001"], "filingDate": ["2024-05-01"], "reportDate": ["2024-03-31"], "primaryDocument": ["test.htm"]}}}
        with patch.dict(os.environ, {"SEC_USER_AGENT": "Test test@example.com", "GROQ_API_KEY": ""}), \
             patch.object(providers, "companies", return_value=catalog), \
             patch.object(providers, "company_data", return_value=(facts, submissions, "2024-05-01T00:00:00Z")), \
             patch.object(providers, "filing_html", return_value="<html></html>"), \
             patch.object(providers, "prices", return_value=[]):
            app = AppTest.from_file(APP).run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "$100.0M")
        self.assertTrue(any(item.value == "Chart unavailable" for item in app.info))
