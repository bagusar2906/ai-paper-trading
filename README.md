# Paper Trading System

A small, modular paper-trading service for XAUUSD (gold) and forex. It pulls
OHLCV candles from a pluggable data provider (Yahoo Finance, MT5, or OANDA),
computes indicators (EMA, RSI, ADX/DI), runs a rule-based strategy, and
exposes the result over a FastAPI HTTP API — plus logs every signal to a
local SQLite database.

## Project layout

```
paper-trading/
├── app/
│   ├── main.py                  FastAPI app: /signal, /history, /health
│   ├── worker.py                Standalone script: fetch data → run strategy → print signal
│   ├── config.py                Symbol, timeframe, indicator periods, provider selection
│   │
│   ├── providers/                Market data sources (all implement DataProvider)
│   │   ├── base.py               Abstract interface every provider must follow
│   │   ├── factory.py            create_provider(name) → picks the right provider
│   │   ├── yahoo_provider.py     Yahoo Finance via yfinance (no credentials needed)
│   │   ├── mt5_provider.py       MetaTrader5 terminal (Windows + MT5 installed only)
│   │   └── oanda_provider.py     OANDA v3 REST API (practice or live account)
│   │
│   ├── indicators/                Pure indicator math (pandas/numpy only, no I/O)
│   │   ├── trend.py               ema()
│   │   ├── momentum.py            rsi()
│   │   ├── adx.py                 adx_di()  → (+DI, -DI, ADX)
│   │   ├── volume.py              obv(), cmf(), relative_volume()
│   │   └── volatile.py            (placeholder for ATR / Bollinger / Keltner later)
│   │
│   ├── strategy/                  Trading logic
│   │   ├── base.py                Strategy ABC + generic TradingSignal dataclass
│   │   └── ema_rsi_adx.py         EMARSIADXStrategy: the actual BUY/SELL/HOLD rules
│   │
│   ├── models/
│   │   └── signal.py               TradingSignal dataclass actually returned by the strategy
│   │                                (symbol, action, price, time, ema, rsi, adx, ±DI, ...)
│   │
│   └── database/
│       └── database.py             SQLite: init_db(), save_signal(), get_recent_signals()
│
└── tests/
    ├── conftest.py                Puts the project root on sys.path (see "Running tests")
    ├── test_indicators.py         Unit tests for indicator math (synthetic data)
    ├── test_provider.py           Factory + provider tests (network calls mocked)
    ├── test_strategy.py           Strategy decision-logic tests (BUY/SELL/HOLD branches)
    ├── test_worker.py             worker.run() tested with a fake provider
    └── test_api.py                FastAPI endpoints via TestClient
```

## How the pieces fit together

```
              ┌──────────────┐
              │   config.py  │  SYMBOL, TIMEFRAME, EMA/RSI/ADX periods, DATA_PROVIDER
              └──────┬───────┘
                     │
     ┌───────────────┴───────────────┐
     │                               │
┌────▼─────┐                  ┌──────▼───────┐
│  main.py │  (FastAPI app)   │  worker.py   │  (standalone script)
└────┬─────┘                  └──────┬───────┘
     │  create_provider(...)          │  create_provider(...)
     └───────────────┬─────────────────┘
                      │
              ┌───────▼────────┐
              │ providers/      │  get_history(symbol, timeframe, bars) → DataFrame
              │ factory.py      │  (OHLCV, DatetimeIndex)
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │ strategy/        │  strategy.generate_signal(symbol, df)
              │ ema_rsi_adx.py   │    1. prepare(df)   → adds EMA/RSI/ADX/+DI/-DI columns
              │                  │       (calls indicators/*)
              │                  │    2. apply BUY/SELL/HOLD rules to the last row
              └───────┬────────┘
                      │  TradingSignal
              ┌───────▼────────┐
              │ database/        │  save_signal(...) / get_recent_signals(...)
              │ database.py      │  (SQLite, data/papertrade.db)
              └────────────────┘
```

- **Provider swap is transparent** — `DATA_PROVIDER` in `config.py` (or an explicit
  argument to `create_provider("twelve_data"|"yahoo"|"mt5"|"oanda")`) decides where candles
  come from. Everything downstream (indicators, strategy, API) only ever talks
  to the `DataProvider` interface, never a specific provider.
- **Indicators are pure functions** — no I/O, no provider knowledge, just
  pandas/numpy in → pandas/numpy out. That's what makes them independently
  unit-testable.
