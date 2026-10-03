# AI Trading Lab Enhancement Specification

## Purpose

Enhance the existing paper-trading application into an **AI Trading Lab**: a controlled research and paper-execution environment that collects market data, derives reproducible features, trains and evaluates prediction models, produces explainable trading decisions, and tracks their simulated outcomes.

This is an enhancement of the existing repository, not a request to replace it. Preserve working MT5, Python, strategy, API, worker, backtest, and UI integrations whenever possible. Add small, well-tested seams around the current architecture; refactor only when a measured limitation makes it necessary.

> Safety principle: the application remains paper-trading only. A trained model is a research artifact until it passes evaluation and is **manually promoted**. No model may autonomously enable live trading or submit a live broker order.

## Goals

- Retain the existing RSI/EMA/ADX strategy and its current behavior as a deterministic baseline.
- Collect reliable, timestamped OHLCV and execution-cost data from MT5 (or the application's present feed).
- Build a reusable, point-in-time-safe feature engine.
- Train an interpretable XGBoost baseline that predicts a measurable outcome probability, not a direct `BUY`/`SELL` action.
- Add regime-aware strategy selection, paper execution, journaling, realistic backtesting, and model governance.
- Expose suitable capabilities through the existing FastAPI service and present results in the existing React/lightweight-charts dashboard if present.
- Make every prediction, trade, model version, and evaluation reproducible and auditable.

## Non-goals

- Do not introduce live trading, automatic broker-account funding, or autonomous model promotion.
- Do not start with LLMs, reinforcement learning, LSTMs, or Transformers. Establish a strong, reproducible tabular baseline first.
- Do not discard existing trading rules merely because an ML feature is added.
- Do not promise profit, predict certainty, or optimize solely on in-sample returns.
- Do not add microservices, a message broker, a new database, containers, or cloud infrastructure unless the current repository clearly needs them.

## Required Repository Discovery Before Changes

Codex must first inspect the repository and report a concise implementation plan. In particular:

1. Read `README.md`, dependency/lock files, configuration files, and startup scripts.
2. Map the current entry points (for example API, worker, MT5 signal server, and backtest runners) and how they communicate.
3. Identify the existing data source, candle timeframes, timezone convention, database/storage layer, schemas, and migrations.
4. Locate strategy logic, indicator calculation, SL/TP logic, sizing, simulated execution, trade persistence, and current tests.
5. Inspect the FastAPI routes, their request/response contracts, and any React/lightweight-charts frontend before changing a contract.
6. Run the existing relevant tests and a non-destructive smoke check before modifications; record failures that already exist.
7. Preserve compatibility with existing API clients and MT5 integration. If a contract must change, add a versioned endpoint or backwards-compatible optional fields.
8. Check `.gitignore` and avoid committing credentials, model binaries, large raw datasets, or local database files unless the project has an intentional artifact-storage approach.

## Target Architecture

Use the existing modules and deployment shape. The following is a logical design, not a mandate to create every directory or service at once.

```text
MT5 / market feed
  -> data collector + quality checks
  -> immutable candle / quote store
  -> feature engine (point-in-time features)
  -> labels + training dataset snapshots
  -> model training / validation
  -> model registry (candidate, champion, retired)
  -> inference service
  -> regime + deterministic strategy rules
  -> risk manager
  -> paper execution simulator
  -> trade journal / metrics / dashboard
```

Keep these responsibilities distinct:

- **Data collection** records what was known at a particular time; it does not calculate future-looking fields.
- **Feature engine** calculates only features available at the decision candle close.
- **Model** estimates probabilities and confidence; it does not place orders.
- **Strategy engine** converts a model score plus regime and technical gates into an intent (`long`, `short`, or `flat`) with reasons.
- **Risk manager** can veto or resize an intent independently.
- **Paper executor** simulates fills and lifecycle transitions; it never routes live orders.

## Market Data Collection and Quality

Support the project's current MT5 integration first. The MT5 boundary should provide normalized records, such as `symbol`, `timeframe`, UTC candle-open time, OHLCV, spread, tick volume/real volume when available, source, and ingestion timestamp.

- Store all timestamps in UTC; convert only for UI display.
- Treat completed candles as the default training and decision input. Clearly flag an in-progress candle and exclude it from finalized training rows.
- Make ingestion idempotent using a unique key such as `(source, symbol, timeframe, candle_open_time)`.
- Backfill incrementally and capture data-quality events: gaps, duplicates, out-of-order candles, non-positive prices, unexpected volume, stale feed, and changing broker symbol specifications.
- Persist the observed bid/ask spread or a documented proxy so backtests and paper fills use realistic costs.
- Keep MT5-specific calls in an adapter/gateway. The rest of the lab consumes a broker-neutral data contract.

## Feature Engine

Implement a single deterministic feature pipeline shared by training, backtests, and live-paper inference. Feature definitions and parameters must be versioned. Features must use information through time `t` only; shift/rolling-window rules must be explicit.

Minimum feature groups:

| Group | Examples |
| --- | --- |
| OHLCV | open, high, low, close, tick/real volume, spread where available |
| Returns | log/simple return over 1, 3, 5, 10 candles; rolling cumulative return |
| Trend | EMA 9/20/50, EMA slopes, close distance from EMA, EMA cross state |
| Oscillation | RSI and changes in RSI |
| Trend strength | ADX and directional indicators if available |
| Range/risk | ATR, true range, ATR percent, rolling high-low range |
| Candle geometry | body size/percent, direction, upper/lower wick percent, close location in range, gap |
| Momentum | rolling return, rate of change, consecutive up/down candles |
| Volatility | rolling standard deviation of returns, realized volatility, ATR-normalized movement |
| Session/time | UTC hour, weekday, market session flags; use cyclical encodings for time-of-day where appropriate |

Rules:

- Calculate indicators per symbol/timeframe and sort ascending by time before rolling operations.
- Do not forward-fill unavailable historical observations across a data gap.
- Drop or explicitly mark warm-up rows; never silently replace unavailable indicator values with future-informed values.
- Persist a feature-set ID, column order, code/config version, and data range with every training run and prediction.
- Add unit tests with small known candle sequences for EMA, RSI, ADX, ATR, return alignment, and candle geometry.

## Labels and XGBoost Baseline

Model a verifiable prediction target, not an order command.

Initial binary target at decision candle `t`:

```text
label_up(t) = 1 when close(t + N) / close(t) - 1 >= threshold
              0 otherwise
```

Make `N` (future completed candles) and `threshold` configurable per symbol/timeframe. Start with a threshold that exceeds typical expected round-trip spread, commission, and slippage for that instrument. Consider a three-class extension only after the binary model is trusted: `up`, `neutral`, `down`.

Train an XGBoost classifier as the first model. Store:

- model binary/artifact and SHA-256 checksum;
- feature-set ID and exact ordered feature list;
- label definition, hyperparameters, random seed, and package versions;
- train/validation/test date ranges and dataset snapshot/reference;
- probability calibration method and metrics;
- code revision, author/time, and training logs.

Use the model output as `P(up | features at t)` plus quality/confidence metadata. Do not equate a high probability with profitability until a cost-aware out-of-sample strategy evaluation supports it.

## Market-Regime Classification

Begin with transparent rules rather than an extra ML model. Example regimes can be `trend_up`, `trend_down`, `range`, `high_volatility`, and `unknown`, derived from EMA direction/separation, ADX, and ATR/realized-volatility percentiles.

- The classifier must produce a regime, feature inputs, threshold/config version, and reason fields.
- Run it at the same decision timestamp as inference.
- Start by using regime as a gate or strategy parameter selector. For example, only permit a trend-following long setup in `trend_up` and prevent new positions in `high_volatility` until explicitly designed and tested.
- Later, compare a learned regime model only against this rule baseline with the same walk-forward discipline.

## Strategy Engine

Keep the existing RSI/EMA/ADX logic as an explicit baseline strategy. Introduce an AI-assisted strategy only as an additional, selectable strategy mode.

Example long intent:

```text
P(up) >= configured_probability_threshold
AND EMA20 > EMA50
AND ADX >= configured_adx_threshold
AND RSI is in configured range
AND regime permits long entries
AND model/data health checks pass
```

Each intent must include symbol, side, timestamp, entry reference price, proposed stop/take-profit methodology, model ID, probability, regime, all gate outcomes, and a human-readable reason. Decisions with missing/stale data, an unknown champion, feature mismatch, or risk breach must resolve to `flat` and be journaled as rejected.

## Risk Manager

Risk management is deterministic and has final veto authority. Implement configurable controls that fit the current execution model:

- paper account equity and per-trade risk fraction (start small, e.g. 0.25–0.5%);
- position size derived from stop distance, contract/pip value, and configurable rounding;
- ATR/rule-based stop loss and take profit with a documented reward-to-risk ratio;
- maximum open positions, exposure per symbol/direction, and correlated-exposure policy;
- max daily loss, max drawdown circuit breaker, consecutive-loss pause, and cooldown after exit;
- spread, volatility, market-hours, data-staleness, and duplicate-signal guards;
- hard paper-only environment guard.

Calculate costs and position value using broker symbol specifications supplied by the MT5 adapter. Fail closed if required specifications are unavailable.

## Paper Execution and Trade Journal

The execution adapter must only simulate orders. Use bid/ask-aware fills where data exists: buy entries near ask and sell entries near bid, with configurable adverse slippage and commissions. Model pending/filled/rejected/cancelled/closed lifecycle states and partial fills only if the existing simulator supports them.

For every decision and trade, journal:

- IDs and links: decision ID, signal ID, order ID, position ID, model ID, backtest/run ID;
- timestamps (signal, submitted, filled, closed), symbol, timeframe, side, requested/fill prices;
- quantity, stop, take profit, spread, commission, slippage, realized and unrealized P&L;
- strategy/risk/model/regime inputs and decision reasons;
- exit reason, errors/rejections, and data/feature versions.

The journal should support reconstructing: “What did the system know, decide, simulate, and realize at this point?”

## Backtesting and Evaluation

Backtests must reuse the production feature, strategy, risk, and execution code paths as far as practical. Never let the backtest use a simplified fill path that makes it incomparable with paper trading.

Include configurable spread, commission, slippage, candle timing/fill assumptions, symbol trading hours, and enough warm-up history. Avoid same-candle look-ahead: if a decision is made on candle close, fill no earlier than a defensible subsequent price/candle event.

Report at least:

- net return and equity curve;
- profit factor, gross profit/loss, expectancy, win rate, average win/loss;
- maximum drawdown and drawdown duration;
- Sharpe ratio (document frequency/annualization assumptions), volatility, trade count, exposure;
- per-symbol, per-regime, per-side, and monthly breakdowns;
- classifier metrics: ROC-AUC where meaningful, precision, recall, Brier score/log loss, and probability calibration/reliability;
- benchmark comparison against the existing deterministic strategy and a no-trade/buy-and-hold reference when appropriate.

### Time-Series Validation and Leakage Prevention

This is mandatory.

- Split strictly by time: train before validation before final test. Never shuffle rows across time.
- Prefer rolling or expanding-window walk-forward evaluation. Hold out the most recent final period until model-selection decisions are complete.
- Purge or embargo observations around split boundaries when labels overlap the `N`-candle future horizon.
- Fit scalers, encoders, imputers, calibration models, feature selection, and hyperparameter choices only on the relevant training window.
- Do not use future revisions, future candle highs/lows, future rolling values, or a label-derived field as a feature.
- Make the decision timestamp, feature availability timestamp, label horizon, and assumed fill time explicit in data and tests.
- Reject a training run if split ranges overlap, feature columns differ from the registered contract, or leakage checks fail.

## Model Registry and Promotion

Maintain a lightweight registry in the existing database or artifact metadata. A model status is one of `candidate`, `champion`, `retired`, or `rejected`.

- Only one champion is active for a `(strategy, symbol group, timeframe, label definition, feature-set)` scope.
- A candidate is trained and evaluated offline/paper-shadow mode first.
- Compare candidate vs champion over equivalent, unseen walk-forward windows using cost-aware strategy metrics, calibration, stability across windows/regimes, and risk limits.
- Initial promotion is manual: store reviewer, time, prior/new model IDs, comparison report, and rationale.
- Support instant rollback to the previous champion and fail closed to the deterministic baseline if the champion cannot load.
- Never overwrite artifacts in place; version and checksum them.

## Retraining and Drift Monitoring

Scheduled retraining creates a **candidate only**. Use the simplest scheduler already present in the app (worker/cron/task scheduler); do not add distributed scheduling prematurely.

- Make cadence configurable (for example weekly or after a minimum number of new completed candles).
- Snapshot the training input and log its date range.
- Detect data drift using feature missingness/ranges and a distribution comparison such as PSI; detect prediction drift with probability distributions and calibration/outcome monitoring once labels mature.
- Alert and optionally stop new AI-assisted entries when data is stale, a required feature is missing, drift exceeds a configured threshold, model load fails, or live paper performance breaches guardrails.
- Drift must trigger investigation/candidate evaluation, never silent self-promotion.

## FastAPI Boundaries and Example Payloads

Use the established FastAPI patterns and validation library. Make long-running training/backtests asynchronous through the current worker/job pattern when one exists; return a run/job ID instead of blocking an HTTP request. Protect write/admin endpoints locally at minimum, and keep paper-only checks server-side.

Suggested endpoints (adapt names to current routes):

- `GET /api/v1/models/champion?symbol=EURUSD&timeframe=M15`
- `POST /api/v1/training-runs`
- `GET /api/v1/training-runs/{run_id}`
- `POST /api/v1/backtests`
- `GET /api/v1/backtests/{run_id}`
- `POST /api/v1/models/{model_id}/promote` (manual/admin action)
- `POST /api/v1/inference` (internal/paper-only)
- `GET /api/v1/journal/trades`
- `GET /api/v1/health/data` and `GET /api/v1/health/model`

Example training request:

```json
{
  "symbol": "EURUSD",
  "timeframe": "M15",
  "feature_set_id": "core-v1",
  "label": { "horizon_candles": 12, "up_return_threshold": 0.003 },
  "train_start": "2023-01-01T00:00:00Z",
  "train_end": "2025-06-30T23:45:00Z",
  "validation_mode": "walk_forward",
  "promotion_mode": "candidate_only"
}
```

Example inference response:

```json
{
  "decision_id": "dec_...",
  "timestamp": "2026-10-03T09:15:00Z",
  "symbol": "EURUSD",
  "timeframe": "M15",
  "model_id": "model_...",
  "probability_up": 0.72,
  "regime": "trend_up",
  "intent": "long",
  "risk_status": "approved",
  "reasons": ["probability gate passed", "EMA20 above EMA50", "ADX gate passed"],
  "paper_only": true
}
```

Example candidate-promotion request:

```json
{
  "scope": { "symbol": "EURUSD", "timeframe": "M15", "strategy": "ai_assisted_v1" },
  "rationale": "Candidate improved walk-forward profit factor without exceeding drawdown guardrail.",
  "expected_current_champion_id": "model_..."
}
```

## Dashboard (React / lightweight-charts)

Extend the existing dashboard incrementally. Prefer existing components and API conventions. Useful views are:

- price chart with entries/exits, SL/TP markers, current regime, and AI probability at each decision;
- paper account equity and drawdown chart;
- live/paper decision feed with accepted/rejected reasons;
- trade journal with filters by model, strategy, symbol, regime, and date;
- model registry with champion/candidates, training dates, dataset range, feature version, validation metrics, and manual promotion controls;
- data/model health panel: last candle time, gaps, feature completeness, drift, and model status.

Do not expose secrets or raw broker credentials to the browser. Display paper-only status prominently.

## Database / Schema Suggestions

Adapt to the repository's existing persistence technology and migration style. Suggested entities:

| Entity | Key fields |
| --- | --- |
| `market_candles` | source, symbol, timeframe, candle time UTC, OHLCV, spread, ingested time |
| `feature_sets` | ID, definition/config version, ordered columns, code revision |
| `training_runs` | data range/snapshot, label config, split config, seed, status, logs, metrics |
| `model_versions` | model ID, artifact URI/checksum, feature/label IDs, status, metrics, parent/champion scope |
| `model_promotions` | scope, old/new model IDs, reviewer, rationale, timestamp |
| `inference_decisions` | model/version inputs, probabilities, regime, gates, intent, rejection reason |
| `paper_orders` / `paper_positions` | lifecycle, requested/fill prices, size, costs, stop/TP, timestamps |
| `trade_journal` | realized outcome and foreign keys to decision/order/position/model/run |
| `backtest_runs` | config, data range, assumptions, metrics, artifact/report reference |
| `monitoring_events` | data-quality, drift, risk, model-load, and alert events |

Use indexes that match time-series access: `(symbol, timeframe, candle_time)` and journal queries by timestamp/model/strategy. Use migrations; do not mutate production-like schemas ad hoc.

## Configuration, Logging, and Error Handling

- Centralize configurable symbols, timeframes, indicator periods, label horizon/threshold, model settings, risk limits, cost assumptions, scheduler cadence, and alert thresholds.
- Provide safe defaults that keep AI-assisted trading disabled until explicitly enabled in paper mode.
- Keep secrets in environment variables or the repository's current secret mechanism; never log MT5 credentials or tokens.
- Use structured logs with correlation IDs for ingestion, training, inference, decision, order, and backtest runs.
- Return clear validation errors. For data/model/risk failures, fail closed to no new AI-assisted position and store an observable event.
- Make retries bounded and idempotent for ingestion/jobs; do not retry an order-like action without an idempotency key.

## Testing Requirements

- Unit tests: feature calculations/alignment, label horizon, regime rules, sizing, risk vetoes, cost calculations, registry state transitions, and API validation.
- Integration tests: ingest -> feature -> inference -> decision -> simulated order -> journal; and candidate training -> evaluation -> manual promotion -> rollback.
- Backtest regression tests: a deterministic fixture validates identical results under a fixed config/seed.
- Leakage tests: assert temporal ordering, no feature access after decision time, no overlap without purge/embargo, and training-only preprocessing.
- API contract tests maintain existing routes and verify `paper_only` safeguards.
- UI tests only where the repository already has a suitable test setup; otherwise add focused component behavior checks rather than a new testing stack.

## Security and Operational Safety

- Enforce paper mode in configuration, API/service guards, and the execution adapter; a UI toggle alone is insufficient.
- Keep live-trading code out of scope. If a future live mode is proposed, require a separate specification, explicit user approval, and independent safety review.
- Authenticate/authorize administrative actions such as training, promotion, and configuration changes according to the current app's access model.
- Sanitize/log-limit errors and user-provided parameters. Validate symbol/timeframe allowlists and date ranges.
- Maintain audit logs for model promotion, risk configuration changes, and manually triggered retraining/backtests.

## Phased Implementation Plan and Acceptance Criteria

### Phase 0 — Discovery and Baseline Preservation

Document the current system, run its tests, select the smallest integration points, and add no behavior change except perhaps observability tests.

**Acceptance:** architecture note and phased plan are reviewed; existing relevant tests still pass; current deterministic paper strategy behavior is unchanged.

### Phase 1 — Data Contract and Journal Foundation

Normalize candle ingestion/store access, add quality checks, and ensure decision/order/trade journaling can link existing paper trades.

**Acceptance:** idempotent candle persistence works for a fixture; gaps/duplicates are observable; a sample paper trade can be reconstructed from journal records.

### Phase 2 — Reproducible Features and Labels

Implement `core-v1` point-in-time features and the configurable future-return label, shared across offline and paper inference paths.

**Acceptance:** indicator/label tests pass; feature rows contain no future data; a dataset snapshot records feature and label versions; warm-up/gap behavior is explicit.

### Phase 3 — Cost-Aware Baseline Backtest

Bring the deterministic strategy through a realistic common backtest path with spread/commission/slippage and walk-forward scaffolding.

**Acceptance:** fixed fixtures yield stable metrics; no same-candle look-ahead; reports include profit factor, drawdown, Sharpe assumptions, win rate, and cost breakdown.

### Phase 4 — XGBoost Candidate Pipeline

Train and register candidates using strict time-series validation, calibration, metrics, and artifacts. No production inference change yet.

**Acceptance:** a training run creates a candidate with metadata/checksum and walk-forward report; leakage tests pass; calibration and precision/recall metrics are reported where appropriate.

### Phase 5 — AI-Assisted Paper Decisions

Add rule-based regimes, AI probability gates, risk vetoes, and champion-model inference to the paper strategy alongside the deterministic baseline.

**Acceptance:** every paper decision records model/regime/risk reasons; invalid data/model states create no trade; paper-only tests pass; deterministic baseline remains selectable.

### Phase 6 — Registry, Dashboard, and Controlled Operations

Add champion/candidate comparison, manual promotion/rollback, scheduled candidate-only retraining, drift health, and focused dashboard views.

**Acceptance:** manual promotion and rollback are audited; retraining cannot self-promote; drift/data/model-health events appear in API/dashboard; the dashboard displays decisions and journal records without exposing secrets.

## Recommended Folder Structure

Adapt this to the repository's current layout. Do not move working modules simply to match these names.

```text
app/
  api/                 # existing FastAPI routes/schemas
  market_data/         # MT5/feed adapter, normalization, quality checks
  features/            # feature definitions and point-in-time dataset builder
  labels/               # target definitions
  ml/                   # training, validation, calibration, inference, registry
  strategies/           # existing baseline plus AI-assisted rules and regimes
  risk/                 # sizing, limits, vetoes
  execution/            # paper-only simulator/adapters
  backtesting/          # shared simulation/reporting
  journal/              # decision/trade audit access
  monitoring/           # data quality and drift
  workers/              # existing background-job integration
  config/
tests/
  unit/
  integration/
  fixtures/
data/                   # local/dev data only; ignored when appropriate
artifacts/              # model/backtest outputs; usually ignored or externalized
```

## Concrete Codex Execution Prompt / Checklist

Copy the following into a Codex task when ready to implement:

```text
Enhance this existing paper-trading repository according to AI_TRADING_LAB_ENHANCEMENT_SPEC.md.

First, do not edit code. Inspect README, dependencies, startup scripts, current API/worker/MT5 integration, persistence, strategy/indicator/backtest logic, frontend, configuration, and tests. Summarize the existing architecture, identify the smallest safe extension points, run the relevant baseline tests, and propose a Phase 0–1 implementation plan that preserves all working behavior. Ask for confirmation only if a decision materially changes scope or requires destructive migration.

After the plan, implement exactly one phase at a time. Before each phase, state files to change and compatibility risks. Reuse existing patterns and contracts; do not rewrite functioning modules or add infrastructure without a demonstrated need. Keep the system paper-only: no live execution path, no automatic model promotion, and fail closed to no AI-assisted trade when data/model/risk checks fail.

For every phase:
1. Implement the smallest cohesive change.
2. Add/update focused tests, including time-series leakage tests for ML/data changes.
3. Run relevant tests and report results.
4. Provide migrations/configuration/documentation needed to use the change.
5. Stop at the phase boundary and summarize what changed, what remains, risks, and the recommended next phase.

Use shared point-in-time feature, strategy, risk, and execution paths for training, backtesting, and paper inference. Use time-ordered walk-forward validation with purge/embargo for overlapping labels. Register models as candidates first; require a manual, audited promotion to champion after cost-aware out-of-sample comparison against the current champion and deterministic baseline.
```

## Final Guardrail

Treat the lab as a decision-research and simulation system. A good result is not merely a high backtest return; it is a reproducible, cost-aware, leakage-resistant process whose model decisions, risk controls, and paper-trading outcomes can be independently inspected.
