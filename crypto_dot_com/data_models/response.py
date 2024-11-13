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
