# GPT 5.6 Sol agent decision core

Ported on 2026-10-09 from the local sibling project
`GPT_5.6_Sol_Trading_Agent/btc_agent`: `agents.py`, `tools.py`,
`indicators.py`, and `market_view.py`. The standalone simulator and CLI are
not imported. This copy makes paper-trading deployment self-contained.

`app/strategy/ai_agent.py` retains the `AI_AGENT` strategy identifier so existing
saved profiles use the replacement. Legacy confidence, pip-stop and backtest
stride settings are ignored. New defaults match the source: `gpt-5.6-sol`,
medium reasoning, 1000 output tokens, ten-day warmup, 24 hourly / 10 daily
snapshot candles, decisions every four hours, anonymized prices and ATR stops.
`OPENAI_TRADING_MODEL` can override the default model; gateway/key/timeout
environment variables remain supported. Model availability depends on the
configured gateway. The cache lives in `data/sol_agent_cache`.

Integration differences:

- The actual application account, positions and closed trades supply context.
  The application RiskManager sizes entries; model size_fraction is advisory.
- Hourly candle timestamps are opens. Daily resampling uses calendar days and
  excludes unfinished days and a truncated first day in a rolling window.
- Timestamp-based cadence survives worker restarts. Production selects H1
  automatically; dashboard backtests must select H1 explicitly.
- The paper engine evaluates the preceding completed hour and simulates its
  decision at the next hour's open. It then checks that hour's high/low against
  stops and targets (stop first when both hit). This is paper simulation;
  polling completed candles can record a fill at an earlier open.
- Buy/sell keep the same side or reverse the opposite side; close flattens.
  Manual mode still records signals without executing any action.
- Malformed, missing, incomplete, or multiple tool calls hold. API failures
  never terminate the worker. Cache identity includes the complete snapshot.
- Source fee/slippage assumptions remain prompt context; actual fills and
  fees use the selected application's paper/backtest broker.

The source prompt, indicators, anonymization, one-shot place_order call,
retry policy and decision cache are retained. Local hardening rejects
incomplete/multiple orders and invalid ATR distances before execution.