- **The strategy owns the decision logic** — `prepare()` computes indicator
  columns, `generate_signal()` reads the last row and returns a
  `TradingSignal`. Swapping in a different rule set later just means adding a
  new class in `strategy/` that implements the same `Strategy` interface.

## Running the API

```bash
cd paper-trading
pip install -r requirements.txt   # fastapi, uvicorn, pandas, numpy, yfinance, requests
uvicorn app.main:app --reload
```

- `GET /signal` — fetches fresh candles, runs the strategy, saves and returns
  the signal.
- `GET /history?limit=20` — recent signals from SQLite.
- `GET /health` — liveness check.

## Running the worker script

```bash
python -m app.worker
```

Fetches candles for `SYMBOL`/`TIMEFRAME` (from `config.py`) via Twelve Data by
default, runs the strategy once, and prints the resulting signal.

## Running the tests

The tests are real `pytest` tests — network calls and MT5/OANDA connections
are mocked out, so the whole suite runs offline in a few seconds.

```bash
cd paper-trading
python -m pytest tests/ -v
```

**Run this from the `paper-trading` folder** (the parent of both `app/` and
`tests/`), not from inside `tests/`. `tests/conftest.py` also adds the
project root to `sys.path` automatically, so the suite works even if pytest
is invoked from a different working directory.

Do **not** run individual test files as scripts (`python -m test_indicators`)
— they're pytest modules now (they use `assert`, fixtures, and mocking), not
standalone scripts. Use `pytest`.

### What's covered

| File                  | Covers |
|-----------------------|--------|
| `test_indicators.py`  | EMA, RSI, ADX/±DI, OBV, CMF, relative volume — math correctness on synthetic OHLCV data |
| `test_provider.py`    | `create_provider()` selection/errors, OANDA missing-key guard, Yahoo `get_history()` shape (yfinance call mocked) |
| `test_strategy.py`    | BUY / SELL / HOLD branches of `EMARSIADXStrategy` (indicators forced via monkeypatch), plus one end-to-end run with real indicator math |
| `test_worker.py`      | `worker.run()` with a fake provider — checks it returns a valid `TradingSignal` |
| `test_api.py`         | `/health`, `/signal`, `/history` via FastAPI `TestClient`, with a scratch SQLite DB per test |

## Configuration

All tunable parameters live in `app/config.py`:

- `MARKET_DATA_PROVIDER` — optional override: `"twelve_data"` (default),
  `"yahoo"`, `"mt5"`, or `"oanda"`
- `SYMBOL`, `TIMEFRAME`
- `EMA_LEN`, `RSI_LEN`, `RSI_OB`/`RSI_OS`, `ADX_LEN`, `ADX_SMOOTH`, `ADX_LEVEL`
- OANDA credentials are read from environment variables (`OANDA_API_KEY`,
  `OANDA_ACCOUNT_ID`, `OANDA_ENV`) rather than hardcoded — set these before
  using `DATA_PROVIDER = "oanda"`.
