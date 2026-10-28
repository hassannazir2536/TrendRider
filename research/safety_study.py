"""
Safety study: which risk-reduction techniques make TrendRider's losses smaller without
giving up its return?

Each variant is a long-or-cash rule on daily candles (decide at the close, trade at the next
open, 0.1% fee per side, equal weight across pairs). Results are split into an in-sample
period and a later out-of-sample period so a tweak only counts if it helps on data it was
not designed on.

Columns:  ret = total return, dd = worst drawdown, mo- = worst calendar month,
          n = position changes per pair per year (more = more fees and whipsaws)

Usage:
    .venv\\Scripts\\python.exe research\\safety_study.py --pairs BTC/USDT ETH/USDT
    .venv\\Scripts\\python.exe research\\safety_study.py            # all coins in config.json
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


def load(pair: str) -> pd.DataFrame:
    return pd.read_feather(DATA_DIR / f"{pair.replace('/', '_')}-1d.feather").set_index("date")


def stateful(df: pd.DataFrame, enter: pd.Series, exit_: pd.Series) -> pd.Series:
    """Position (0/1) from separate enter/exit conditions, walked day by day."""
    pos = np.zeros(len(df))
    holding = False
    e, x = enter.to_numpy(), exit_.to_numpy()
    for i in range(len(df)):
        if holding and x[i]:
            holding = False
        elif not holding and e[i]:
            holding = True
        pos[i] = holding
    return pd.Series(pos, index=df.index)


def trailing(df: pd.DataFrame, base: pd.Series, drop: float) -> pd.Series:
    """Base rule plus: exit if close falls `drop` below the highest close since entry."""
    pos = np.zeros(len(df))
    close = df["close"].to_numpy()
    b = base.to_numpy()
    holding, peak = False, 0.0
    for i in range(len(df)):
        if holding:
            peak = max(peak, close[i])
            if not b[i] or close[i] < peak * (1 - drop):
                holding = False
        elif b[i] and (i == 0 or not b[i - 1]):
            holding, peak = True, close[i]
        pos[i] = holding
    return pd.Series(pos, index=df.index)


def variants(df: pd.DataFrame, btc: pd.DataFrame) -> dict[str, pd.Series]:
    c = df["close"]
    sma = lambda n: c.rolling(n).mean()  # noqa: E731
    above50 = c > sma(50)
    base = above50.astype(float)
    vol20 = c.pct_change().rolling(20).std()
    vol_scale = (0.025 / vol20).clip(0.25, 1.0)
    btc_regime = (btc["close"] > btc["close"].rolling(200).mean()).reindex(df.index).fillna(False)
    above_2d = above50 & above50.shift(1, fill_value=False)
    return {
        "base SMA50": base,
        "confirm 2 days": stateful(df, above_2d, ~above50),
        "exit below SMA20": stateful(df, above50, c < sma(20)),
        "trailing 15%": trailing(df, above50, 0.15),
        "trailing 20%": trailing(df, above50, 0.20),
        "vol-scaled size": base * vol_scale,
        "BTC regime filter": (above50 & btc_regime).astype(float),
        "blend SMA20/50/100": sum((c > sma(n)).astype(float) for n in (20, 50, 100)) / 3,
        "confirm2 + vol-scaled": stateful(df, above_2d, ~above50) * vol_scale,
        "vol-scaled + trail 20%": trailing(df, above50, 0.20) * vol_scale,
    }


def strategy_returns(df: pd.DataFrame, pos: pd.Series) -> tuple[pd.Series, pd.Series]:
    held = pos.shift(1).fillna(0)
    ret = df["open"].pct_change().shift(-1).fillna(0)
    change = held.diff().abs().fillna(held.iloc[0])
    return held * ret - change * FEE, change


def stats(returns: pd.Series) -> dict:
    equity = (1 + returns).cumprod()
    monthly = equity.resample("ME").last().pct_change().dropna()
    return {
        "ret": equity.iloc[-1] - 1,
        "dd": (equity / equity.cummax() - 1).min(),
        "worst_month": monthly.min() if len(monthly) else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", default=None)
    parser.add_argument("--start", default="2024-03-01")
    parser.add_argument("--split", default="2026-01-01")
    args = parser.parse_args()
    start, split = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.split, tz="UTC")
    end = pd.Timestamp("2100-01-01", tz="UTC")
    periods = {"IS": (start, split), "OOS": (split, end)}

    pairs = args.pairs or default_pairs()
    frames = {p: load(p) for p in pairs}
    btc = load("BTC/USDT")
    names = list(variants(next(iter(frames.values())), btc).keys())
    print(f"{len(frames)} pairs, equal weight: {', '.join(p.split('/')[0] for p in frames)}")
    print(f"{'variant':24s} | {'IS: ret     dd    mo-    n':34s} | OOS: ret     dd    mo-    n")
    for name in names:
        cells = []
        for label, (a, b) in periods.items():
            series, changes = [], []
            for pair, df in frames.items():
                strat, change = strategy_returns(df, variants(df, btc)[name])
                w = (df.index >= a) & (df.index < b)
                series.append(strat[w])
                changes.append(change[w].sum() / (w.sum() / 365.25))
            portfolio = pd.concat(series, axis=1).fillna(0).mean(axis=1)
            s = stats(portfolio)
            cells.append(
                f"{s['ret'] * 100:+6.1f}% {s['dd'] * 100:6.1f}% {s['worst_month'] * 100:6.1f}% {np.mean(changes):4.1f}"
            )
        print(f"{name:24s} | {cells[0]:34s} | {cells[1]}")


if __name__ == "__main__":
    main()
