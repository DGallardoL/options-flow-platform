"""Tests for the REST poller."""
import unittest
from ingest.rest_poller import parse_option_symbol


class TestParseOptionSymbol(unittest.TestCase):
    def test_valid_call(self):
        result = parse_option_symbol("O:AAPL251219C00200000")
        self.assertIsNotNone(result)
        self.assertEqual(result["underlying"], "AAPL")
        self.assertEqual(result["expiration"], "2025-12-19")
        self.assertEqual(result["contract_type"], "call")
        self.assertEqual(result["strike"], 200.0)

    def test_valid_put(self):
        result = parse_option_symbol("O:TSLA260115P00150000")
        self.assertIsNotNone(result)
        self.assertEqual(result["underlying"], "TSLA")
        self.assertEqual(result["contract_type"], "put")
        self.assertEqual(result["strike"], 150.0)

    def test_invalid_symbol(self):
        result = parse_option_symbol("AAPL")
        self.assertIsNone(result)

    def test_fractional_strike(self):
        result = parse_option_symbol("O:SPY251219C00450500")
        self.assertIsNotNone(result)
        self.assertEqual(result["strike"], 450.5)


if __name__ == "__main__":
    unittest.main()
