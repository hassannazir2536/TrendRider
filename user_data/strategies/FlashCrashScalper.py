"""
FlashCrashScalper: buy a coin minutes after a sudden plunge, sell a few hours later.

Rule (5m candles):
- Enter at the next candle open when a coin has fallen more than `drop_threshold`
  (default 5%) over the last `lookback` candles (default 24 = 2 hours).
- Exit after `hold_candles` (default 72 = 6 hours), whatever the price. No profit target.
- A wide -25% disaster stop, kept on the exchange as a stop-limit order, caps the damage
  if a coin collapses. A -10% stop was tested and ruined the strategy: it was hit during
  the plunge and then the coin rebounded without us.

Why: research/signal_study.py on 20 large coins found this was the only short-term
setup that beat Binance's 0.2% round-trip fee: +0.3% to +1.0% net per trade, in both
the design period and the later unseen period, on 15-18 of the coins. Every classic
scalping signal tested (RSI, Bollinger, breakouts, EMA crosses) lost money.

Status: EXPERIMENTAL. In Freqtrade backtests the edge is thin (2024-25 roughly flat with
a 40%+ drawdown; 2026 clearly positive). It only works as many small bets, so keep
max_open_trades equal to the number of pairs (needs ~200 USDT or more). Paper trade it;
do not fund it with real money unless months of paper results justify it.

Trades are clustered: a market-wide flash crash fires on many coins within the same few
minutes, and real fills during a crash are worse than a backtest assumes.
"""

from datetime import datetime, timedelta

from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, Trade, timeframe_to_minutes


class FlashCrashScalper(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "5m"
    startup_candle_count = 60
    process_only_new_candles = True

    # Exits are time-based (custom_exit). ROI is off; populate_exit_trend never signals,
    # but use_exit_signal must stay True or Freqtrade skips custom_exit entirely.
    minimal_roi = {"0": 100}
    stoploss = -0.25
    trailing_stop = False
    use_exit_signal = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    lookback = IntParameter(6, 48, default=24, space="buy", optimize=False)
    drop_threshold = DecimalParameter(-0.10, -0.03, default=-0.05, decimals=2, space="buy", optimize=False)
    hold_candles = IntParameter(6, 144, default=72, space="sell", optimize=False)

    @property
    def protections(self):
        # Do not re-buy a coin within an hour of exiting it.
        return [{"method": "CooldownPeriod", "stop_duration_candles": 12}]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ret_lookback"] = dataframe["close"].pct_change(self.lookback.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["ret_lookback"] < self.drop_threshold.value) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "flash_crash")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        hold = timedelta(minutes=self.hold_candles.value * timeframe_to_minutes(self.timeframe))
        if current_time - trade.open_date_utc >= hold:
            return "time_exit"
        return None
