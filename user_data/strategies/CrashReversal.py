"""
CrashReversal: buy a coin right after a sharp one-day crash, sell about a day later.

Rule:
- Enter at the next hourly open when a coin has fallen more than `drop_threshold`
  (default 8%) over the last 24 hours.
- Exit after `hold_hours` (default 24), whatever the price. No profit target.
- A wide -25% disaster stop, kept on the exchange as a stop-limit order, caps the damage
  if a coin collapses. Tighter stops (-10%/-12%) were tested and ruined the strategy:
  they were hit during the crash and then the coin rebounded without us.

Why: research/signal_study.py on 20 large coins (2024-2026) found that sharp 24h crashes
were followed by a rebound averaging +0.6% to +1.0% net of fees over the next 12-24h,
in both the design period and the later unseen period, on 15-17 of the 20 coins.
Deeper crashes bounced harder, which makes a lucky fluke less likely.

This only works as many small bets. Backtests with 4 slots (25% of capital each) lost
money because the bot could only take the first few signals of a market-wide crash.
With 20 slots (5% each) it was profitable in both periods. Keep max_open_trades equal
to the number of pairs, which means at least ~200 USDT so each 5% slice clears
Binance's minimum order size.

Trades are clustered: a market-wide crash fires on many coins at once, so the bot's
capital is exposed exactly when markets are most violent. Real fills in a crash are worse
than a backtest assumes. Keep this strategy's capital separate from TrendRider's.
"""

from datetime import datetime, timedelta

from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, Trade


class CrashReversal(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1h"
    startup_candle_count = 30
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

    drop_threshold = DecimalParameter(-0.15, -0.05, default=-0.08, decimals=2, space="buy", optimize=False)
    hold_hours = IntParameter(4, 48, default=24, space="sell", optimize=False)

    @property
    def protections(self):
        # Do not re-buy a coin within a few hours of exiting it.
        return [{"method": "CooldownPeriod", "stop_duration_candles": 4}]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ret24"] = dataframe["close"].pct_change(24)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["ret24"] < self.drop_threshold.value) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "crash_24h")
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
        if current_time - trade.open_date_utc >= timedelta(hours=self.hold_hours.value):
            return "time_exit"
        return None
