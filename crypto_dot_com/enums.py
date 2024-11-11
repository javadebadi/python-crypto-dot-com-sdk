from enum import StrEnum


class CryptoDotComMethodsEnum(StrEnum):
    PRIVATE_GET_ORDER_HISTORY = "private/get-order-history"
    PRIVATE_CREATE_ORDER = "private/create-order"
    PRIVATE_CANCEL_ALL_ORDERS = "private/cancel-all-orders"
    PRIVATE_CANCEL_ORDER = "private/cancel-order"
    PRIVATE_GET_ORDER_DETAILS = "private/get-order-detail"


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
