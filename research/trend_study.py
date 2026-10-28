"""
Trend-following study: long-or-cash rules on 4h and daily candles versus buy-and-hold.

Each rule decides at a candle close whether to hold the coin or USDT, and trades at the
next candle's open, paying `FEE` per side. Results are shown for an in-sample and a
later out-of-sample period.

By default each rule is summarized across all pairs:
  avg / med  - average and median return of the individual pairs
  port       - return of an equal-weight portfolio running the rule on every pair
  dd         - that portfolio's worst drawdown
  >B&H       - how many pairs beat their own buy-and-hold return
Use --per-pair to see every pair separately.

Usage:
    .venv\\Scripts\\python.exe research\\trend_study.py
    .venv\\Scripts\\python.exe research\\trend_study.py --per-pair --pairs BTC/USDT ETH/USDT
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "user_data" / "data" / "binance"
FEE = 0.001


def default_pairs() -> list[str]:
    config = json.loads((ROOT / "user_data" / "config.json").read_text(encoding="utf-8"))
    return config["exchange"]["pair_whitelist"]


def load(pair: str, rule: str) -> pd.DataFrame | None:
    path = DATA_DIR / f"{pair.replace('/', '_')}-1h.feather"
    if not path.exists():
        print(f"(no 1h data for {pair}, skipping)")
        return None
    df = pd.read_feather(path).set_index("date")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).agg(agg).dropna()


def donchian(df: pd.DataFrame, entry: int, exit_: int) -> pd.Series:
    upper = df["high"].rolling(entry).max().shift(1)
    lower = df["low"].rolling(exit_).min().shift(1)
    pos = pd.Series(np.nan, index=df.index)
    pos[df["close"] > upper] = 1
    pos[df["close"] < lower] = 0
    return pos.ffill().fillna(0)


def rules(df: pd.DataFrame) -> dict[str, pd.Series]:
    c = df["close"]
    ema = lambda n: c.ewm(span=n, adjust=False).mean()  # noqa: E731
    above_sma = lambda n: (c > c.rolling(n).mean()).astype(float)  # noqa: E731
    return {
        "buy_and_hold": pd.Series(1.0, index=df.index),
        "close>SMA20": above_sma(20),
        "close>SMA30": above_sma(30),
        "close>SMA50": above_sma(50),
        "close>SMA75": above_sma(75),
        "close>SMA100": above_sma(100),
        "EMA20>EMA50": (ema(20) > ema(50)).astype(float),
        "EMA50>EMA200": (ema(50) > ema(200)).astype(float),
        "EMA10>EMA30": (ema(10) > ema(30)).astype(float),
        "donchian20/10": donchian(df, 20, 10),
        "donchian55/20": donchian(df, 55, 20),
        "blend SMA20/50/100": (above_sma(20) + above_sma(50) + above_sma(100)) / 3,
    }


def strategy_returns(df: pd.DataFrame, pos: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Per-candle net return of following `pos`, and the position changes (trades)."""
    # Decide at the close of candle t, hold from the open of t+1.
    held = pos.shift(1).fillna(0)
    ret = df["open"].pct_change().shift(-1).fillna(0)  # open(t) -> open(t+1)
    trades = held.diff().abs().fillna(held.iloc[0])
    return held * ret - trades * FEE, trades


def window_stats(returns: pd.Series) -> tuple[float, float]:
    equity = (1 + returns).cumprod()
    return equity.iloc[-1] - 1, (equity / equity.cummax() - 1).min()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", default=None, help="Default: pair_whitelist in config.json")
    parser.add_argument("--start", default="2024-03-01")
    parser.add_argument("--split", default="2026-01-01")
    parser.add_argument("--per-pair", action="store_true")
    args = parser.parse_args()
    start = pd.Timestamp(args.start, tz="UTC")
    split = pd.Timestamp(args.split, tz="UTC")
    end = pd.Timestamp("2100-01-01", tz="UTC")
    periods = {"IS": (start, split), "OOS": (split, end)}

    for tf in ("4h", "1D"):
        frames = {p: df for p in (args.pairs or default_pairs()) if (df := load(p, tf)) is not None}
        print(f"\n=== {tf} candles, {len(frames)} pairs, {FEE:.1%} fee per side ===")
        bh = {}
        for name in rules(next(iter(frames.values()))):
            per_pair = {label: {} for label in periods}
            series = {label: {} for label in periods}
            trades_n = {label: {} for label in periods}
            for pair, df in frames.items():
                strat, trades = strategy_returns(df, rules(df)[name])
                for label, (a, b) in periods.items():
                    w = (df.index >= a) & (df.index < b)
                    per_pair[label][pair] = window_stats(strat[w])
                    series[label][pair] = strat[w]
                    trades_n[label][pair] = int(trades[w].sum())
            if name == "buy_and_hold":
                bh = per_pair
            if args.per_pair:
                cells = [
                    f"{pair.split('/')[0]} {label}: ret={per_pair[label][pair][0] * 100:+7.1f}% "
                    f"dd={per_pair[label][pair][1] * 100:6.1f}% n={trades_n[label][pair]:3d}"
                    for pair in frames
                    for label in periods
                ]
                print(f"{name:18s} | " + " | ".join(cells))
                continue
            cells = []
            for label in periods:
                rets = np.array([r for r, _ in per_pair[label].values()])
                beat = sum(1 for p in frames if per_pair[label][p][0] > bh[label][p][0])
                portfolio = pd.concat(series[label].values(), axis=1).fillna(0).mean(axis=1)
                p_ret, p_dd = window_stats(portfolio)
                cells.append(
                    f"{label}: avg={rets.mean() * 100:+6.1f}% med={np.median(rets) * 100:+6.1f}% "
                    f"port={p_ret * 100:+6.1f}% dd={p_dd * 100:6.1f}% >B&H={beat:2d}/{len(frames)}"
                )
            print(f"{name:18s} | " + " | ".join(cells))


if __name__ == "__main__":
    main()
