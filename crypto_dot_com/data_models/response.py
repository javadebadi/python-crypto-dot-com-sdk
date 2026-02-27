import datetime
from typing import Any

from pydantic import BaseModel

from crypto_dot_com.enums import CandlestickTimeInterval


class CreateOrderDataMessage(BaseModel):
    client_oid: str
    order_id: str


class CryptoDotComeCandlestick(BaseModel):
    o: float  # open price
    h: float  # high price
    l: float  # low price
    c: float  # close price
    v: float  # volume
    t: int  # timestamp in ms


class GetCandlestickDataMessage(BaseModel):
    interval: CandlestickTimeInterval
    data: list[CryptoDotComeCandlestick]
    instrument_name: str


class CurrencyBalanceDataMessage(BaseModel):
    quantity: float
    reserved_qty: float
    collateral_amount: float
    haircut: float = 0
    collateral_eligible: bool = False
    market_value: float
    max_withdrawal_balance: float
    instrument_name: str
    hourly_interest_rate: float


class GetUserBalanceDataMessage(BaseModel):
    total_available_balance: float
    total_margin_balance: float
    total_initial_margin: float
    total_haircut: float
    total_position_im: float
    total_maintenance_margin: float
    total_position_cost: float
    total_cash_balance: float
    total_collateral_value: float
    total_session_unrealized_pnl: float
    instrument_name: str
    total_session_realized_pnl: float
    position_balances: list[CurrencyBalanceDataMessage]
    credit_limits: list[Any]
    total_effective_leverage: float
    position_limit: float
    used_position_limit: float
    total_borrow: float
    margin_score: float
    is_liquidating: bool
    has_risk: bool
    terminatable: bool


class TradeHistoryDataMessage(BaseModel):
    account_id: str
    trade_id: str
    trade_match_id: str | None
    order_id: str
    instrument_name: str
    side: str
    traded_price: float
    traded_quantity: float
    fees: float
    fee_instrument_name: str
    client_oid: str | None
    taker_side: str | None
    create_time: datetime.datetime
    create_time_ns: str | None
    transact_time_ns: str | None
    match_count: int
    event_date: str
