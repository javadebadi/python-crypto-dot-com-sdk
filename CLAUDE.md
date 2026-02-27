# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Tasks are run via [invoke](https://www.pyinvoke.org/) (`tasks.py`):

```bash
invoke install       # uv sync --all-groups (install all deps including dev)
invoke lock          # uv lock (update uv.lock)
invoke test          # Run all tests with pytest
invoke lint          # Run autoflake, isort, mypy, flake8, black --check
invoke autoformat    # Run autoflake, isort, black (in-place)
invoke build         # uv build (sdist + wheel)
invoke deploy        # uv publish
invoke tag           # Git tag with current version and push
```

Run a single test:
```bash
.venv/bin/pytest tests/test_client.py::TestCryptoAPI::test_create_limit_order
```

> **Note:** Always use `.venv/bin/pytest` (not the system `pytest`) to ensure the correct Python 3.12 environment is used. The `.python-version` file pins the project to Python 3.12.

## Architecture

This is a Python SDK wrapping the [crypto.com Exchange REST API v1](https://api.crypto.com/exchange/v1).

### Two client classes

**`CryptoAPI`** (`crypto_dot_com/client.py`) — Core REST client. Wraps public and private API endpoints. Public endpoints use GET; private endpoints use signed POST requests. All responses are parsed into Pydantic models from `xarizmi` or local `data_models/`.

**`CryptoDbApiClient`** (`crypto_dot_com/client_db.py`) — Extends `CryptoAPI` with database persistence via the `xarizmi` ORM. Adds methods to download candlesticks and portfolio data into a configured SQL database using `xarizmi`'s session/migration system. Requires a `database_url` parameter and a `setup()` call before use.

### Key dependency: `xarizmi`

Most domain models (`Candlestick`, `Order`, `Portfolio`, `Symbol`, `IntervalTypeEnum`, etc.) come from the `xarizmi` package rather than being defined locally. This SDK is essentially an adapter between crypto.com's API and xarizmi's data model.

### Request signing (`crypto_dot_com/request_builder.py`)

Private API calls require HMAC-SHA256 signing. `CryptoDotComRequestBuilder` constructs the signed JSON body. The signature is computed over a canonical string: `method + id + api_key + sorted_params_string + nonce`.

### Data models (`crypto_dot_com/data_models/`)

Pydantic v2 models for API request/response shapes:
- `crypto_dot_com.py` — base response envelope (`CryptoDotComResponseType`, `CryptoDotComErrorResponse`)
- `response.py` — candlestick response, user balance response, create order result
- `order_history.py` — order history record
- `request_message.py` — create-order request body

### Enums (`crypto_dot_com/enums.py`)

- `CryptoDotComMethodsEnum` — maps API method names (e.g. `"private/create-order"`)
- `CandlestickTimeInterval` — valid timeframes (`"1m"`, `"1D"`, `"1M"`, etc.)
- `TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM` — maps local intervals to xarizmi's `IntervalTypeEnum`
- `StatusEnum` — order statuses, with `to_xarizmi_status()` conversion

### Export utilities (`crypto_dot_com/export.py`)

High-level functions for downloading and persisting data to CSV/charts without needing to instantiate the client directly: `export_order_history()`, `export_user_balance()`, `read_order_history_from_csv()`.

### Settings (`crypto_dot_com/settings.py`)

Base URL (`https://api.crypto.com/exchange/v1`), exchange name (`crypto.com`), and the `log_json_response()` helper for optional request/response logging to JSON files.

### Linting configuration (`setup.cfg`)

- max line length: 79
- isort profile: black
- mypy: strict mode, pydantic plugin enabled; xarizmi imports are ignored for type checking
