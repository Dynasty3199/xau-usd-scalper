"""
Execution Router
----------------
Turns an approved signal into an order. Ships with a fully working
SimulatedBroker for backtesting. LiveBroker is an intentional, documented
stub - wiring real capital to a broker requires YOUR OWN credentials and
their official SDK/FIX engine, which this local sandbox does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Order:
    timestamp: object
    side: str                    # "buy" or "sell"
    size: float
    order_type: str = "limit"    # "limit" avoids the slippage a market order pays
    limit_offset: float = 0.02   # price improvement assumed for a resting limit order


@dataclass
class Fill:
    timestamp: object
    side: str
    size: float
    price: float


class SimulatedBroker:
    """Paper/backtest execution: fills orders against the current bar with a
    simple slippage model. Never touches the network."""

    def __init__(self, slippage_points: float = 0.05):
        self.slippage_points = slippage_points
        self.fills: list[Fill] = []

    def execute(self, order: Order, market_price: float) -> Fill:
        direction = 1 if order.side == "buy" else -1

        if order.order_type == "limit":
            # Assume the limit rests slightly better than market and fills there.
            fill_price = market_price - direction * order.limit_offset
        else:
            # Market order: pays slippage against the trader.
            fill_price = market_price + direction * self.slippage_points

        fill = Fill(order.timestamp, order.side, order.size, fill_price)
        self.fills.append(fill)
        logger.debug("Filled %s %.4f @ %.2f", order.side, order.size, fill_price)
        return fill


class LiveBroker:
    """
    Placeholder for live execution. Intentionally NOT implemented here.

    To go live, wire this up to your broker's actual API (a FIX engine, or
    a REST/WebSocket API such as OANDA, IG, or Interactive Brokers) using
    your own credentials and their official client library. That's
    broker-specific, requires a funded account, and should only touch real
    capital after extensive paper trading and a careful read of your
    broker's terms, margin rules, and rate limits.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "LiveBroker is a placeholder. Plug in your broker's official SDK/FIX "
            "engine here once you've validated the strategy with SimulatedBroker."
        )

    def execute(self, order: Order, market_price: float) -> Fill:
        raise NotImplementedError
