import pytest
from src.tools.agent_utils import QueryParser

def test_extract_anchor_date():
    qp = QueryParser(market_sectors={})
    details = qp.extract_query_details("Show AVWAP since 2025-05-01 for AAPL")
    assert details["anchor"] == "2025-05-01"

def test_extract_anchor_keyword():
    qp = QueryParser(market_sectors={})
    details = qp.extract_query_details("AVWAP from earnings on AAPL")
    assert details["anchor"] == "earnings"
