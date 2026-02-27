"""
Unit tests for crypto_dot_com/enums.py
=======================================

All enums in this module are StrEnum subclasses, meaning each member IS a
plain string and can be passed directly to APIs, serialisers, or string
comparisons.

Test classes
------------
TestCryptoDotComMethodsEnum     API endpoint path values used to build URLs.
                                Wrong values would silently route requests to
                                the wrong endpoint.

TestSideEnum                    BUY / SELL strings sent verbatim to the API.

TestOrderTypeEnum               Order type strings (LIMIT, MARKET, …).

TestTimeInForceEnum             Time-in-force strings (GTC, IOC, FOK).

TestExecInstEnum                Execution instruction strings (POST_ONLY, …).

TestStatusEnum                  Order status strings plus the critical
                                to_xarizmi_status() mapping.  Three distinct
                                crypto.com statuses (REJECTED, CANCELED,
                                EXPIRED) all map to xarizmi CANCELLED.

TestCandlestickTimeInterval     All 12 timeframe values (1m … 1M).

TestTimeIntervalMapping         The lookup dict that converts
                                CandlestickTimeInterval → xarizmi
                                IntervalTypeEnum.  Tests that every interval
                                has an entry and that each maps to the
                                correct xarizmi value.
"""

import pytest
from xarizmi.enums import IntervalTypeEnum, OrderStatusEnum

from crypto_dot_com.enums import (
    TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM,
    CandlestickTimeInterval,
    CryptoDotComMethodsEnum,
    ExecInstEnum,
    OrderTypeEnum,
    SideEnum,
    StatusEnum,
    TimeInForceEnum,
)

# ---------------------------------------------------------------------------
# TestCryptoDotComMethodsEnum
# ---------------------------------------------------------------------------


class TestCryptoDotComMethodsEnum:
    """Verify that every method enum value is the exact path string that
    crypto.com expects.  These strings are appended to the base URL, so any
    typo would produce silent 404 errors.
    """

    def test_private_get_order_history(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_GET_ORDER_HISTORY.value
            == "private/get-order-history"
        )

    def test_private_create_order(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_CREATE_ORDER.value
            == "private/create-order"
        )

    def test_private_cancel_all_orders(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_CANCEL_ALL_ORDERS.value
            == "private/cancel-all-orders"
        )

    def test_private_cancel_order(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_CANCEL_ORDER.value
            == "private/cancel-order"
        )

    def test_private_get_order_details(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_GET_ORDER_DETAILS.value
            == "private/get-order-detail"
        )

    def test_public_get_candlestick(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PUBLIC_GET_CANDLESTICK.value
            == "public/get-candlestick"
        )

    def test_private_user_balance(self) -> None:
        assert (
            CryptoDotComMethodsEnum.PRIVATE_USER_BALANCE.value
            == "private/user-balance"
        )

    def test_all_members_are_strings(self) -> None:
        """StrEnum members must behave as plain strings."""
        for member in CryptoDotComMethodsEnum:
            assert isinstance(member, str)

    def test_eight_methods_defined(self) -> None:
        assert len(CryptoDotComMethodsEnum) == 8


# ---------------------------------------------------------------------------
# TestSideEnum
# ---------------------------------------------------------------------------


class TestSideEnum:
    """BUY and SELL are sent verbatim to the order creation endpoint."""

    def test_buy_value(self) -> None:
        assert SideEnum.BUY == "BUY"

    def test_sell_value(self) -> None:
        assert SideEnum.SELL == "SELL"

    def test_usable_as_string(self) -> None:
        assert f"side={SideEnum.BUY}" == "side=BUY"

    def test_exactly_two_members(self) -> None:
        assert len(SideEnum) == 2


# ---------------------------------------------------------------------------
# TestOrderTypeEnum
# ---------------------------------------------------------------------------


class TestOrderTypeEnum:
    """Order type strings control how the exchange processes the order."""

    def test_market(self) -> None:
        assert OrderTypeEnum.MARKET == "MARKET"

    def test_limit(self) -> None:
        assert OrderTypeEnum.LIMIT == "LIMIT"

    def test_stop_loss(self) -> None:
        assert OrderTypeEnum.STOP_LOSS == "STOP_LOSS"

    def test_stop_limit(self) -> None:
        assert OrderTypeEnum.STOP_LIMIT == "STOP_LIMIT"

    def test_take_profit(self) -> None:
        assert OrderTypeEnum.TAKE_PROFIT == "TAKE_PROFIT"

    def test_take_profit_limit(self) -> None:
        assert OrderTypeEnum.TAKE_PROFIT_LIMIT == "TAKE_PROFIT_LIMIT"

    def test_six_members_defined(self) -> None:
        assert len(OrderTypeEnum) == 6


