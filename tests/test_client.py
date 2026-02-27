"""
Unit tests for crypto_dot_com/client.py
========================================

CryptoAPI is the primary interface for communicating with the crypto.com
Exchange REST API v1 (https://api.crypto.com/exchange/v1).

All HTTP calls are intercepted with unittest.mock, so no real credentials or
internet connection are required.

Test classes
------------
TestGetXarizmiSymbol            Module-level helper that parses "BASE_QUOTE"
                                instrument names into xarizmi Symbol objects.

TestCryptoAPIInit               Constructor defaults and custom attribute
                                values.

TestGetOrderHistory             get_order_history – normal path and the
                                recursive pagination logic triggered when the
                                API returns exactly `limit` records.
                                get_all_order_history_of_a_day – date-based
                                convenience wrapper.

TestCreateOrder                 create_limit_order – raw API call.
                                create_buy_limit_order_xarizmi and
                                create_sell_limit_order_xarizmi – wrappers
                                that return xarizmi Order objects.

TestCancelOrder                 cancel_all_orders and cancel_order – fire-and-
                                forget calls that send a signed POST and
                                discard the response.

TestGetOrderDetails             get_order_details – raw response parsing.
                                get_order_details_in_xarizmi – conversion to
                                xarizmi Order including price computation.

TestGetCandlesticks             get_candlesticks – public GET endpoint,
                                optional timestamp parameters.
                                get_all_candlesticks – pagination loop that
                                stops when the API returns no data; string
                                interval parsing (enum name and value).

TestGetUserBalance              get_user_balance – raw balance messages.
                                get_user_balance_summary – conversion to
                                xarizmi PortfolioItem objects.
                                get_current_portfolio – Portfolio wrapper.

TestGetUserBalanceSummaryAsDf   get_user_balance_summary_as_df – DataFrame
                                structure, sort order, percentage column,
                                optional columns.

TestErrorHandling               API error codes 213, 308, 315 and unknown
                                codes; non-2xx public GET response.
"""

import datetime
import json
from typing import Any
from unittest import mock

import pytest
import pytz
from xarizmi.enums import OrderStatusEnum
from xarizmi.enums import SideEnum

from crypto_dot_com.client import CryptoAPI
from crypto_dot_com.client import get_xarizmi_symbol_from_instrument_name
from crypto_dot_com.data_models.response import CreateOrderDataMessage
from crypto_dot_com.enums import CandlestickTimeInterval
from crypto_dot_com.exceptions import BadPriceException
from crypto_dot_com.exceptions import BadQuantityException

# ---------------------------------------------------------------------------
# Mock infrastructure
# ---------------------------------------------------------------------------


class MockResponse:
    """Minimal stand-in for requests.Response.

    The ``ok`` property mirrors requests.Response behaviour by returning True
    for any 2xx status code, which is what _get_public and _post inspect.
    """

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
# Shared fixture data
# ---------------------------------------------------------------------------

_API_KEY = "test-api-key"
_API_SECRET = "test-api-secret"

# Minimal dict that satisfies OrderHistoryDataMessage validation.
_ORDER_HISTORY_ITEM: dict[str, Any] = {
    "account_id": "acc-001",
    "order_id": "ord-001",
    "client_oid": "clt-001",
    "order_type": "LIMIT",
    "time_in_force": "GOOD_TILL_CANCEL",
    "side": "BUY",
    "exec_inst": "[]",
    "quantity": 100.0,
    "order_value": 14.0,
    "avg_price": 0.14,
    "ref_price": 0.0,
    "cumulative_quantity": 0.0,
    "cumulative_value": 0.0,
    "cumulative_fee": 0.0,
    "status": "ACTIVE",
    "update_user_id": "user-001",
    "order_date": "2024-01-01",
    "instrument_name": "CRO_USD",
    "fee_instrument_name": "CRO",
    "reason": 0,
    "create_time": 1704067200000,
    "create_time_ns": 1704067200000000000.0,
    "update_time": 1704067200001,
}

# One OHLCV candle covering 2024-01-01 00:00 UTC.
_CANDLESTICK_ITEM: dict[str, Any] = {
    "o": 50000.0,
    "h": 51000.0,
    "l": 49000.0,
    "c": 50500.0,
    "v": 10.5,
    "t": 1704067200000,
}

