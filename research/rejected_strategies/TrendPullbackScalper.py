"""
Trend pullback scalper (5m, with a 1h trend filter).

Idea: in a healthy uptrend, short dips to the fast moving average tend to get bought.
We wait for the dip, then enter when price turns back up.

- Trend (1h): close > EMA50 > EMA200 and ADX shows a real trend.
- Setup (5m): EMA21 > EMA50, price touched EMA21 in the last few candles,
  and RSI cooled off below `rsi_dip`.
- Trigger (5m): a green candle that closes back above EMA9 with RSI rising,
  without having broken below EMA50.
- Exits: handled by RiskManagedStrategy, plus an exit when the 1h trend breaks.
"""

from functools import reduce

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IntParameter, informative

from risk_managed_base import RiskManagedStrategy


class TrendPullbackScalper(RiskManagedStrategy):
    timeframe = "5m"

    rsi_dip = IntParameter(30, 50, default=42, space="buy")
    pullback_lookback = IntParameter(2, 8, default=4, space="buy")
    adx_min_1h = IntParameter(15, 35, default=20, space="buy")

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        lookback = self.pullback_lookback.value
        touched_ema21 = (dataframe["low"] <= dataframe["ema21"]).astype(int).rolling(lookback).max()
        conditions = [
            dataframe["close_1h"] > dataframe["ema50_1h"],
            dataframe["ema50_1h"] > dataframe["ema200_1h"],
            dataframe["adx_1h"] > self.adx_min_1h.value,
            dataframe["ema21"] > dataframe["ema50"],
            touched_ema21 == 1,
            dataframe["rsi"].rolling(lookback).min() < self.rsi_dip.value,
            dataframe["rsi"] > dataframe["rsi"].shift(1),
            dataframe["close"] > dataframe["ema9"],
            dataframe["close"] > dataframe["open"],
            dataframe["low"].rolling(lookback).min() > dataframe["ema50"],
            dataframe["volume"] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, conditions), ["enter_long", "enter_tag"]] = (
            1,
            "trend_pullback",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe["close_1h"] < dataframe["ema50_1h"], ["exit_long", "exit_tag"]
        ] = (1, "trend_broken_1h")
        return dataframe
