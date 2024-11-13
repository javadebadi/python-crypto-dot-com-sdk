from enum import StrEnum


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
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_12 = "12h"
    DAY_1 = "1D"
    DAY_7 = "7D"
    DAT_14 = "14D"
    MONTH_1 = "1M"