- Twelve Data credentials are read from `TWELVE_DATA_API_KEY`. Create a free
  key at [Twelve Data](https://twelvedata.com/pricing). The app uses its spot
  `XAU/USD` symbol and evaluates once per completed M5 candle (about 288
  scheduled data requests per day, below the free plan's 800/day limit).

## AI buy/sell signals

The strategy editor now offers **AI Agent (OpenAI)**. It sends the selected
recent OHLCV candles to the OpenAI Responses API and returns a constrained
`BUY`, `SELL`, or `HOLD` signal. Set `OPENAI_API_KEY` in the environment, then
create and activate the strategy in `/ui`. Optionally set
`OPENAI_TRADING_MODEL` (default: `gpt-5-mini`) and
`OPENAI_TRADING_TIMEOUT_SECONDS` (default: `20`).

The API key is never stored in the database or exposed to the dashboard. The
AI agent only chooses direction and confidence; this app calculates stop loss /
take profit locally and continues to apply the existing risk manager before an
order is placed. Missing credentials, API failures, malformed responses, and
low-confidence decisions safely become `HOLD`.

On the **Strategies** page, press **Activate** for exactly one strategy. The
background trading scheduler reads that active strategy on its next cycle, so
no application restart is required.

On Windows, you can start the API with `./start_ai_trading.ps1`. The launcher
uses `OPENAI_API_KEY` if it is already set, otherwise prompts securely for it.

### OmniRoute

OmniRoute is supported through its OpenAI-compatible Responses endpoint. Start
OmniRoute, then run `./start_ai_trading.ps1`. The launcher defaults to
`http://localhost:20128/v1` and model `gpt-5.5`; pass `-Model "<your OmniRoute
model or combo>"` to override the model. Set its key in `OMNIROUTE_API_KEY` (or
enter it when the launcher prompts). The default OmniRoute HTTP API port is
`20128`.

## Notes on the providers

- **Twelve Data** (`twelve_data_provider.py`) — the default provider. Uses
  spot `XAU/USD`, requires `TWELVE_DATA_API_KEY`, requests UTC candles, and
  excludes the in-progress candle from strategy decisions.

- **Yahoo** (`yahoo_provider.py`) — works out of the box, no credentials.
  Maps `"XAUUSD"` → the Yahoo ticker `"XAUUSD=X"` and translates
  `"1h"`/`"4h"` timeframes to yfinance's `"60m"` interval.
- **MT5** (`mt5_provider.py`) — only works on Windows with the MetaTrader5
  terminal and package installed. Importing this module elsewhere won't
  crash the app; it only raises if you actually try to use it.
- **OANDA** (`oanda_provider.py`) — talks to the practice or live v3 REST API
  depending on `OANDA_ENV`. Requires `OANDA_API_KEY` (and `OANDA_ACCOUNT_ID`
  for `get_current_price`).

## AI Trading Lab foundation

The first AI Trading Lab phase adds additive, paper-only database records for
completed normalized candles, data-quality events, and decision journaling.
They are intentionally not yet wired into the trading cycle, so existing
provider, strategy, risk, broker, and API behavior remains unchanged.

- Candle times enter the lab only as timezone-aware UTC timestamps. SQLite
  stores normalized UTC values without timezone metadata.
- Candle upserts are idempotent by source, symbol, timeframe, and candle-open
  time. The recorded candle must be complete; in-progress candles remain out
  of scope for this foundation layer.
- Decision journal entries are structurally paper-only and can capture future
  model, regime, risk, gate, and reason metadata without changing `/signal`.
- The app's current SQLAlchemy initialization creates these new additive tables
  at startup. Existing tables are not altered. Before deploying this beyond a
  local paper database, introduce the project's first versioned migration
  mechanism rather than relying on `create_all`.

### Candidate versus champion backtest

Train new XGBoost models as **candidates** from the dashboard. The training
record now keeps the symbol, timeframe, and final walk-forward held-out start
time. On **Backtesting**, select an AI Assisted XGBoost strategy, choose a
candidate in **Candidate comparison**, then run the backtest. The system:

- refuses candidates without recorded market context or a held-out window;
- refuses a different symbol, timeframe, feature set, or label definition;
- replays the candidate and current compatible champion over exactly the same
  held-out candles; and
- leaves the candidate unpromoted and unavailable to normal paper inference.

Older candidates do not contain this provenance and must be retrained before
comparison. A completed comparison displays net profit, profit factor, maximum
drawdown, win rate, and trade count for review. Promotion remains a manual,
audited decision from **AI Model Operations**.

### Raw market learning and background self-training

In **Train Candidate**, choose **Raw price and volume only** to learn from
the current and previous 11 completed OHLCV candles. This feature set contains
no ADX, RSI, EMA, ATR, or other technical indicators. In the AI Assisted XGBoost
strategy editor, select the same **Model inputs**. Raw models use probability
thresholds for BUY/SELL/HOLD entries and a fixed percentage stop with the
configured reward/risk ratio. Technical entry filters are disabled; position
sizing and risk limits still apply. The target remains the selected upward
return event: a low probability is not a separate learned downward-move target.

The training form also provides **Enable / update self-training** and **Stop
self-training**. Enabling saves the current symbol, timeframe, input choice,
and training parameters. The backend checks immediately and then at the selected
interval (5–1440 minutes; default 60). It fetches completed candles from the
selected provider and skips inputs already represented in the model registry.
Data or training failures are shown in the status and retried at the next interval.
Only one training run can execute at a time, including manual runs.

Self-training runs while the backend is open, even if its browser tab is closed.
The setting survives restarts; stopping the backend stops the loop. Disabling
prevents future runs while an in-progress run may finish. All output models
remain candidates until manual promotion. This is periodic supervised retraining,
not reinforcement learning or automatic adaptation of the executing champion.