# ---------------------------------------------------------------------------
# TestTimeInForceEnum
# ---------------------------------------------------------------------------


class TestTimeInForceEnum:
    """Time-in-force controls when an unfilled order is automatically
    cancelled."""

    def test_good_till_cancel(self) -> None:
        assert TimeInForceEnum.GOOD_TILL_CANCEL == "GOOD_TILL_CANCEL"

    def test_immediate_or_cancel(self) -> None:
        assert TimeInForceEnum.IMMEDIATE_OR_CANCEL == "IMMEDIATE_OR_CANCEL"

    def test_fill_or_kill(self) -> None:
        assert TimeInForceEnum.FILL_OR_KILL == "FILL_OR_KILL"

    def test_three_members_defined(self) -> None:
        assert len(TimeInForceEnum) == 3


# ---------------------------------------------------------------------------
# TestExecInstEnum
# ---------------------------------------------------------------------------


class TestExecInstEnum:
    """Execution instruction modifiers attached to an order."""

    def test_post_only(self) -> None:
        assert ExecInstEnum.POST_ONLY == "POST_ONLY"

    def test_liquidation(self) -> None:
        assert ExecInstEnum.LIQUIDATION == "LIQUIDATION"

    def test_two_members_defined(self) -> None:
        assert len(ExecInstEnum) == 2


# ---------------------------------------------------------------------------
# TestStatusEnum
# ---------------------------------------------------------------------------


class TestStatusEnum:
    """Tests for order status values and the to_xarizmi_status() conversion.

    to_xarizmi_status() maps crypto.com statuses to the xarizmi framework:

        ACTIVE   → OrderStatusEnum.ACTIVE
        FILLED   → OrderStatusEnum.DONE
        REJECTED → OrderStatusEnum.CANCELLED  (rejected before reaching book)
        CANCELED → OrderStatusEnum.CANCELLED  (cancelled by user or system)
        EXPIRED  → OrderStatusEnum.CANCELLED  (time-in-force expired)
    """

    # --- string values ---

    def test_rejected_value(self) -> None:
        assert StatusEnum.REJECTED == "REJECTED"

    def test_canceled_value(self) -> None:
        assert StatusEnum.CANCELED == "CANCELED"

    def test_filled_value(self) -> None:
        assert StatusEnum.FILLED == "FILLED"

    def test_expired_value(self) -> None:
        assert StatusEnum.EXPIRED == "EXPIRED"

    def test_active_value(self) -> None:
        assert StatusEnum.ACTIVE == "ACTIVE"

    def test_five_members_defined(self) -> None:
        assert len(StatusEnum) == 5

    # --- to_xarizmi_status() ---

    def test_active_maps_to_active(self) -> None:
        assert StatusEnum.ACTIVE.to_xarizmi_status() == OrderStatusEnum.ACTIVE

    def test_filled_maps_to_done(self) -> None:
        assert StatusEnum.FILLED.to_xarizmi_status() == OrderStatusEnum.DONE

    def test_rejected_maps_to_cancelled(self) -> None:
        """A rejected order never entered the book — treat as cancelled."""
        assert (
            StatusEnum.REJECTED.to_xarizmi_status()
            == OrderStatusEnum.CANCELLED
        )

    def test_canceled_maps_to_cancelled(self) -> None:
        assert (
            StatusEnum.CANCELED.to_xarizmi_status()
            == OrderStatusEnum.CANCELLED
        )

    def test_expired_maps_to_cancelled(self) -> None:
        """An order expired due to time-in-force — treat as cancelled."""
        assert (
            StatusEnum.EXPIRED.to_xarizmi_status() == OrderStatusEnum.CANCELLED
        )

    def test_all_terminal_statuses_covered(self) -> None:
        """Every StatusEnum member must return without raising."""
        for status in StatusEnum:
            result = status.to_xarizmi_status()
            assert isinstance(result, OrderStatusEnum)

    def test_cancelled_group_has_three_members(self) -> None:
        """REJECTED, CANCELED, and EXPIRED all collapse to CANCELLED."""
        cancelled = [
            s
            for s in StatusEnum
            if s.to_xarizmi_status() == OrderStatusEnum.CANCELLED
        ]
        assert len(cancelled) == 3


# ---------------------------------------------------------------------------
# TestCandlestickTimeInterval
# ---------------------------------------------------------------------------


