# XAU/USD Scalping Engine — Local Backtesting Reference

A modular, local-first implementation of the gold scalping blueprint: Data
Ingestion → Alpha Model → Risk Manager → Execution Router, wired together by
`main.py`. It runs fully offline against CSV data, with no charting UI and
no network calls once dependencies are installed.

**This is a reference/starting-point implementation, not a production
trading system.** Treat it as scaffolding to test and extend, not as a
finished strategy.

## Before you trade with real money

- A backtest — even on real historical data — does not guarantee future
  results. Markets change; a strategy that worked last year may not work
  next year.
- This code ships with **synthetic, randomly generated data** (see below).
  A backtest against it is meaningless as a trading signal; it only proves
  the pipeline runs.
- `LiveBroker` in `src/execution_router.py` is an intentional stub. Nothing
  in this project can place a real order. Connecting to a live broker,
  sizing real positions, and managing real leverage/margin is a separate,
  serious undertaking — paper trade extensively first.
- Nothing here is financial advice.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

python3 scripts/generate_sample_data.py   # writes data/raw/XAUUSD_sample.csv
python3 main.py                           # runs the backtest
python3 tests/test_risk_manager.py        # sanity-checks the circuit breaker
```

Example output (synthetic data, your numbers will vary — a new random seed
or date range changes the run):

```
===== Backtest Summary =====
Starting equity : 10,000.00
Ending equity   : 7,750.09
Return          : -22.50%
Max drawdown    : 60.25%
Total fills     : 491
Signals vetoed  : {'no_signal': 30241, 'daily_drawdown_halt': 822, 'max_trades_reached': 356}
```

That loss is *expected and not a bug*: the sample data is a plain random
walk with no real trend, so a trend-following crossover has no edge to
find. What the run demonstrates instead is that the pipeline executes
end-to-end and that the Risk Manager actually halts trading once daily
drawdown limits are hit (see the `daily_drawdown_halt` count, and the
`WARNING` log lines) — the whole point of section 1's "risk mitigation"
philosophy. Point it at real history and the picture changes completely.

## Project structure

```
xauusd_scalper/
├── data/
│   ├── raw/            # input CSVs (sample generator writes here)
│   └── processed/      # cleaned OHLCV output from data_ingestion
├── src/
│   ├── data_ingestion.py   # CSV/tick loading, cleaning, weekend-gap handling
│   ├── alpha_model.py      # 9/21 EMA crossover + ATR filter -> signals
│   ├── risk_manager.py     # circuit breaker: drawdown/vol/size vetoes
│   └── execution_router.py # SimulatedBroker (real) + LiveBroker (stub)
├── scripts/
│   └── generate_sample_data.py
├── tests/
│   └── test_risk_manager.py
├── settings.py          # every tunable parameter lives here
├── main.py              # the event loop
└── requirements.txt
```

## Configuration

Every knob — EMA lengths, ATR thresholds, risk-per-trade, max daily
drawdown, slippage — lives in `settings.py`. Nothing else should need
editing for routine tuning. Notably:

- `ATR_SPIKE_MULT` / `ATR_QUIET_MULT`: the Alpha Model ignores crossovers
  when ATR is either an extreme multiple above its rolling average (spike)
  or a fraction below it (dead market noise).
- `RISK_CONFIG.max_daily_drawdown_pct`: once daily losses hit this, the
  Risk Manager halts *all* new entries until the next trading day — it
  cannot be overridden by a signal, by design.
- `RISK_CONFIG.risk_per_trade_pct` + `stop_loss_atr_mult`: position size is
  derived from these two, not hardcoded lot sizes.

## Using real data

Swap `data/raw/XAUUSD_sample.csv` for real history and point
`settings.RAW_DATA_PATH` at it:

- **Dukascopy** / **HistData** — free tick or minute bars, good for
  prototyping. `load_and_prepare(..., is_tick_data=True)` will resample
  raw ticks into OHLCV bars for you.
- **Databento** / **Polygon.io** — paid, more reliable for anything you'd
  trust with real capital.

`data_ingestion.clean_ohlcv` already drops the Fri-22:00→Sun-22:00 UTC
weekend gap rather than forward-filling a fake flat price through it —
adjust the exact session boundary if your broker's hours differ.

## Notes on dependencies

`pandas-ta` is used for EMA/ATR when it's importable; `alpha_model.py`
transparently falls back to a manual pandas/numpy implementation if it
isn't (some `pandas-ta` releases have had compatibility issues with newer
NumPy versions). You don't need to do anything either way — just know both
code paths exist if you're debugging an indicator value.

## Extending toward sections 3–4 of the blueprint

This local package intentionally stays dependency-light (`pandas` +
`numpy` + `pandas-ta`), matching section 5's environment. If you outgrow
it:

- **VectorBT** — swap `main.py`'s loop for vectorized signals when you
  want to sweep hundreds of `EMA_FAST`/`EMA_SLOW`/ATR combinations fast.
- **Backtrader** — port `alpha_model.py`/`risk_manager.py` into Strategy/
  Sizer classes if you want built-in event-driven order/broker simulation.
- **QuantConnect (LEAN)** or **NautilusTrader** — once you're ready for
  tick-level accuracy or a path toward live deployment, these are built
  for it; this project's module boundaries (Alpha/Risk/Execution) map
  fairly directly onto their equivalents.

## Running the tests

```bash
python3 tests/test_risk_manager.py
```

Covers: daily-drawdown halt, ATR-spike veto, position sizing math, and
that a new trading day resets the halt. No pytest dependency required,
though the `test_*` functions are pytest-discoverable if you have it.
