from unittest.mock import patch

from crypto_dot_com.client import CryptoDotComMarketClient
from crypto_dot_com.data_models.standard import SymbolSummaryInfo
from crypto_dot_com.settings import ROOT_API_ENDPOINT


def test_list_all_available_market_symbols() -> None:
    # Expected JSON response
    expected_json = {
        "code": "0",
        "msg": "suc",
        "data": [
            {
                "symbol": "ethbtc",
                "count_coin": "btc",
                "amount_precision": 3,
                "base_coin": "eth",
                "price_precision": 8,
            },
            {
                "symbol": "ltcbtc",
                "count_coin": "btc",
                "amount_precision": 2,
                "base_coin": "ltc",
                "price_precision": 8,
            },
            {
                "symbol": "etcbtc",
                "count_coin": "btc",
                "amount_precision": 2,
                "base_coin": "etc",
                "price_precision": 8,
            },
        ],
    }

    # Given a client
    client = CryptoDotComMarketClient(api_key="", api_secret="")

    with patch("requests.get") as mock_get:
        # And mocking the requests.get function
        mock_get.return_value.json.return_value = expected_json

        # When calling the function that sends the GET request
        data = client.list_all_available_market_symbols()

        # Then the requests.get was called with the correct URL
        mock_get.assert_called_once_with(
            f"{ROOT_API_ENDPOINT}/v1/symbols",
            "",
            headers={},
            timeout=1000,
        )

        # And then the returned data is as expected
        assert data[0] == SymbolSummaryInfo(
            symbol="ethbtc",
            quote_currency="btc",
            base_currency="eth",
            price_precision=8,
            amount_precision=3,
            exchange="crypto.com",
        )
        assert data[1] == SymbolSummaryInfo(
            symbol="ltcbtc",
            quote_currency="btc",
            base_currency="ltc",
            price_precision=8,
            amount_precision=2,
            exchange="crypto.com",
        )
        assert data[2] == SymbolSummaryInfo(
            symbol="etcbtc",
            quote_currency="btc",
            base_currency="etc",
            price_precision=8,
            amount_precision=2,
            exchange="crypto.com",
        )