# A single account with two position balances (BTC and ETH).
_BALANCE_ITEM: dict[str, Any] = {
    "total_available_balance": 28000.0,
    "total_margin_balance": 28000.0,
    "total_initial_margin": 0.0,
    "total_haircut": 0.0,
    "total_position_im": 0.0,
    "total_maintenance_margin": 0.0,
    "total_position_cost": 0.0,
    "total_cash_balance": 28000.0,
    "total_collateral_value": 28000.0,
    "total_session_unrealized_pnl": 0.0,
    "instrument_name": "USD",
    "total_session_realized_pnl": 0.0,
    "position_balances": [
        {
            "quantity": 0.5,
            "reserved_qty": 0.0,
            "collateral_amount": 0.0,
            "haircut": 0.0,
            "collateral_eligible": False,
            "market_value": 25000.0,
            "max_withdrawal_balance": 0.5,
            "instrument_name": "BTC",
            "hourly_interest_rate": 0.0,
        },
        {
            "quantity": 10.0,
            "reserved_qty": 0.0,
            "collateral_amount": 0.0,
            "haircut": 0.0,
            "collateral_eligible": False,
            "market_value": 3000.0,
            "max_withdrawal_balance": 10.0,
            "instrument_name": "ETH",
            "hourly_interest_rate": 0.0,
        },
    ],
    "credit_limits": [],
    "total_effective_leverage": 0.0,
    "position_limit": 0.0,
    "used_position_limit": 0.0,
    "total_borrow": 0.0,
    "margin_score": 0.0,
    "is_liquidating": False,
    "has_risk": False,
    "terminatable": False,
}


# ---------------------------------------------------------------------------
# Helper factories for mock responses
# ---------------------------------------------------------------------------


def _post_ok(result: Any, method: str = "private/test") -> MockResponse:
    """Wrap *result* in a successful (HTTP 200) API response envelope."""
    return MockResponse(
        {"id": 1, "method": method, "code": 0, "result": result}
    )


def _get_ok(result: Any, method: str = "public/test") -> MockResponse:
    """Wrap *result* in a successful (HTTP 200) public GET response
    envelope."""
    return MockResponse(
        {"id": 1, "method": method, "code": 0, "result": result}
    )


def _error(code: int, message: str) -> MockResponse:
    """Return an HTTP 400 response carrying an API-level error code."""
    return MockResponse(
        {"id": 1, "method": "private/test", "code": code, "message": message},
        status_code=400,
    )


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> CryptoAPI:
    """A CryptoAPI instance with dummy credentials and logging disabled."""
    return CryptoAPI(api_key=_API_KEY, api_secret=_API_SECRET)


# ---------------------------------------------------------------------------
# TestGetXarizmiSymbol
# ---------------------------------------------------------------------------


class TestGetXarizmiSymbol:
    """Tests for get_xarizmi_symbol_from_instrument_name.

    This function splits a crypto.com instrument name (e.g. "BTC_USD") into
    its base and quote currencies and builds a xarizmi Symbol.
    """

    def test_parses_base_currency(self) -> None:
        symbol = get_xarizmi_symbol_from_instrument_name("BTC_USD")
        assert symbol.base_currency.name == "BTC"

    def test_parses_quote_currency(self) -> None:
        symbol = get_xarizmi_symbol_from_instrument_name("BTC_USD")
        assert symbol.quote_currency.name == "USD"

    def test_exchange_name_is_crypto_dot_com(self) -> None:
        symbol = get_xarizmi_symbol_from_instrument_name("ETH_USDT")
        assert symbol.exchange is not None
        assert symbol.exchange.name == "crypto.com"

    def test_works_with_various_pairs(self) -> None:
        symbol = get_xarizmi_symbol_from_instrument_name("CRO_USD")
        assert symbol.base_currency.name == "CRO"
        assert symbol.quote_currency.name == "USD"


# ---------------------------------------------------------------------------
# TestCryptoAPIInit
# ---------------------------------------------------------------------------


