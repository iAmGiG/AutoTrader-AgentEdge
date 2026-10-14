"""Every message the API error translator shows must exist in cli_messages.yaml."""

import re
from pathlib import Path

import pytest

from config_defaults.message_loader import MessageLoader

from src.trading.broker.api_error_translator import APIErrorTranslator

TRANSLATOR = Path(__file__).resolve().parents[3] / "src/trading/broker/api_error_translator.py"
KEYS = sorted(set(re.findall(r'_MSG\.get\(\s*"([a-z_.]+)"', TRANSLATOR.read_text())))
FORMAT_ARGS = {
    "ticker": "SPY",
    "entry": "$660.00",
    "stop": "$628.10",
    "target": "$712.80",
    "base": "$631.2",
}


def test_translator_keys_found():
    assert len(KEYS) == 12


@pytest.mark.parametrize("key", KEYS)
def test_translator_message_exists(key):
    text = MessageLoader().get(key, **FORMAT_ARGS)

    assert not text.startswith(("[Missing message", "[Invalid path")), text


@pytest.mark.parametrize(
    "api_error, title",
    [
        (
            '{"code": 42210000, "message": "stop_loss.stop_price must be <= base_price - 0.01",'
            ' "base_price": "631.2"}',
            "Order rejected: Stop loss price ($628.10) doesn't match market price",
        ),
        (
            '{"code": 40310000, "message": "insufficient buying power"}',
            "Order rejected: Not enough cash available",
        ),
        ('{"code": 40010001, "message": "market is closed"}', "Order rejected: Market is closed"),
        ('{"code": 1, "message": "something else"}', "Order failed for SPY"),
    ],
)
def test_translate_shows_real_messages(api_error, title):
    shown_title, detail = APIErrorTranslator.translate(
        api_error, "SPY", entry=660.0, stop=628.10, target=712.80
    )

    assert shown_title == title
    assert not detail.startswith("[")
