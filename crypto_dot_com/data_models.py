from typing import Any
from typing import TypedDict


class CryptDotComResponseType(TypedDict):
    data: dict[str, Any] | None
    code: str
    msg: str
