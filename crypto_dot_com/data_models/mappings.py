from crypto_dot_com.data_models.crypto_dot_com import (
    AvailableMarketSymbolInfoResponse,
)
from crypto_dot_com.data_models.crypto_dot_com import (
    ListAllAvailableMarketSymbolsResponse,
)
from crypto_dot_com.data_models.standard import SymbolSummaryInfo
from crypto_dot_com.settings import EXCHANGE_NAME


def map_to_standard_symbol_info(
    symbol: AvailableMarketSymbolInfoResponse,
) -> SymbolSummaryInfo:
    return SymbolSummaryInfo(
        symbol=symbol.symbol,
        quote_currency=symbol.count_coin,
        base_currency=symbol.base_coin,
        price_precision=symbol.price_precision,
        amount_precision=symbol.amount_precision,
        exchange=EXCHANGE_NAME,
    )


def map_to_standard_list_of_symbols_info(
    symbols: ListAllAvailableMarketSymbolsResponse,
) -> list[SymbolSummaryInfo]:
    standard_symbols: list[SymbolSummaryInfo] = []
    for symbol in symbols.symbols_info:
        standard_symbols.append(map_to_standard_symbol_info(symbol))
    return standard_symbols
