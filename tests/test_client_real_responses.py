"""
Tests using real API response fixtures
=======================================

These tests mock HTTP calls with verbatim (sanitized) responses captured from
the live crypto.com Exchange API.  The goal is to exercise the full Pydantic
parsing pipeline against the actual shape the API returns — including quirks
that synthetic dicts in test_client.py might miss:

  * Numeric fields returned as JSON strings ("9.197", "360.41")
  * Extra fields the model ignores (journal_type, etc.)
  * Millisecond integer timestamps coerced to datetime

How to add a new fixture
------------------------
1. Capture a real API response JSON (e.g. via log_json_response_to_file=True).
2. Sanitize sensitive data: replace real account_id / order_id / client_oid
   values with placeholder UUIDs / numeric strings.
3. Save the file to tests/fixtures/<endpoint_name>.json keeping the full
   envelope:  {"id": ..., "method": ..., "code": 0, "result": {...}}
4. Add a test class below that loads the fixture with load_fixture() and
   asserts the parsed domain values you care about.
"""

import json
import pathlib
from typing import Any
from unittest import mock

import pytest
import pytz

from crypto_dot_com.client import CryptoAPI
from crypto_dot_com.enums import StatusEnum

# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture file from tests/fixtures/ and return it as a dict.

    The returned dict is the full API envelope
    (keys: id, method, code, result).
    """
    result: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text())
    return result


# ---------------------------------------------------------------------------
# Minimal mock response (mirrors test_client.py)
# ---------------------------------------------------------------------------


class MockResponse:
    def __init__(
        self, json_data: dict[str, Any], status_code: int = 200
    ) -> None:
        self.json_data = json_data
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict[str, Any]:
        return self.json_data


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------

_API_KEY = "test-api-key"
_API_SECRET = "test-api-secret"


@pytest.fixture
def client() -> CryptoAPI:
    return CryptoAPI(api_key=_API_KEY, api_secret=_API_SECRET)


# ---------------------------------------------------------------------------
# TestGetTradesRealResponse
# ---------------------------------------------------------------------------


class TestGetTradesRealResponse:
    """get_trades parsed against a sanitized real private/get-trades response.

    Key things being validated beyond what test_client.py covers:
    - traded_price / traded_quantity / fees come as strings in the API JSON
      but the model declares them as float — Pydantic must coerce them.
    - journal_type is an extra field not present in TradeHistoryDataMessage;
      it must be silently ignored (not raise a ValidationError).
    - create_time is an integer (milliseconds since epoch) that must be
      coerced to a timezone-aware datetime.
    - Negative fees are preserved correctly.
    """

    @mock.patch("requests.post")
    def test_correct_number_of_trades_returned(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        assert len(trades) == 3

    @mock.patch("requests.post")
    def test_string_price_coerced_to_float(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """The API returns traded_price as a JSON string; model must be
        float."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        assert isinstance(trades[0].traded_price, float)
        assert trades[0].traded_price == pytest.approx(9.197)
        assert trades[1].traded_price == pytest.approx(9.198)
        assert trades[2].traded_price == pytest.approx(9.199)

    @mock.patch("requests.post")
    def test_string_quantity_coerced_to_float(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        assert isinstance(trades[0].traded_quantity, float)
        assert trades[0].traded_quantity == pytest.approx(360.41)

    @mock.patch("requests.post")
    def test_negative_fees_parsed_correctly(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """Fees are negative strings in the API response (e.g. "-16.57")."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        assert trades[0].fees == pytest.approx(-16.57345385)
        assert trades[1].fees == pytest.approx(-6.05136420)
        assert trades[2].fees == pytest.approx(-1.80668360)
        for trade in trades:
            assert trade.fees < 0

    @mock.patch("requests.post")
    def test_millisecond_timestamp_coerced_to_datetime(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """create_time arrives as an int (ms epoch); model must produce a
        datetime.  The fixture value 1772092422307 ms = 2026-02-27."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        import datetime

        assert isinstance(trades[0].create_time, datetime.datetime)
        assert trades[0].create_time.year == 2026
        assert trades[0].create_time.month == 2

    @mock.patch("requests.post")
    def test_instrument_name_and_side(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        for trade in trades:
            assert trade.instrument_name == "LINK_USD"
            assert trade.side == "SELL"
            assert trade.fee_instrument_name == "USD"
            assert trade.taker_side == "TAKER"

    @mock.patch("requests.post")
    def test_match_count_values(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        assert trades[0].match_count == 2
        assert trades[1].match_count == 3
        assert trades[2].match_count == 1

    @mock.patch("requests.post")
    def test_all_trades_share_same_order_id(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """Multiple fills from one order share an order_id."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_trades.json")
        )

        trades = client.get_trades(
            start_time=1_772_092_000_000, end_time=1_772_093_000_000
        )

        order_ids = {t.order_id for t in trades}
        assert len(order_ids) == 1  # all fills belong to one order


# ---------------------------------------------------------------------------
# TestGetOrderHistoryRealResponse
# ---------------------------------------------------------------------------


class TestGetOrderHistoryRealResponse:
    """get_order_history parsed against a realistic private/get-order-history
    fixture.

    Validates that string-encoded numeric fields (quantity, order_value, etc.)
    are coerced to float and that enum fields (side, status, order_type) parse
    correctly from their string representations.
    """

    @mock.patch("requests.post")
    def test_correct_number_of_orders(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        assert len(orders) == 2

    @mock.patch("requests.post")
    def test_string_quantity_coerced_to_float(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        assert isinstance(orders[0].quantity, float)
        assert orders[0].quantity == pytest.approx(100.0)

    @mock.patch("requests.post")
    def test_status_enum_parsed(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """FILLED and CANCELED must map to the correct StatusEnum values."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        assert orders[0].status == StatusEnum.FILLED
        assert orders[1].status == StatusEnum.CANCELED

    @mock.patch("requests.post")
    def test_side_enum_parsed(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        from xarizmi.enums import SideEnum

        assert orders[0].side == SideEnum.BUY
        assert orders[1].side == SideEnum.SELL

    @mock.patch("requests.post")
    def test_exec_inst_parsed_from_json_string(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """exec_inst arrives as a JSON-encoded string "[]" and must be parsed
        into an empty list by the field_validator."""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        assert orders[0].exec_inst == []

    @mock.patch("requests.post")
    def test_optional_fee_rates_parsed(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_history.json")
        )

        orders = client.get_order_history(
            start_time=1_704_000_000_000, end_time=1_704_200_000_000
        )

        assert orders[0].maker_fee_rate == pytest.approx(0.001)
        assert orders[0].taker_fee_rate == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# TestCreateOrderRealResponse
# ---------------------------------------------------------------------------


class TestCreateOrderRealResponse:
    """create_limit_order parsed against a real private/create-order
    fixture."""

    @mock.patch("requests.post")
    def test_order_id_and_client_oid_parsed(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_create_order.json")
        )

        result = client.create_limit_order(
            instrument_name="CRO_USD",
            quantity="100.0",
            side="BUY",
            price="0.145",
        )

        assert result.order_id == "6531362339749152100"
        assert result.client_oid == "1704067200000"


# ---------------------------------------------------------------------------
# TestGetOrderDetailRealResponse
# ---------------------------------------------------------------------------


class TestGetOrderDetailRealResponse:
    """get_order_details and get_order_details_in_xarizmi against a real
    private/get-order-detail fixture."""

    @mock.patch("requests.post")
    def test_raw_order_fields(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_detail.json")
        )

        order = client.get_order_details(order_id="6531362339749152100")

        assert order.order_id == "6531362339749152100"
        assert order.instrument_name == "CRO_USD"
        assert order.status == StatusEnum.FILLED
        assert order.quantity == pytest.approx(100.0)
        assert order.order_value == pytest.approx(14.5)

    @mock.patch("requests.post")
    def test_xarizmi_conversion_computes_price(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """price = order_value / quantity = 14.5 / 100.0 = 0.145"""
        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_detail.json")
        )

        order = client.get_order_details_in_xarizmi(
            order_id="6531362339749152100"
        )

        assert order.price == pytest.approx(0.145)
        assert order.symbol.base_currency.name == "CRO"
        assert order.symbol.quote_currency.name == "USD"

    @mock.patch("requests.post")
    def test_xarizmi_status_maps_filled_to_done(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        from xarizmi.enums import OrderStatusEnum

        mock_post.return_value = MockResponse(
            load_fixture("private_get_order_detail.json")
        )

        order = client.get_order_details_in_xarizmi(
            order_id="6531362339749152100"
        )

        assert order.status == OrderStatusEnum.DONE


# ---------------------------------------------------------------------------
# TestGetUserBalanceRealResponse
# ---------------------------------------------------------------------------


class TestGetUserBalanceRealResponse:
    """get_user_balance and related methods against a realistic
    private/user-balance fixture.

    The fixture has string-encoded numeric fields (e.g. "28000.0") to match
    what the live API returns.
    """

    @mock.patch("requests.post")
    def test_string_balance_coerced_to_float(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """total_available_balance arrives as a string in the real API."""
        mock_post.return_value = MockResponse(
            load_fixture("private_user_balance.json")
        )

        balances = client.get_user_balance()

        assert isinstance(balances[0].total_available_balance, float)
        assert balances[0].total_available_balance == pytest.approx(28000.0)

    @mock.patch("requests.post")
    def test_position_balances_count(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_user_balance.json")
        )

        balances = client.get_user_balance()

        assert len(balances[0].position_balances) == 3

    @mock.patch("requests.post")
    def test_position_balance_quantity_coerced(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """position_balances[].quantity comes as a string from the API."""
        mock_post.return_value = MockResponse(
            load_fixture("private_user_balance.json")
        )

        balances = client.get_user_balance()

        btc = next(
            pb
            for pb in balances[0].position_balances
            if pb.instrument_name == "BTC"
        )
        assert isinstance(btc.quantity, float)
        assert btc.quantity == pytest.approx(0.25)
        assert btc.market_value == pytest.approx(25000.0)

    @mock.patch("requests.post")
    def test_summary_contains_all_currencies(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_user_balance.json")
        )

        items = client.get_user_balance_summary()

        names = {item.symbol.base_currency.name for item in items}
        assert names == {"BTC", "ETH", "USD"}

    @mock.patch("requests.post")
    def test_summary_market_values(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = MockResponse(
            load_fixture("private_user_balance.json")
        )

        items = client.get_user_balance_summary()
        by_name = {
            item.symbol.base_currency.name: item.market_value for item in items
        }

        assert by_name["BTC"] == pytest.approx(25000.0)
        assert by_name["ETH"] == pytest.approx(15000.0)
        assert by_name["USD"] == pytest.approx(3000.0)


# ---------------------------------------------------------------------------
# TestGetCandlestickRealResponse
# ---------------------------------------------------------------------------


class TestGetCandlestickRealResponse:
    """get_candlesticks parsed against a real public/get-candlestick fixture.

    OHLCV values come as strings in the API response; Pydantic must coerce
    them to float.  Timestamps are integers (ms) mapped to datetime.
    """

    @mock.patch("requests.get")
    def test_correct_number_of_candles(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_get.return_value = MockResponse(
            load_fixture("public_get_candlestick.json")
        )

        candles = client.get_candlesticks("BTC_USD", timeframe="1m")

        assert len(candles) == 3

    @mock.patch("requests.get")
    def test_string_ohlcv_coerced_to_float(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """o/h/l/c/v all arrive as strings; model must yield floats."""
        mock_get.return_value = MockResponse(
            load_fixture("public_get_candlestick.json")
        )

        candles = client.get_candlesticks("BTC_USD", timeframe="1m")

        c = candles[0]
        assert isinstance(c.open, float)
        assert c.open == pytest.approx(95000.0)
        assert c.high == pytest.approx(96200.5)
        assert c.low == pytest.approx(94800.0)
        assert c.close == pytest.approx(95500.0)
        assert c.volume == pytest.approx(12.5)

    @mock.patch("requests.get")
    def test_candles_are_datetime_aware(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """Each candle's datetime must be timezone-aware (UTC)."""
        mock_get.return_value = MockResponse(
            load_fixture("public_get_candlestick.json")
        )

        candles = client.get_candlesticks("BTC_USD", timeframe="1m")

        for candle in candles:
            assert candle.datetime is not None
            assert candle.datetime.tzinfo is not None
            assert candle.datetime.tzinfo == pytz.UTC

    @mock.patch("requests.get")
    def test_candle_timestamps_increase_by_one_minute(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """The fixture contains 1-minute candles; consecutive datetimes must
        differ by exactly 60 seconds."""
        import datetime

        mock_get.return_value = MockResponse(
            load_fixture("public_get_candlestick.json")
        )

        candles = client.get_candlesticks("BTC_USD", timeframe="1m")

        assert candles[0].datetime is not None
        assert candles[1].datetime is not None
        delta = candles[1].datetime - candles[0].datetime
        assert delta == datetime.timedelta(seconds=60)

    @mock.patch("requests.get")
    def test_candle_instrument_name_in_symbol(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_get.return_value = MockResponse(
            load_fixture("public_get_candlestick.json")
        )

        candles = client.get_candlesticks("BTC_USD", timeframe="1m")

        assert candles[0].symbol is not None
        assert candles[0].symbol.quote_currency.name == "BTC_USD"
