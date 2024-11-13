from enum import StrEnum

from xarizmi.enums import IntervalTypeEnum


class CryptoDotComMethodsEnum(StrEnum):
    PRIVATE_GET_ORDER_HISTORY = "private/get-order-history"
    PRIVATE_CREATE_ORDER = "private/create-order"
    PRIVATE_CANCEL_ALL_ORDERS = "private/cancel-all-orders"
    PRIVATE_CANCEL_ORDER = "private/cancel-order"
    PRIVATE_GET_ORDER_DETAILS = "private/get-order-detail"
    PUBLIC_GET_CANDLESTICK = "public/get-candlestick"


class SideEnum(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderTypeEnum(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class TimeInForceEnum(StrEnum):
    GOOD_TILL_CANCEL = "GOOD_TILL_CANCEL"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"


class ExecInstEnum(StrEnum):
    POST_ONLY = "POST_ONLY"
    LIQUIDATION = "LIQUIDATION"


class StatusEnum(StrEnum):
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    FILLED = "FILLED"
    EXPIRED = "EXPIRED"
    ACTIVE = "ACTIVE"


class CandlestickTimeInterval(StrEnum):
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_12 = "12h"
    DAY_1 = "1D"
    DAY_7 = "7D"
    DAY_14 = "14D"
    MONTH_1 = "1M"


TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM = {
    CandlestickTimeInterval.MIN_1: IntervalTypeEnum.MIN_1,
    CandlestickTimeInterval.MIN_5: IntervalTypeEnum.MIN_5,
    CandlestickTimeInterval.MIN_15: IntervalTypeEnum.MIN_15,
    CandlestickTimeInterval.MIN_30: IntervalTypeEnum.MIN_30,
    CandlestickTimeInterval.HOUR_1: IntervalTypeEnum.HOUR_1,
    CandlestickTimeInterval.HOUR_2: IntervalTypeEnum.HOUR_2,
    CandlestickTimeInterval.HOUR_4: IntervalTypeEnum.HOUR_4,
    CandlestickTimeInterval.HOUR_12: IntervalTypeEnum.HOUR_12,
    CandlestickTimeInterval.DAY_1: IntervalTypeEnum.DAY_1,
    CandlestickTimeInterval.DAY_7: IntervalTypeEnum.DAY_7,
    CandlestickTimeInterval.DAY_14: IntervalTypeEnum.DAY_14,
    CandlestickTimeInterval.MONTH_1: IntervalTypeEnum.MONTH_1,
}
