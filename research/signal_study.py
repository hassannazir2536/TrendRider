"""
Signal study: does a setup actually predict price going up by more than fees?

For each candidate entry signal, this measures the average return from entering at the
next candle's open and exiting `h` candles later, using non-overlapping events.
Results are split into an in-sample period and a later out-of-sample period, so a
signal only looks good if it holds up on data it was not designed on.

By default events are pooled across all pairs, and "pairs+" counts how many individual
pairs were profitable on their own. Use --per-pair to see every pair separately.

Usage:
    .venv\\Scripts\\python.exe research\\signal_study.py --timeframe 1h --horizons 4 12 24 48
    .venv\\Scripts\\python.exe research\\signal_study.py --timeframe 5m --horizons 6 24 --pairs BTC/USDT SOL/USDT
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import talib


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "user_data" / "data" / "binance"


def default_pairs() -> list[str]:
    config = json.loads((ROOT / "user_data" / "config.json").read_text(encoding="utf-8"))
    return config["exchange"]["pair_whitelist"]


def load(pair: str, timeframe: str) -> pd.DataFrame | None:
    path = DATA_DIR / f"{pair.replace('/', '_')}-{timeframe}.feather"
    if not path.exists():
        print(f"(no {timeframe} data for {pair}, skipping)")
        return None
    return pd.read_feather(path).sort_values("date").reset_index(drop=True)


def add_indicators(df: pd.DataFrame, candles_per_hour: int) -> pd.DataFrame:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    # Trend filter equivalent to a 1h EMA200, whatever the base timeframe.
    df["ema_trend"] = talib.EMA(c, 200 * candles_per_hour)
    df["ema_trend_fast"] = talib.EMA(c, 50 * candles_per_hour)
    df["ema20"] = talib.EMA(c, 20)
    df["ema50"] = talib.EMA(c, 50)
    df["rsi14"] = talib.RSI(c, 14)
    df["rsi2"] = talib.RSI(c, 2)
    df["atr"] = talib.ATR(h, l, c, 14)
    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    df["bb_lower"] = mid - 2 * std
    df["bb_upper"] = mid + 2 * std
    df["vol_mean"] = v.rolling(20).mean()
    df["high20"] = h.rolling(20).max().shift(1)
    df["high55"] = h.rolling(55).max().shift(1)
    df["ret12"] = c.pct_change(12)
    df["ret24"] = c.pct_change(24)
    df["zscore"] = (c - mid) / std
    df["down3"] = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
    return df


def signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    up = (df["close"] > df["ema_trend"]) & (df["ema_trend_fast"] > df["ema_trend"])
    ema_cross_up = (df["ema20"] > df["ema50"]) & (df["ema20"].shift(1) <= df["ema50"].shift(1))
    return {
        "baseline_every_candle": pd.Series(True, index=df.index),
        "uptrend_regime": up,
        "rsi14<30": df["rsi14"] < 30,
        "rsi14<25 & uptrend": (df["rsi14"] < 25) & up,
        "rsi14<30 & uptrend": (df["rsi14"] < 30) & up,
        "rsi2<10 & uptrend": (df["rsi2"] < 10) & up,
        "rsi2<5 & uptrend": (df["rsi2"] < 5) & up,
        "below_bb & uptrend": (df["close"] < df["bb_lower"]) & up,
        "zscore<-2.5": df["zscore"] < -2.5,
        "zscore<-3": df["zscore"] < -3,
        "zscore<-2.5 & uptrend": (df["zscore"] < -2.5) & up,
        "down3 & uptrend": df["down3"] & up,
        "breakout20+vol & uptrend": (df["close"] > df["high20"])
        & (df["volume"] > 1.5 * df["vol_mean"])
        & up,
        "breakout55": df["close"] > df["high55"],
        "breakout55 & uptrend": (df["close"] > df["high55"]) & up,
        "ema20x50_up": ema_cross_up,
        "ema20x50_up & uptrend": ema_cross_up & up,
        "momentum ret24>5%": df["ret24"] > 0.05,
        "crash ret12<-4%": df["ret12"] < -0.04,
        "crash ret24<-5%": df["ret24"] < -0.05,
        "crash ret24<-8%": df["ret24"] < -0.08,
        "crash ret24<-5% & uptrend": (df["ret24"] < -0.05) & up,
    }


def event_returns(df: pd.DataFrame, mask: pd.Series, horizon: int) -> np.ndarray:
    """Entry at next open, exit at open `horizon` candles later. Events never overlap."""
    opens = df["open"].to_numpy()
    idx = np.flatnonzero(mask.fillna(False).to_numpy())
    rets = []
    next_free = -1
    for i in idx:
        entry, exit_ = i + 1, i + 1 + horizon
        if i < next_free or exit_ >= len(opens):
            continue
        rets.append(opens[exit_] / opens[entry] - 1)
        next_free = exit_
    return np.asarray(rets)


def summarize(rets: np.ndarray, fee: float) -> str:
    if len(rets) < 10:
        return f"{'n<10':>36}"
    net = rets - fee
    t = net.mean() / (net.std(ddof=1) / np.sqrt(len(net))) if net.std() > 0 else 0
    return f"n={len(rets):5d} net={net.mean() * 100:+6.2f}% win={np.mean(net > 0) * 100:3.0f}% t={t:+5.1f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--horizons", type=int, nargs="+", default=[4, 12, 24, 48])
    parser.add_argument("--pairs", nargs="+", default=None, help="Default: pair_whitelist in config.json")
    parser.add_argument("--split", default="2026-01-01", help="Start of out-of-sample period")
    parser.add_argument("--fee", type=float, default=0.002, help="Round-trip fee ratio (0.002 = 0.1%% per side)")
    parser.add_argument("--per-pair", action="store_true", help="Show every pair instead of pooling")
    args = parser.parse_args()

    candles_per_hour = {"1m": 60, "5m": 12, "15m": 4, "1h": 1}[args.timeframe]
    split = pd.Timestamp(args.split, tz="UTC")

    frames = {}
    for pair in args.pairs or default_pairs():
        df = load(pair, args.timeframe)
        if df is None:
            continue
        df = add_indicators(df, candles_per_hour)
        # Skip indicator warm-up.
        frames[pair] = df.iloc[200 * candles_per_hour :].reset_index(drop=True)

    names = list(signals(next(iter(frames.values()))).keys())
    periods = {"IS": lambda df: df["date"] < split, "OOS": lambda df: df["date"] >= split}
    print(f"{len(frames)} pairs: {', '.join(p.split('/')[0] for p in frames)}")
    for horizon in args.horizons:
        hours = horizon / candles_per_hour
        print(f"\n=== {args.timeframe}, hold {horizon} candles ({hours:g}h), net of {args.fee:.2%} fees ===")
        for name in names:
            pooled = {label: [] for label in periods}
            per_pair_cells = []
            for pair, df in frames.items():
                mask = signals(df)[name]
                for label, in_period in periods.items():
                    rets = event_returns(df, mask & in_period(df), horizon)
                    pooled[label].append(rets)
                    per_pair_cells.append(f"{pair.split('/')[0]} {label}: {summarize(rets, args.fee)}")
            if args.per_pair:
                print(f"{name:28s} | " + " | ".join(per_pair_cells))
                continue
            cells = []
            for label, groups in pooled.items():
                scored = [g for g in groups if len(g) >= 10]
                positive = sum(1 for g in scored if (g - args.fee).mean() > 0)
                all_rets = np.concatenate(groups) if groups else np.array([])
                cells.append(f"{label}: {summarize(all_rets, args.fee)} pairs+={positive:2d}/{len(scored):2d}")
            print(f"{name:28s} | " + " | ".join(cells))


if __name__ == "__main__":
    main()
