"""
TrendRider: hold the coin while it is in a daily uptrend, sit in USDT otherwise.

Rule:
- Enter when the last daily close is above its `sma_period`-day simple moving average.
- Exit when the last daily close falls below it.
- A hard stop-loss, kept on the exchange, caps the damage from a crash between daily closes.

Why this and not scalping: research/signal_study.py shows that common 5m-1h entry
signals on BTC/ETH have no edge large enough to cover Binance's 0.2% round-trip fee.
research/trend_study.py shows this daily rule beat buy-and-hold on both pairs, with
smaller drawdowns, in 2024-25 and on unseen 2026 data. Neighbouring SMA lengths
(20, 100) were also profitable, so the result does not hinge on one lucky setting.

It trades rarely (a few times per month per pair) and spends roughly half the time in cash.

Position size: each coin gets a fixed slice of the strategy's capital. Slices come from
"pair_weights" in the strategy's config file (e.g. BTC 25%, ETH 15%); coins not listed
there share the remainder equally. Without "pair_weights", capital is split evenly.
"""

import logging
from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IntParameter, IStrategy, informative


logger = logging.getLogger(__name__)


class TrendRider(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    # Checked hourly so unfilled orders are retried quickly; signals only change at the daily close.
    timeframe = "1h"
    # 1d SMA needs `sma_period` days of history: 1300 hours covers up to ~54 days.
    startup_candle_count = 1300
    process_only_new_candles = True

    minimal_roi = {"0": 100}
    # Disaster stop only. The daily trend exit normally fires long before this.
    stoploss = -0.15
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        # Keeps a stop order on Binance so positions stay protected if this PC goes offline.
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    sma_period = IntParameter(20, 100, default=50, space="buy", optimize=False)

    @property
    def protections(self):
        # After a stop-loss, wait a day before buying the same pair again.
        return [{"method": "CooldownPeriod", "stop_duration_candles": 24}]

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma"] = ta.SMA(dataframe, timeperiod=self.sma_period.value)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close_1d"] > dataframe["sma_1d"]) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "daily_uptrend")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close_1d"] < dataframe["sma_1d"], ["exit_long", "exit_tag"]] = (
            1,
            "daily_downtrend",
        )
        return dataframe

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
        weights: dict[str, float] = self.config.get("pair_weights") or {}
        if not weights:
            return proposed_stake
        others = [p for p in self.config["exchange"]["pair_whitelist"] if p not in weights]
        remaining = max(0.0, 1.0 - sum(weights.values()))
        weight = weights.get(pair, remaining / len(others) if others else 0.0)
        # Total capital at cost: open positions plus free balance (honours available_capital).
        equity = self.wallets.get_total_stake_amount()
        stake = min(equity * weight, max_stake)
        # Freqtrade tops small stakes up by at most 30%. Below that the trade is impossible, so
        # pause the pair until the next candle instead of re-checking (and logging) every loop.
        if min_stake and stake * 1.3 < min_stake:
            reason = f"slice {stake:.2f} USDT < Binance minimum {min_stake:.2f} USDT"
            # Freqtrade rounds the lock end up to the next candle, i.e. the next hour.
            self.lock_pair(pair, current_time, reason)
            if pair not in self._too_small_logged:
                self._too_small_logged.add(pair)
                logger.info(
                    f"{pair}: buy signal skipped, {reason}. Raise available_capital "
                    f"or remove small coins to trade it."
                )
            return 0
        self._too_small_logged.discard(pair)
        return stake

    def bot_start(self, **kwargs) -> None:
        self._too_small_logged: set[str] = set()
