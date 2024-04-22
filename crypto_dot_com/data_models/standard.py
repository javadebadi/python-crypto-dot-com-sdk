from pydantic import BaseModel


class SymbolSummaryInfo(BaseModel):
    symbol: str
    quote_currency: str
    base_currency: str
    price_precision: int
    amount_precision: int
    exchange: str
