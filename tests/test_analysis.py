import json
import unittest
from unittest.mock import Mock, patch
from lens.analysis import explain


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        explain.clear()
        self.payload = json.dumps({"charts": {"Stock price": {}}, "sources": [{"id": "S1"}]})

    def run_result(self, item):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {"choices": [{"message": {"content": json.dumps({"charts": {"Stock price": item}})}}]}
        with patch("lens.analysis.requests.post", return_value=response):
            return explain(self.payload, "test-model", "fake-test-key")

    def test_uncited_explanation_rejected(self):
        self.assertEqual(self.run_result({"what_changed": "Price fell", "explanation": "No evidence.", "confidence": "low", "source_ids": []}), {})

    def test_unknown_inline_source_rejected(self):
        self.assertEqual(self.run_result({"what_changed": "Price fell", "explanation": "Evidence [S9]", "confidence": "low", "source_ids": ["S1"]}), {})

    def test_cited_explanation_accepted(self):
        item = {"what_changed": "Price fell", "explanation": "Cause is not established [S1].", "confidence": "low", "source_ids": ["S1"]}
        self.assertEqual(self.run_result(item), {"Stock price": item})
