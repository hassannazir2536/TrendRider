"""
Bollinger mean-reversion scalper (5m, with a 1h regime filter).

Idea: sharp drops below the lower Bollinger Band often snap back toward the middle
band. We only buy these dips while the bigger picture is bullish, so we are not
catching a falling knife in a bear market.

- Regime (1h): close > EMA200.
- Setup (5m): previous candle closed below the lower band with RSI oversold.
- Trigger (5m): a green candle that closes above the previous close.
- Filters: bands wide enough to profit after fees, volatility not extreme.
- Exits: price back at the middle band, or RiskManagedStrategy's stops/targets.
"""

from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import DecimalParameter, IntParameter, informative

from risk_managed_base import RiskManagedStrategy


class BollingerReversionScalper(RiskManagedStrategy):
    timeframe = "5m"

    atr_stop_mult = DecimalParameter(1.0, 3.0, default=2.0, decimals=1, space="sell")
    reward_risk = DecimalParameter(1.0, 4.0, default=1.5, decimals=1, space="sell")
    max_hold_candles = IntParameter(12, 144, default=36, space="sell")

    rsi_oversold = IntParameter(20, 40, default=30, space="buy")
    min_bb_width = DecimalParameter(0.004, 0.02, default=0.008, decimals=3, space="buy")
    max_atr_pct = DecimalParameter(0.004, 0.02, default=0.012, decimals=3, space="buy")

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_mid"] = bb["mid"]
        dataframe["bb_upper"] = bb["upper"]
        dataframe["bb_width"] = (bb["upper"] - bb["lower"]) / bb["mid"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            dataframe["close_1h"] > dataframe["ema200_1h"],
            dataframe["close"].shift(1) < dataframe["bb_lower"].shift(1),
            dataframe["rsi"].shift(1) < self.rsi_oversold.value,
            dataframe["close"] > dataframe["open"],
            dataframe["close"] > dataframe["close"].shift(1),
            dataframe["bb_width"] > self.min_bb_width.value,
            dataframe["atr"] / dataframe["close"] < self.max_atr_pct.value,
            dataframe["volume"] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, conditions), ["enter_long", "enter_tag"]] = (
            1,
            "bb_reversion",
        )
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] > dataframe["bb_mid"], ["exit_long", "exit_tag"]] = (
            1,
            "bb_mid_reached",
        )
        return dataframe
