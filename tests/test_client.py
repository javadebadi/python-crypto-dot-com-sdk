from typing import Any
from unittest import mock

from crypto_dot_com.client import CryptoAPI


class MockResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int):
        self.json_data = json_data
        self.status_code = status_code

    def ok(self) -> bool:
        return True

    def json(self) -> dict[str, Any]:
        return self.json_data


# This method will be used by the mock to replace requests.post
def mocked_requests_post(*args: Any, **kwargs: Any) -> "MockResponse":

    if args[0] == "https://api.crypto.com/exchange/v1/private/create-order":
        return MockResponse(
            {
                "id": 4151042,
                "method": "private/create-order",
                "code": 0,
                "result": {
                    "client_oid": "1111111",
                    "order_id": "11111000000000000001",
                },
            },
            200,
        )

    return MockResponse({}, 404)


class TestCryptoAPI:

    @mock.patch("requests.post", side_effect=mocked_requests_post)
    def test_create_limit_order(self, mock_post: mock.Mock) -> None:
        # Given API Client
        client = CryptoAPI(
            api_key="", api_secret="", log_json_response_to_file=False
        )

        # When calling the function to create limit order
        data = client.create_limit_order(
            instrument_name="CRO_USD",
            quantity=str(100),
            price=str(0.14),
            side="BUY",
        )

        assert data.model_dump() == {
            "client_oid": "1111111",
            "order_id": "11111000000000000001",
        }

        # Then the requests.post was called with the correct URL
        mock_post.assert_called_once()
