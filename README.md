# Python Crypto API SDK


## Installation
```bash
pip install python_crypto_dot_com_sdk
```

## Market

### List all available market symbols
```python
from crypto_dot_com.client import CryptoDotComMarketClient

client = CryptoDotComMarketClient(api_key="", api_secret="")
client.list_all_available_market_symbols()
```


