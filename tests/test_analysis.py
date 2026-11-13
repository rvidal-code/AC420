import json
import unittest
from unittest.mock import Mock, patch
from lens.analysis import explain


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        explain.clear()
        self.payload = json.dumps({"charts": {"Stock price": {}}, "sources": [{"id": "S1", "text": "Management stated that demand softened during the quarter due to lower orders."}]})

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
        item = {"what_changed": "Price fell", "explanation": "Management reported lower demand [S1].", "confidence": "low", "source_ids": ["S1"], "supporting_quote": "Management stated that demand softened during the quarter due to lower orders."}
        self.assertEqual(self.run_result(item), {"Stock price": item})

    def test_unverifiable_quote_cannot_support_a_causal_claim(self):
        item = {"what_changed": "Price fell", "explanation": "Invented driver [S1].", "confidence": "high", "source_ids": ["S1"], "supporting_quote": "This sentence was invented and does not occur in the source."}
        result = self.run_result(item)["Stock price"]
        self.assertEqual(result["confidence"], "low")
        self.assertIn("do not establish a specific cause", result["explanation"])
