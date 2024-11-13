# Python Crypto API SDK


## Installation
```bash
pip install python_crypto_dot_com_sdk
```

## Market

### Get Candlestick Data
```python
import json
from crypto_dot_com.client import CryptoAPI


client = CryptoAPI(
    api_key=API_KEY,
    api_secret=SECRET_KEY,
    log_json_response_to_file=True,
)

kline_data = client.get_candlesticks("MTD_USD")
with open("x.json", "w") as f:
    json.dump([obj.model_dump() for obj in kline_data], f, indent=4)
```