class TestCandlestickTimeInterval:
    """Verify the exact string values sent to the candlestick endpoint and
    that all 12 expected intervals are present.  Wrong values would cause the
    API to reject the request silently or return data for a different period.
    """

    def test_min_1(self) -> None:
        assert CandlestickTimeInterval.MIN_1.value == "1m"

    def test_min_5(self) -> None:
        assert CandlestickTimeInterval.MIN_5.value == "5m"

    def test_min_15(self) -> None:
        assert CandlestickTimeInterval.MIN_15.value == "15m"

    def test_min_30(self) -> None:
        assert CandlestickTimeInterval.MIN_30.value == "30m"

    def test_hour_1(self) -> None:
        assert CandlestickTimeInterval.HOUR_1.value == "1h"

    def test_hour_2(self) -> None:
        assert CandlestickTimeInterval.HOUR_2.value == "2h"

    def test_hour_4(self) -> None:
        assert CandlestickTimeInterval.HOUR_4.value == "4h"

    def test_hour_12(self) -> None:
        assert CandlestickTimeInterval.HOUR_12.value == "12h"

    def test_day_1(self) -> None:
        assert CandlestickTimeInterval.DAY_1.value == "1D"

    def test_day_7(self) -> None:
        assert CandlestickTimeInterval.DAY_7.value == "7D"

    def test_day_14(self) -> None:
        assert CandlestickTimeInterval.DAY_14.value == "14D"

    def test_month_1(self) -> None:
        assert CandlestickTimeInterval.MONTH_1.value == "1M"

    def test_twelve_intervals_defined(self) -> None:
        assert len(CandlestickTimeInterval) == 12

    def test_lookup_by_value(self) -> None:
        """The API response contains value strings; we must be able to
        reconstruct the enum from them."""
        assert CandlestickTimeInterval("1m") is CandlestickTimeInterval.MIN_1
        assert CandlestickTimeInterval("1D") is CandlestickTimeInterval.DAY_1
        assert CandlestickTimeInterval("1M") is CandlestickTimeInterval.MONTH_1

    def test_lookup_by_name(self) -> None:
        """get_all_candlesticks accepts interval as the enum name string."""
        assert (
            CandlestickTimeInterval["MIN_1"] is CandlestickTimeInterval.MIN_1
        )
        assert (
            CandlestickTimeInterval["MONTH_1"]
            is CandlestickTimeInterval.MONTH_1
        )

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            CandlestickTimeInterval("invalid")


# ---------------------------------------------------------------------------
# TestTimeIntervalMapping
# ---------------------------------------------------------------------------


class TestTimeIntervalMapping:
    """Tests for TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM.

    This dict is the bridge between crypto.com's timeframe strings and the
    xarizmi IntervalTypeEnum used throughout the xarizmi framework.  A
    missing or wrong mapping would silently store candles under the wrong
    interval type in the database.
    """

    def test_every_interval_has_a_mapping(self) -> None:
        """No CandlestickTimeInterval member may be absent from the dict."""
        for interval in CandlestickTimeInterval:
            assert interval in TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM, (
                f"{interval!r} is missing from the interval mapping"
            )

    def test_mapping_has_no_extra_keys(self) -> None:
        """The dict must not contain keys that are not valid intervals."""
        assert len(TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM) == len(
            CandlestickTimeInterval
        )

    def test_all_values_are_interval_type_enum(self) -> None:
        for value in TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM.values():
            assert isinstance(value, IntervalTypeEnum)

    # --- individual mappings ---

    def test_min_1_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.MIN_1
            ]
            == IntervalTypeEnum.MIN_1
        )

    def test_min_5_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.MIN_5
            ]
            == IntervalTypeEnum.MIN_5
        )

    def test_min_15_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.MIN_15
            ]
            == IntervalTypeEnum.MIN_15
        )

    def test_min_30_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.MIN_30
            ]
            == IntervalTypeEnum.MIN_30
        )

    def test_hour_1_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.HOUR_1
            ]
            == IntervalTypeEnum.HOUR_1
        )

    def test_hour_2_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.HOUR_2
            ]
            == IntervalTypeEnum.HOUR_2
        )

    def test_hour_4_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.HOUR_4
            ]
            == IntervalTypeEnum.HOUR_4
        )

    def test_hour_12_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.HOUR_12
            ]
            == IntervalTypeEnum.HOUR_12
        )

    def test_day_1_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.DAY_1
            ]
            == IntervalTypeEnum.DAY_1
        )

    def test_day_7_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.DAY_7
            ]
            == IntervalTypeEnum.DAY_7
        )

    def test_day_14_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.DAY_14
            ]
            == IntervalTypeEnum.DAY_14
        )

    def test_month_1_maps_correctly(self) -> None:
        assert (
            TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
                CandlestickTimeInterval.MONTH_1
            ]
            == IntervalTypeEnum.MONTH_1
        )
