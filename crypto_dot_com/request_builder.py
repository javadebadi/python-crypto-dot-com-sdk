import hashlib
import hmac
import json
import random
from typing import Any
from typing import NotRequired
from typing import TypedDict

from crypto_dot_com.enums import CryptoDotComMethodsEnum
from crypto_dot_com.settings import API_VERSION
from crypto_dot_com.settings import ROOT_API_ENDPOINT
from crypto_dot_com.utils import get_current_time_ms
from crypto_dot_com.utils import sort_dict_by_key


class CryptoDotComRequestBuilderTypedDict(TypedDict):
    url: str
    headers: dict[str, str]
    data: str


class InternalTypedDict(TypedDict):
    id: int
    method: str
    api_key: str
    nonce: int
    params: NotRequired[dict[str, str | float | int | None]]
    sig: NotRequired[str]


class CryptoDotComUrlBuilder:

    def __init__(self, method: CryptoDotComMethodsEnum) -> None:
        self.method = method

    def build(self) -> str:
        return ROOT_API_ENDPOINT + "/" + API_VERSION + "/" + self.method.value


class CryptoDotComRequestBuilder:

    REQUEST_ID_MAX = 10000000
    MAX_LEVEL = 3

    def __init__(
        self,
        method: CryptoDotComMethodsEnum,
        api_key: str,
        secret_key: str | None,
        request_id: int | None = None,
        params: dict[str, str | float | int | None] | None = None,
        sign: bool = False,
    ) -> None:
        if request_id is None:
            request_id = random.randint(
                1, CryptoDotComRequestBuilder.REQUEST_ID_MAX
            )
        self.req: InternalTypedDict = {
            "id": request_id,
            "method": method.value,
            "api_key": api_key,
            "nonce": get_current_time_ms(),
        }
        if params:
            self.req["params"] = params
        self.req = sort_dict_by_key(self.req)  # type: ignore
        if "params" in self.req:
            self.param_str = self._params_to_str(self.req["params"], 0)
        else:
            self.param_str = ""  # TODO: is it correct?
        if sign is True:
            self._sign(secret_key=secret_key)

    def _params_to_str(self, obj: Any, level: int) -> str:
        if level >= CryptoDotComRequestBuilder.MAX_LEVEL:
            return str(obj)

        return_str = ""
        for key in sorted(obj):
            return_str += key
            if obj[key] is None:
                return_str += "null"
            elif isinstance(obj[key], list):
                for subObj in obj[key]:
                    return_str += self._params_to_str(subObj, level + 1)
            else:
                return_str += str(obj[key])
        return return_str

    def _sign(self, secret_key: str | None) -> None:
        payload_str = (
            self.req["method"]
            + str(self.req["id"])
            + self.req["api_key"]
            + self.param_str
            + str(self.req["nonce"])
        )
        if secret_key is None:
            raise ValueError(
                "To sign a request secret_key should not be 'None'!"
            )
        self.req["sig"] = hmac.new(
            bytes(str(secret_key), "utf-8"),
            msg=bytes(payload_str, "utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def json_dumps(self) -> str:
        return json.dumps(self.req)

    def __str__(self) -> str:
        s = ""
        if self.req.get("params", None) is not None:
            for key, value in self.req["params"].items():
                s += f"\n{key}:{value}"
        s += "\n==============================================="
        return s

    def build(self) -> CryptoDotComRequestBuilderTypedDict:
        return CryptoDotComRequestBuilderTypedDict(
            url=(
                ROOT_API_ENDPOINT
                + "/"
                + API_VERSION
                + "/"
                + self.req["method"]
            ),
            headers={"Content-Type": "application/json"},
            data=self.json_dumps(),
        )
