"""Tests for the WebSocket consumer."""
import unittest
from unittest.mock import MagicMock
from ingest.ws_consumer import trade_to_dict, quote_to_dict, agg_to_dict


class MockTrade:
    event_type = "T"
    symbol = "O:AAPL251219C00200000"
    exchange = 302
    price = 3.45
    size = 5
    conditions = [1, 2]
    timestamp = 1703001600000
    sequence_number = 12345


class MockQuote:
    event_type = "Q"
    symbol = "O:AAPL251219C00200000"
    bid_exchange = 301
    ask_exchange = 302
    bid_price = 3.40
    ask_price = 3.50
    bid_size = 15
    ask_size = 10
    timestamp = 1703001600000
    sequence_number = 12346


class MockAgg:
    event_type = "A"
    symbol = "O:AAPL251219C00200000"
    volume = 100
    accumulated_volume = 5000
    official_open_price = 3.20
    vwap = 3.42
    open = 3.30
    close = 3.45
    high = 3.80
    low = 3.10
    aggregate_vwap = 3.40
    average_size = 10
    start_timestamp = 1703001600000
    end_timestamp = 1703001601000


class TestTradeConversion(unittest.TestCase):
    def test_trade_to_dict(self):
        result = trade_to_dict(MockTrade())
        self.assertEqual(result["ev"], "T")
        self.assertEqual(result["sym"], "O:AAPL251219C00200000")
        self.assertEqual(result["p"], 3.45)
        self.assertEqual(result["s"], 5)
        self.assertEqual(result["q"], 12345)

    def test_quote_to_dict(self):
        result = quote_to_dict(MockQuote())
        self.assertEqual(result["ev"], "Q")
        self.assertEqual(result["bp"], 3.40)
        self.assertEqual(result["ap"], 3.50)

    def test_agg_to_dict(self):
        result = agg_to_dict(MockAgg())
        self.assertEqual(result["ev"], "A")
        self.assertEqual(result["v"], 100)
        self.assertEqual(result["vw"], 3.42)


if __name__ == "__main__":
    unittest.main()