class TestCryptoAPIInit:
    """Tests for CryptoAPI.__init__."""

    def test_stores_api_key_and_secret(self, client: CryptoAPI) -> None:
        assert client.api_key == _API_KEY
        assert client.api_secret == _API_SECRET

    def test_log_to_file_defaults_to_false(self, client: CryptoAPI) -> None:
        assert client.log_json_response_to_file is False

    def test_logs_directory_defaults_to_none(self, client: CryptoAPI) -> None:
        assert client.logs_directory is None

    def test_custom_timeout_is_stored(self) -> None:
        c = CryptoAPI(api_key="k", api_secret="s", timeout=500)
        assert c._timeout == 500

    def test_logging_options_stored(self) -> None:
        c = CryptoAPI(
            api_key="k",
            api_secret="s",
            log_json_response_to_file=True,
            logs_directory="/tmp/logs",
        )
        assert c.log_json_response_to_file is True
        assert c.logs_directory == "/tmp/logs"


# ---------------------------------------------------------------------------
# TestGetOrderHistory
# ---------------------------------------------------------------------------


class TestGetOrderHistory:
    """Tests for get_order_history and get_all_order_history_of_a_day.

    get_order_history fetches paginated order history via a signed POST.
    When the API returns exactly `limit` records the client assumes there may
    be more and recursively splits the time range in two, making two further
    requests for each half-interval until a partial page is received.
    """

    @mock.patch("requests.post")
    def test_returns_parsed_orders(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_ORDER_HISTORY_ITEM]},
            method="private/get-order-history",
        )

        orders = client.get_order_history(start_time=1000, end_time=2000)

        assert len(orders) == 1
        assert orders[0].order_id == "ord-001"
        assert orders[0].instrument_name == "CRO_USD"

    @mock.patch("requests.post")
    def test_instrument_name_forwarded_in_request_body(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """The instrument_name filter must appear in the signed JSON body."""
        mock_post.return_value = _post_ok(
            {"data": [_ORDER_HISTORY_ITEM]},
            method="private/get-order-history",
        )

        client.get_order_history(
            start_time=1000,
            end_time=2000,
            instrument_name="CRO_USD",
        )

        body = json.loads(mock_post.call_args[1]["data"])
        assert body["params"]["instrument_name"] == "CRO_USD"

    @mock.patch("requests.post")
    def test_recurses_when_result_count_equals_limit(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """Receiving exactly `limit` records triggers two recursive calls that
        cover the first and second halves of the original time range.

        The implementation discards the full-page results and re-fetches from
        each half, so the final result is the sum of the two sub-calls.
        """
        limit = 2
        full_page = {"data": [_ORDER_HISTORY_ITEM] * limit}
        one_item = {"data": [_ORDER_HISTORY_ITEM]}

        # First call hits the limit → two recursive half-range calls,
        # each returning one item (below the limit).
        mock_post.side_effect = [
            _post_ok(full_page, "private/get-order-history"),
            _post_ok(one_item, "private/get-order-history"),
            _post_ok(one_item, "private/get-order-history"),
        ]

        orders = client.get_order_history(
            start_time=1000, end_time=3000, limit=limit
        )

        assert mock_post.call_count == 3
        assert len(orders) == 2  # 1 from first half + 1 from second half

    @mock.patch.object(CryptoAPI, "get_order_history", return_value=[])
    def test_get_all_order_history_of_a_day_passes_instrument_name(
        self, mock_history: mock.Mock, client: CryptoAPI
    ) -> None:
        """The day-based wrapper must forward instrument_name to
        get_order_history."""
        client.get_all_order_history_of_a_day(
            day=datetime.date(2024, 1, 15),
            instrument_name="BTC_USD",
        )

        mock_history.assert_called_once()
        _, kwargs = mock_history.call_args
        assert kwargs.get("instrument_name") == "BTC_USD"

    @mock.patch.object(CryptoAPI, "get_order_history", return_value=[])
    def test_get_all_order_history_of_a_day_calls_get_order_history(
        self, mock_history: mock.Mock, client: CryptoAPI
    ) -> None:
        client.get_all_order_history_of_a_day(day=datetime.date(2024, 3, 1))
        mock_history.assert_called_once()


# ---------------------------------------------------------------------------
# TestCreateOrder
# ---------------------------------------------------------------------------


class TestCreateOrder:
    """Tests for create_limit_order, create_buy_limit_order_xarizmi,
    and create_sell_limit_order_xarizmi.

    create_limit_order sends a signed POST and parses the order ID from the
    response.  The xarizmi wrappers additionally build a xarizmi Order with
    the correct side, status, and symbol.
    """

    @mock.patch("requests.post")
    def test_create_limit_order_returns_order_ids(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"client_oid": "clt-999", "order_id": "ord-999"},
            method="private/create-order",
        )

        result = client.create_limit_order(
            instrument_name="CRO_USD",
            quantity=100,
            side="BUY",
            price=0.14,
        )

        assert result.order_id == "ord-999"
        assert result.client_oid == "clt-999"

    @mock.patch("requests.post")
    def test_create_limit_order_accepts_float_inputs(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """quantity and price may be floats; the client converts them to
        strings before serialising the request."""
        mock_post.return_value = _post_ok(
            {"client_oid": "clt-1", "order_id": "ord-1"}
        )

        result = client.create_limit_order(
            instrument_name="BTC_USD",
            quantity=0.001,
            side="SELL",
            price=50000.0,
        )

        assert result.order_id == "ord-1"

    @mock.patch.object(CryptoAPI, "create_limit_order")
    def test_create_buy_limit_order_xarizmi_sets_side_and_status(
        self, mock_create: mock.Mock, client: CryptoAPI
    ) -> None:
        """The BUY wrapper must call create_limit_order with side=BUY and
        return a xarizmi Order with status=ACTIVE."""
        mock_create.return_value = CreateOrderDataMessage(
            client_oid="clt-1", order_id="ord-buy-1"
        )

        order = client.create_buy_limit_order_xarizmi(
            instrument_name="CRO_USD",
            quantity=100,
            price=0.14,
        )

        mock_create.assert_called_once_with(
            instrument_name="CRO_USD",
            quantity=100,
            side=SideEnum.BUY.name,
            price=0.14,
        )
        assert order.order_id == "ord-buy-1"
        assert order.side == SideEnum.BUY
        assert order.status == OrderStatusEnum.ACTIVE

    @mock.patch.object(CryptoAPI, "create_limit_order")
    def test_create_buy_limit_order_xarizmi_builds_symbol(
        self, mock_create: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_create.return_value = CreateOrderDataMessage(
            client_oid="c", order_id="o"
        )

        order = client.create_buy_limit_order_xarizmi(
            instrument_name="CRO_USD", quantity=1, price=0.1
        )

        assert order.symbol.base_currency.name == "CRO"
        assert order.symbol.quote_currency.name == "USD"

    @mock.patch.object(CryptoAPI, "create_limit_order")
    def test_create_sell_limit_order_xarizmi_sets_side(
        self, mock_create: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_create.return_value = CreateOrderDataMessage(
            client_oid="clt-2", order_id="ord-sell-1"
        )

        order = client.create_sell_limit_order_xarizmi(
            instrument_name="ETH_USDT",
            quantity=2.0,
            price=3000.0,
        )

        assert order.order_id == "ord-sell-1"
        assert order.side == SideEnum.SELL
        assert order.symbol.base_currency.name == "ETH"
        assert order.symbol.quote_currency.name == "USDT"


# ---------------------------------------------------------------------------
# TestCancelOrder
# ---------------------------------------------------------------------------


class TestCancelOrder:
    """Tests for cancel_all_orders and cancel_order.

    Both methods are fire-and-forget: they send a signed POST but do not
    parse the response body.  Tests verify that the HTTP call is made.
    """

    @mock.patch("requests.post")
    def test_cancel_all_orders_makes_one_api_call(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok({}, "private/cancel-all-orders")

        client.cancel_all_orders(instrument_name="CRO_USD")

        mock_post.assert_called_once()

    @mock.patch("requests.post")
    def test_cancel_all_orders_works_without_instrument_name(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """instrument_name is optional; omitting it should not raise."""
        mock_post.return_value = _post_ok({}, "private/cancel-all-orders")

        client.cancel_all_orders()

        mock_post.assert_called_once()

    @mock.patch("requests.post")
    def test_cancel_order_makes_one_api_call(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok({}, "private/cancel-order")

        client.cancel_order(order_id="ord-001")

        mock_post.assert_called_once()

    @mock.patch("requests.post")
    def test_cancel_order_sends_order_id_in_body(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok({}, "private/cancel-order")

        client.cancel_order(order_id="ord-xyz")

        body = json.loads(mock_post.call_args[1]["data"])
        assert body["params"]["order_id"] == "ord-xyz"


# ---------------------------------------------------------------------------
# TestGetOrderDetails
# ---------------------------------------------------------------------------


class TestGetOrderDetails:
    """Tests for get_order_details and get_order_details_in_xarizmi.

    get_order_details returns the raw OrderHistoryDataMessage.
    get_order_details_in_xarizmi converts it to a xarizmi Order, computing
    the unit price from order_value / quantity.
    """

    @mock.patch("requests.post")
    def test_get_order_details_parses_response(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            _ORDER_HISTORY_ITEM, method="private/get-order-detail"
        )

        order = client.get_order_details(order_id="ord-001")

        assert order.order_id == "ord-001"
        assert order.instrument_name == "CRO_USD"
        assert order.quantity == 100.0

    @mock.patch("requests.post")
    def test_get_order_details_in_xarizmi_computes_unit_price(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """price = order_value / quantity  →  14.0 / 100.0 = 0.14"""
        item = {**_ORDER_HISTORY_ITEM, "order_value": 14.0, "quantity": 100.0}
        mock_post.return_value = _post_ok(item)

        order = client.get_order_details_in_xarizmi(order_id="ord-001")

        assert abs(order.price - 0.14) < 1e-9

    @mock.patch("requests.post")
    def test_get_order_details_in_xarizmi_builds_symbol(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(_ORDER_HISTORY_ITEM)

        order = client.get_order_details_in_xarizmi(order_id="ord-001")

        assert order.symbol.base_currency.name == "CRO"
        assert order.symbol.quote_currency.name == "USD"

    @mock.patch("requests.post")
    def test_get_order_details_in_xarizmi_maps_status(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """A crypto.com FILLED order maps to xarizmi DONE status."""
        item = {**_ORDER_HISTORY_ITEM, "status": "FILLED"}
        mock_post.return_value = _post_ok(item)

        order = client.get_order_details_in_xarizmi(order_id="ord-001")

        assert order.status == OrderStatusEnum.DONE


# ---------------------------------------------------------------------------
# TestGetCandlesticks
# ---------------------------------------------------------------------------


class TestGetCandlesticks:
    """Tests for get_candlesticks and get_all_candlesticks.

    get_candlesticks calls the public GET endpoint and returns a list of
    xarizmi Candlestick objects.

    get_all_candlesticks repeatedly calls get_candlesticks, walking backwards
    in time, until an empty page is returned or the optional min_datetime
    boundary is crossed.
    """

    @mock.patch("requests.get")
    def test_get_candlesticks_returns_parsed_ohlcv(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_get.return_value = _get_ok(
            {
                "interval": "1m",
                "instrument_name": "BTC_USD",
                "data": [_CANDLESTICK_ITEM],
            }
        )

        candles = client.get_candlesticks("BTC_USD", count=1, timeframe="1m")

        assert len(candles) == 1
        assert candles[0].open == 50000.0
        assert candles[0].high == 51000.0
        assert candles[0].low == 49000.0
        assert candles[0].close == 50500.0
        assert candles[0].volume == 10.5

    @mock.patch("requests.get")
    def test_get_candlesticks_timestamp_params_forwarded(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """start_ts and end_ts, when provided, must appear in the query
        parameters sent to the API."""
        mock_get.return_value = _get_ok(
            {"interval": "1h", "instrument_name": "ETH_USD", "data": []}
        )

        client.get_candlesticks(
            "ETH_USD",
            timeframe="1h",
            start_ts=1_700_000_000_000,
            end_ts=1_700_003_600_000,
        )

        params = mock_get.call_args[1]["params"]
        assert params["start_ts"] == 1_700_000_000_000
        assert params["end_ts"] == 1_700_003_600_000

    @mock.patch("requests.get")
    def test_get_candlesticks_omits_timestamps_when_not_given(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """start_ts and end_ts must NOT appear in the query params when the
        caller does not supply them."""
        mock_get.return_value = _get_ok(
            {"interval": "1m", "instrument_name": "BTC_USD", "data": []}
        )

        client.get_candlesticks("BTC_USD")

        params = mock_get.call_args[1]["params"]
        assert "start_ts" not in params
        assert "end_ts" not in params

    @mock.patch.object(CryptoAPI, "get_candlesticks")
    def test_get_all_candlesticks_stops_on_empty_page(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """The pagination loop must halt as soon as get_candlesticks returns
        an empty list, collecting all candles from earlier calls."""
        dummy = mock.MagicMock()
        mock_get_candles.side_effect = [
            [dummy, dummy],  # first window – two candles
            [dummy],  # second window – one candle
            [],  # third window – empty → stop
        ]

        result = client.get_all_candlesticks(
            "BTC_USD", interval="1m", verbose=False
        )

        assert len(result) == 3
        assert mock_get_candles.call_count == 3

    @mock.patch.object(CryptoAPI, "get_candlesticks", return_value=[])
    def test_get_all_candlesticks_accepts_enum_name_string(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """Interval may be passed as the enum *name*, e.g. 'MIN_1'."""
        client.get_all_candlesticks("BTC_USD", interval="MIN_1", verbose=False)
        mock_get_candles.assert_called_once()

    @mock.patch.object(CryptoAPI, "get_candlesticks", return_value=[])
    def test_get_all_candlesticks_accepts_enum_value_string(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """Interval may be passed as the enum *value*, e.g. '1m'."""
        client.get_all_candlesticks("BTC_USD", interval="1m", verbose=False)
        mock_get_candles.assert_called_once()

    @mock.patch.object(CryptoAPI, "get_candlesticks", return_value=[])
    def test_get_all_candlesticks_accepts_enum_instance(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """Interval may be passed directly as a CandlestickTimeInterval."""
        client.get_all_candlesticks(
            "BTC_USD",
            interval=CandlestickTimeInterval.HOUR_1,
            verbose=False,
        )
        mock_get_candles.assert_called_once()

    def test_get_all_candlesticks_raises_on_invalid_interval(
        self, client: CryptoAPI
    ) -> None:
        """An unrecognised interval string must raise ValueError."""
        with pytest.raises(ValueError, match="not valid"):
            client.get_all_candlesticks("BTC_USD", interval="INVALID")

    @mock.patch.object(CryptoAPI, "get_candlesticks", return_value=[])
    def test_get_all_candlesticks_respects_max_datetime(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """max_datetime caps the starting point of the backward walk so that
        candles beyond the requested ceiling are excluded."""
        max_dt = datetime.datetime(2024, 1, 2, tzinfo=pytz.UTC)

        client.get_all_candlesticks(
            "BTC_USD",
            interval=CandlestickTimeInterval.HOUR_1,
            max_datetime=max_dt,
            verbose=False,
        )

        # At least one call should have been attempted.
        mock_get_candles.assert_called()

    @mock.patch.object(CryptoAPI, "get_candlesticks")
    def test_get_all_candlesticks_min_datetime_causes_loop_to_stop(
        self, mock_get_candles: mock.Mock, client: CryptoAPI
    ) -> None:
        """Once end_ts drops below min_datetime the loop must break without
        making another API call."""
        dummy = mock.MagicMock()
        # Return data on the first call; the second call should never happen
        # because min_datetime causes the loop to exit first.
        mock_get_candles.return_value = [dummy]

        min_dt = datetime.datetime(2024, 1, 1, tzinfo=pytz.UTC)
        max_dt = datetime.datetime(2024, 1, 2, tzinfo=pytz.UTC)

        result = client.get_all_candlesticks(
            "BTC_USD",
            interval=CandlestickTimeInterval.HOUR_1,  # step > 1-day window
            min_datetime=min_dt,
            max_datetime=max_dt,
            verbose=False,
        )

        # Loop ran once (i=0): found one candle; i=1 end_ts < min_ts.
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestGetUserBalance
# ---------------------------------------------------------------------------


class TestGetUserBalance:
    """Tests for get_user_balance, get_user_balance_summary,
    and get_current_portfolio.

    get_user_balance returns raw GetUserBalanceDataMessage objects.
    get_user_balance_summary converts position_balances into a flat list of
    xarizmi PortfolioItem objects, one per held currency.
    get_current_portfolio wraps the summary in a xarizmi Portfolio.
    """

    @mock.patch("requests.post")
    def test_get_user_balance_returns_account_messages(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        result = client.get_user_balance()

        assert len(result) == 1
        assert result[0].instrument_name == "USD"
        assert len(result[0].position_balances) == 2

    @mock.patch("requests.post")
    def test_get_user_balance_summary_returns_one_item_per_currency(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        items = client.get_user_balance_summary()

        assert len(items) == 2
        currency_names = {item.symbol.base_currency.name for item in items}
        assert currency_names == {"BTC", "ETH"}

    @mock.patch("requests.post")
    def test_get_user_balance_summary_sets_market_values(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        items = client.get_user_balance_summary()

        market_values = {
            item.symbol.base_currency.name: item.market_value for item in items
        }
        assert market_values["BTC"] == 25000.0
        assert market_values["ETH"] == 3000.0

    @mock.patch("requests.post")
    def test_get_current_portfolio_wraps_summary(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        portfolio = client.get_current_portfolio()

        assert len(portfolio.items) == 2


# ---------------------------------------------------------------------------
# TestGetUserBalanceSummaryAsDf
# ---------------------------------------------------------------------------


class TestGetUserBalanceSummaryAsDf:
    """Tests for get_user_balance_summary_as_df.

    Verifies DataFrame column presence, sort order, percentage computation,
    and the optional include_* flags.
    """

    @mock.patch("requests.post")
    def test_returns_dataframe_with_required_columns(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df()

        assert df is not None
        for col in (
            "symbol",
            "market_value",
            "exchange",
            "portfolio_percentage",
            "date",
        ):
            assert col in df.columns, f"Missing column: {col}"

    @mock.patch("requests.post")
    def test_sorted_by_market_value_descending(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        """Rows must be sorted from highest to lowest market value."""
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df()

        assert df is not None
        values = df["market_value"].tolist()
        assert values == sorted(values, reverse=True)

    @mock.patch("requests.post")
    def test_portfolio_percentage_sums_to_one(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df()

        assert df is not None
        assert abs(df["portfolio_percentage"].sum() - 1.0) < 0.01

    @mock.patch("requests.post")
    def test_symbol_column_contains_currency_name(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df()

        assert df is not None
        assert set(df["symbol"].tolist()) == {"BTC", "ETH"}

    @mock.patch.object(CryptoAPI, "get_user_balance_summary", return_value=[])
    def test_returns_none_when_no_balance(
        self, _mock: mock.Mock, client: CryptoAPI
    ) -> None:
        df = client.get_user_balance_summary_as_df()
        assert df is None

    @mock.patch("requests.post")
    def test_exclude_percentage_column(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df(
            include_portfolio_percentage=False
        )

        assert df is not None
        assert "portfolio_percentage" not in df.columns

    @mock.patch("requests.post")
    def test_exclude_date_column(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _post_ok(
            {"data": [_BALANCE_ITEM]}, method="private/user-balance"
        )

        df = client.get_user_balance_summary_as_df(include_date=False)

        assert df is not None
        assert "date" not in df.columns


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for API-level error codes and non-2xx HTTP responses.

    The _post method inspects the error code in the response body and raises
    domain-specific exceptions so callers can handle them without parsing raw
    error payloads:

        315 → BadPriceException   (price rejected)
        308 → BadPriceException   (price out of allowed range)
        213 → BadQuantityException (quantity rejected)
        any other → RuntimeError

    A non-2xx response from the public GET endpoint raises NotImplementedError.
    """

    @mock.patch("requests.post")
    def test_error_code_315_raises_bad_price(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _error(315, "Invalid price")

        with pytest.raises(BadPriceException):
            client.create_limit_order("CRO_USD", 100, "BUY", 0.0)

    @mock.patch("requests.post")
    def test_error_code_308_raises_bad_price(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _error(308, "Price out of range")

        with pytest.raises(BadPriceException):
            client.create_limit_order("CRO_USD", 100, "BUY", 999_999.0)

    @mock.patch("requests.post")
    def test_error_code_213_raises_bad_quantity(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _error(213, "Invalid quantity")

        with pytest.raises(BadQuantityException):
            client.create_limit_order("CRO_USD", 0, "BUY", 0.14)

    @mock.patch("requests.post")
    def test_unknown_error_code_raises_runtime_error(
        self, mock_post: mock.Mock, client: CryptoAPI
    ) -> None:
        mock_post.return_value = _error(999, "Unexpected error")

        with pytest.raises(RuntimeError):
            client.get_order_history(start_time=1000, end_time=2000)

    @mock.patch("requests.get")
    def test_public_get_non_2xx_raises_not_implemented(
        self, mock_get: mock.Mock, client: CryptoAPI
    ) -> None:
        """A failed public GET (e.g. 404) must propagate as
        NotImplementedError."""
        mock_get.return_value = MockResponse(
            {"error": "not found"}, status_code=404
        )

        with pytest.raises(NotImplementedError):
            client.get_candlesticks("BTC_USD")
