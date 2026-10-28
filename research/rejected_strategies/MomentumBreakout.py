"""
Momentum breakout (15m, with a 1h trend filter).

Idea: when price breaks out of its recent range on strong volume inside an uptrend,
it often keeps running. Fewer trades than the scalpers, but bigger targets, so
fees matter less.

- Trend (1h): close > EMA50 > EMA200 and ADX shows a real trend.
- Trigger (15m): close above the highest high of the last `breakout_window` candles,
  volume at least `volume_mult` x its 20-candle average, RSI strong but not overheated.
- Exits: RiskManagedStrategy's stops/targets with a wider trail to let winners run.
"""

from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, informative

from risk_managed_base import RiskManagedStrategy


class MomentumBreakout(RiskManagedStrategy):
    timeframe = "15m"
    # 1h EMA200 needs ~200 hours of history: 800 x 15m candles.
    startup_candle_count = 850

    trail_start_r = 2.0
    trail_distance_r = 1.5

    atr_stop_mult = DecimalParameter(1.0, 3.0, default=2.0, decimals=1, space="sell")
    reward_risk = DecimalParameter(1.5, 6.0, default=4.0, decimals=1, space="sell")
    max_hold_candles = IntParameter(16, 192, default=96, space="sell")

    breakout_window = IntParameter(10, 48, default=20, space="buy")
    volume_mult = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="buy")
    rsi_max = IntParameter(65, 85, default=75, space="buy")
    adx_min_1h = IntParameter(15, 35, default=20, space="buy")

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        range_high = dataframe["high"].rolling(self.breakout_window.value).max().shift(1)
        conditions = [
            dataframe["close_1h"] > dataframe["ema50_1h"],
            dataframe["ema50_1h"] > dataframe["ema200_1h"],
            dataframe["adx_1h"] > self.adx_min_1h.value,
            dataframe["close"] > range_high,
            dataframe["volume"] > self.volume_mult.value * dataframe["volume_mean"],
            dataframe["rsi"] > 55,
            dataframe["rsi"] < self.rsi_max.value,
            dataframe["volume"] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, conditions), ["enter_long", "enter_tag"]] = (
            1,
            "breakout",
        )
        return dataframe
