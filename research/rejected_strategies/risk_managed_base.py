"""
Shared risk management for every strategy in this project.

A strategy that inherits from RiskManagedStrategy only has to decide *when* to enter.
This base class decides *how much* to buy and *how* to get out:

- Initial stop: `atr_stop_mult` x ATR below the signal candle's close, never wider
  than the hard `stoploss`.
- Position size: risk `risk_per_trade` of total equity per trade, capped at an even
  split of the balance across `max_open_trades`. Spot only, no leverage.
- Take-profit: `reward_risk` x the initial risk (R), via custom_roi.
- Breakeven: once price has moved `breakeven_at_r` R in our favour, the stop moves
  to entry plus enough to cover fees.
- Trailing: once price has moved `trail_start_r` R, the stop trails the highest
  price by `trail_distance_r` R.
- Time stop: exit trades still open after `max_hold_candles`.
- Protections: per-pair cooldown, pause after a streak of losses, and a 24h
  drawdown limit that stops all new entries.

Subclasses must provide an "atr" column in populate_indicators.
"""

import logging
import math
from datetime import datetime, timedelta

from pandas import DataFrame

from freqtrade.enums import RunMode
from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
    IStrategy,
    Trade,
    stoploss_from_absolute,
    timeframe_to_minutes,
    timeframe_to_prev_date,
)


logger = logging.getLogger(__name__)


class RiskManagedStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "5m"
    # 1h EMA200 needs ~200 hours of history: 2400 x 5m candles.
    startup_candle_count = 2500
    process_only_new_candles = True

    # Hard cap on the loss of any single trade. The ATR stop is normally much tighter.
    stoploss = -0.04
    use_custom_stoploss = True
    use_custom_roi = True
    use_exit_signal = True
    exit_profit_only = False
    # Take-profit comes from custom_roi; this table only disables the default ROI.
    minimal_roi = {"0": 1.0}

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        # Keeps a stop order on Binance so trades stay protected if this PC goes offline.
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    # --- Risk settings -------------------------------------------------------------
    risk_per_trade = 0.01
    # Stop moves to entry + this ratio at breakeven, enough to cover 2 x 0.1% fees.
    breakeven_buffer = 0.0025
    breakeven_at_r = 1.0
    trail_start_r = 1.5
    trail_distance_r = 1.0

    atr_stop_mult = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="sell")
    reward_risk = DecimalParameter(1.0, 4.0, default=2.0, decimals=1, space="sell")
    max_hold_candles = IntParameter(24, 288, default=72, space="sell")

    @property
    def protections(self):
        return [
            # Wait a few candles before re-entering the same pair after an exit.
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            # 3 losing stop-outs within 3 hours -> pause all pairs for 2 hours.
            {
                "method": "StoplossGuard",
                "lookback_period": 180,
                "trade_limit": 3,
                "stop_duration": 120,
                "only_per_pair": False,
            },
            # Daily loss limit: >4% drawdown within 24h -> stop new entries for 12 hours.
            {
                "method": "MaxDrawdown",
                "lookback_period": 1440,
                "trade_limit": 3,
                "stop_duration": 720,
                "max_allowed_drawdown": 0.04,
            },
        ]

    def bot_start(self, **kwargs) -> None:
        self._initial_stops: dict[int, float] = {}
        # Live and dry-run trades survive restarts, so their stop is stored in the database.
        self._persist_stops = self.config.get("runmode") in (RunMode.LIVE, RunMode.DRY_RUN)

    def _signal_candle(self, pair: str, trade: Trade):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None
        open_candle = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        signal_date = open_candle - timedelta(minutes=timeframe_to_minutes(self.timeframe))
        candle = df.loc[df["date"] == signal_date]
        return candle.iloc[-1] if not candle.empty else df.iloc[-1]

    def _initial_stop(self, pair: str, trade: Trade) -> float | None:
        stop = self._initial_stops.get(trade.id)
        if stop is not None:
            return stop
        if self._persist_stops:
            stop = trade.get_custom_data("initial_stop")
        if stop is None:
            candle = self._signal_candle(pair, trade)
            if candle is None:
                return None
            stop = candle["close"] - self.atr_stop_mult.value * candle["atr"]
            hard_stop = trade.open_rate * (1 + self.stoploss)
            if not math.isfinite(stop) or stop >= trade.open_rate:
                stop = hard_stop
            stop = max(stop, hard_stop)
            if self._persist_stops:
                trade.set_custom_data("initial_stop", stop)
        self._initial_stops[trade.id] = stop
        return stop

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return proposed_stake
        last = df.iloc[-1]
        stop_distance = self.atr_stop_mult.value * last["atr"] / last["close"]
        if not math.isfinite(stop_distance) or stop_distance <= 0:
            return proposed_stake
        stop_distance = min(stop_distance, abs(self.stoploss))
        equity = self.wallets.get_total_stake_amount()
        risk_stake = equity * self.risk_per_trade / stop_distance
        return min(risk_stake, proposed_stake)

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        stop = self._initial_stop(pair, trade)
        if stop is None:
            return None
        risk = trade.open_rate - stop
        if trade.max_rate >= trade.open_rate + self.breakeven_at_r * risk:
            stop = max(stop, trade.open_rate * (1 + self.breakeven_buffer))
        if trade.max_rate >= trade.open_rate + self.trail_start_r * risk:
            stop = max(stop, trade.max_rate - self.trail_distance_r * risk)
        return stoploss_from_absolute(
            stop, current_rate, is_short=trade.is_short, leverage=trade.leverage
        )

    def custom_roi(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        trade_duration: int,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float | None:
        stop = self._initial_stop(pair, trade)
        if stop is None:
            return None
        return self.reward_risk.value * (trade.open_rate - stop) / trade.open_rate

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        max_minutes = self.max_hold_candles.value * timeframe_to_minutes(self.timeframe)
        if current_time - trade.open_date_utc >= timedelta(minutes=max_minutes):
            return "time_exit"
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
