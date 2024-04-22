from typing import Any
from typing import TypedDict

from pydantic import BaseModel


class CryptDotComResponseType(TypedDict):
    data: dict[str, Any] | None
    code: str
    msg: str


class AvailableMarketSymbolInfoResponse(BaseModel):
    symbol: str
    count_coin: str
    base_coin: str
    price_precision: int
    amount_precision: int


class ListAllAvailableMarketSymbolsResponse(BaseModel):
    symbols_info: list[AvailableMarketSymbolInfoResponse]
