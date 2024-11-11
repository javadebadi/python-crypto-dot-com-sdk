class CryptoDotComAPIException(Exception):
    pass


class CreateOrderException(CryptoDotComAPIException):
    pass


class BadPriceException(CreateOrderException):
    pass


class BadQuantityException(CreateOrderException):
    pass
