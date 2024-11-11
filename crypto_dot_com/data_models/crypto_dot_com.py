from typing import Any

from pydantic import BaseModel


class CryptoDotComResponseType(BaseModel):
    id: int
    method: str
    code: int
    result: Any | None = None


class CryptoDotComErrorResponse(BaseModel):
    id: int
    method: str
    code: int
    message: str
    result: Any | None = None


class AvailableMarketSymbolInfoResponse(BaseModel):
    symbol: str
    count_coin: str
    base_coin: str
    price_precision: int
    amount_precision: int


class ListAllAvailableMarketSymbolsResponse(BaseModel):
    symbols_info: list[AvailableMarketSymbolInfoResponse]
