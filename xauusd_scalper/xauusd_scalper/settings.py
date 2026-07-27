"""
Central configuration for the gold scalping engine.
Tune the strategy here - the modules under src/ shouldn't need touching
for routine parameter changes.
"""

from src.risk_manager import RiskConfig

SYMBOL = "XAUUSD"

# --- Data ---
RAW_DATA_PATH = "data/raw/XAUUSD_sample.csv"
PROCESSED_DATA_PATH = "data/processed/XAUUSD_clean.csv"

# --- Alpha Model ---
EMA_FAST = 9
EMA_SLOW = 21
ATR_PERIOD = 14
ATR_SPIKE_MULT = 3.0   # veto signals when ATR >= 3x its rolling average (extreme volatility)
ATR_QUIET_MULT = 0.3   # ignore crossovers when ATR <= 0.3x its rolling average (dead-market noise)
WARMUP_BARS = 50        # ignore signals until indicators have settled

# --- Risk Manager ---
RISK_CONFIG = RiskConfig(
    starting_equity=100.0,
    risk_per_trade_pct=1.0,
    max_daily_drawdown_pct=2.0,
    atr_spike_mult=ATR_SPIKE_MULT,
    stop_loss_atr_mult=1.5,
    max_trades_per_day=20,
)

# --- Execution ---
SLIPPAGE_POINTS = 0.05
LIMIT_ORDER_OFFSET = 0.02
