import datetime
import urllib
import urllib.parse

from requests import Response

from crypto_dot_com.utils import json_to_file

EXCHANGE_NAME: str = "crypto.com"
# ROOT_API_ENDPOINT: str = "https://api.crypto.com"
ROOT_API_ENDPOINT: str = "https://api.crypto.com/exchange"
API_VERSION: str = "v1"
ROOT_WEBSOCKET_ENDPOINT: str = "wss://ws.crypto.com/kline-api/ws"

URIS: dict[str, str] = {
    "list_all_available_market_symbols": "/symbols",
    "get_instruments": "/public/get-instruments",
    "user_balance": "/private/user-balance",
}


def log_json_response(response: Response) -> None:
    data = response.json()
    url = urllib.parse.urlparse(response.request.url)
    path = str(url.path).replace("/", "-")
    time = datetime.datetime.now().strftime("%Y-%m-%dT%H%M%S%f")
    if data is not None:
        json_to_file(data, f"{time}-{path}-{response.status_code}.json")
