# Analyzer & Trader

Automated Binance **spot** trading bots built on [Freqtrade](https://www.freqtrade.io) 2026.9.
The main bot trades BTC and ETH by default and can be widened to 20 large coins. No leverage, no shorting.

> **Risk warning:** No strategy is guaranteed to make money. Backtests describe the past,
> not the future. Only trade money you can afford to lose.

## The three strategies

| Strategy | What it does | Status |
|---|---|---|
| **TrendRider** | Holds a coin while its daily close is above its 50-day average, otherwise sits in USDT. Checks hourly. | **Main strategy.** Live-ready after paper trading. |
| **CrashReversal** | Buys a coin that fell >8% in 24h, sells 24h later. | **Experimental.** Paper trading only. |
| **FlashCrashScalper** | Buys a coin that fell >5% in 2h, sells 6h later (5-minute candles). | **Experimental.** Paper trading only. |

Each strategy runs as its own bot with its own capital, dashboard port and settings file
(`user_data/config.<Strategy>.json`). All three keep a stop-loss order on Binance so positions
stay protected if your PC goes offline.

**Coins:** BTC, ETH, XRP, SOL, DOGE, TRX, ADA, LINK, SUI, AVAX, BCH, LTC, NEAR, DOT, UNI, AAVE, APT, ARB, INJ, ATOM
(all against USDT; the list is `pair_whitelist` in `user_data/config.json`).

## Backtest results

All results include Binance's 0.1% fee per side. "Unseen" means Jan–Oct 2026 data that was not
looked at while designing the strategies.

### TrendRider

| Coins | Mar 2024 – Dec 2025 | Jan – Oct 2026 (unseen) | Worst drawdown | Buy & hold of same coins |
|---|---|---|---|---|
| **BTC + ETH, 50/50 (default, 100 USDT)** | **+58%** | **+20%** | −32% / −21% | +15% / −15% |
| Top 10, equal slices | +59% | −2% | −29% / −28% | +16% / −20% |
| All 20, equal slices | +18% | +4% | −34% / −25% | −13% / −5% |
| All 20, tiered slices (needs ~300 USDT) | +31% | +9% | −28% / −21% | −13% / −5% |

Tiered slices: BTC 25%, ETH 15%, each other coin 3.3% (set with `pair_weights`, see "Capital" below).

Honest reading: in this period altcoins were weak, so adding them **lowered** returns compared with
BTC+ETH alone, even though the rule beat buy-and-hold on 15–17 of the 20 coins. The 20-coin version
is a bet that the next up-cycle is broader than the last one. Only ~17–28% of trades win; a few big
winners pay for many small losses, and 20–30% drawdowns are normal.

**Safety techniques tested and rejected** ([research/safety_study.py](research/safety_study.py)):
2-day entry confirmation, a faster 20-day exit, 15% and 20% trailing stops, volatility-scaled position
sizes, a BTC 200-day regime filter, a three-average blend, and combinations of these. None improved
both the design period and the unseen 2026 data, on either BTC+ETH or all 20 coins. Most traded
return for a slightly smaller drawdown, which is achieved more simply by allocating less capital.
The plain 50-day rule stays.

### CrashReversal and FlashCrashScalper (20 slots, −25% stop)

| Strategy | Mar 2024 – Dec 2025 | Jan – Oct 2026 (unseen) | Profit factor | Worst drawdown |
|---|---|---|---|---|
| CrashReversal (1h) | +5% | +16% | 1.02 / 1.65 | −29% / −11% |
| FlashCrashScalper (5m) | +9% | +18% | 1.05 / 1.83 | −24% / −9% |

Why they are "experimental":
- The 2024–25 edge is thin (profit factor barely above 1). 2026 looks great because it was a bear
  market full of crashes, which is exactly when these strategies shine.
- They only work as **many small bets**: with 4 slots instead of 20 they lost 65% and 17% in-sample,
  because the bot could only take the first few signals of a market-wide crash.
- Tight stops (−10%/−12%) destroyed them: the stop was hit during the crash, then the coin rebounded.
  The −25% stop is a disaster brake, not a trading tool.
- On 10 Oct 2025 ATOM wicked from $3.7 to $0.001 on Binance within minutes. Buying crashes means
  being exposed to events like that. Freqtrade uses stop-*limit* orders on Binance, which cannot
  fill at $0.001, but real fills in a crash are always worse than a backtest assumes.

### Why there is no classic scalping bot

[research/signal_study.py](research/signal_study.py) tested 22 common entry signals (RSI, Bollinger
Bands, z-score, breakouts, EMA crosses, momentum, crashes) on 5m, 15m and 1h candles across all 20
coins, split into design and unseen periods. **Every classic scalping signal lost about the 0.2%
round-trip fee per trade on every timeframe.** The only setups with a real edge were crash rebounds,
which became the two experimental strategies. [research/trend_study.py](research/trend_study.py)
compared daily and 4h trend rules and led to TrendRider.

Earlier 5m/15m strategies that lost 65–73% are kept in
[research/rejected_strategies/](research/rejected_strategies/), outside the folder the bot loads from.

## Quick start: paper trading (do this first)

Paper trading uses live Binance prices with simulated money and sends no real orders. Open one
Command Prompt window per strategy you want to run and leave them open:

```cmd
cd /d "C:\path\to\TrendRider"
powershell -ExecutionPolicy Bypass -File scripts\paper-trade.ps1
powershell -ExecutionPolicy Bypass -File scripts\paper-trade.ps1 -Strategy CrashReversal
powershell -ExecutionPolicy Bypass -File scripts\paper-trade.ps1 -Strategy FlashCrashScalper
```

After changing any config file, stop the bot with `Ctrl+C` and start it again so it picks up the change.

Dashboards (login is the `api_server` username/password in `config.private.json`):
TrendRider http://127.0.0.1:8080, CrashReversal http://127.0.0.1:8081, FlashCrashScalper http://127.0.0.1:8082.

Paper results are kept in `user_data\tradesv3.dryrun*.sqlite`. Run for **at least 2–4 weeks**
(the crash strategies need months, since they only trade in crashes) and compare with the backtests.

> The bots only trade while your PC is awake and online. Set Windows sleep to "Never" while they
> run, or move them to a cloud server later.

## Capital: how much each bot needs

`available_capital` in each `user_data/config.<Strategy>.json` is the most USDT that bot may use.
It applies in paper trading too, so paper results match what live would do. Binance rejects orders
below ~5–10 USDT, so slices smaller than that are skipped automatically.

| Bot | Default capital | Minimum that makes sense | Why |
|---|---|---|---|
| TrendRider (BTC + ETH, default) | 100 | ~20 USDT | each half must be ≥ ~7 USDT |
| TrendRider (20 coins, tiered) | — | ~300 USDT | 3.3% alt slices must be ≥ 10 USDT |
| CrashReversal | 200 | ~200 USDT | 20 slots × 5% must be ≥ 10 USDT |
| FlashCrashScalper | 200 | ~200 USDT | same |

If you run several bots at once, the sum of their `available_capital` must not exceed your USDT balance.
With 100 USDT, run **TrendRider only**: the crash bots cannot trade with less than ~200 USDT.

If a slice is too small, TrendRider pauses that coin until the next hour and logs once:
`NEAR/USDT: buy signal skipped, slice 3.33 USDT < Binance minimum 6.18 USDT`.

**300 USDT or more?** Switch TrendRider to all 20 coins. Replace `user_data\config.TrendRider.json` with:

```json
{
    "bot_name": "trend-rider",
    "max_open_trades": 20,
    "available_capital": 300,
    "pair_weights": { "BTC/USDT": 0.25, "ETH/USDT": 0.15 },
    "api_server": { "listen_port": 8080 }
}
```

## Going live with real money

1. Create a Binance API key (Profile → API Management → Create API). Binance offers two types:
   - **System generated (HMAC):** Binance shows an API Key **and** a Secret Key (shown once).
   - **Self-generated (Ed25519, recommended by Binance):** create a key pair with Binance's
     [Asymmetric Key Generator](https://github.com/binance/asymmetric-key-generator), upload the
     **public** key; Binance gives you an API Key and your **private key file** acts as the secret.

   Either way: enable **Spot & Margin Trading**, **do NOT enable withdrawals**, restrict access to **your IP address**.
2. Save the key by running the helper **yourself**. Never paste keys into a chat or share them:

   ```cmd
   powershell -ExecutionPolicy Bypass -File scripts\set-binance-key.ps1
   powershell -ExecutionPolicy Bypass -File scripts\set-binance-key.ps1 -PrivateKeyFile "C:\path\to\private_key.pem"
   ```

   It writes `user_data\config.private.json`, sets a random dashboard password, and asks Binance
   (read-only) to confirm the key works, warning if withdrawals are on or the IP restriction is missing.
3. Deposit USDT and set `available_capital` in the strategy's config file (see Capital above).
4. Start a live bot and type `LIVE` when prompted:

   ```cmd
   powershell -ExecutionPolicy Bypass -File scripts\live-trade.ps1
   powershell -ExecutionPolicy Bypass -File scripts\live-trade.ps1 -Strategy CrashReversal
   ```

Live trades are kept in `user_data\tradesv3.live.<Strategy>.sqlite`, separate from paper trading.

## Backtesting and research

```cmd
powershell -ExecutionPolicy Bypass -File scripts\update-data.ps1                    :: fetch latest candles for all 20 coins
powershell -ExecutionPolicy Bypass -File scripts\backtest.ps1                       :: TrendRider, Mar 2024 to now, at its configured capital
powershell -ExecutionPolicy Bypass -File scripts\backtest.ps1 -Capital 1000         :: same, pretending you had 1000 USDT
powershell -ExecutionPolicy Bypass -File scripts\backtest.ps1 -Strategy FlashCrashScalper -Timerange 20260101-
.venv\Scripts\python.exe research\signal_study.py --timeframe 15m --horizons 4 16 48
.venv\Scripts\python.exe research\trend_study.py
```

Research scripts use the coins in `config.json` by default; add `--pairs BTC/USDT ETH/USDT` to narrow
them or `--per-pair` to see every coin. Before trusting a change, check it on **all coins** and on
data it was **not tuned on**. Small tweaks that only improve one backtest are usually overfitting.

## Project layout

| Path | What it is |
|---|---|
| `user_data/strategies/TrendRider.py` | Main strategy |
| `user_data/strategies/CrashReversal.py`, `FlashCrashScalper.py` | Experimental crash-rebound strategies |
| `user_data/config.json` | Shared settings: coin list, pricing, paper mode by default |
| `user_data/config.<Strategy>.json` | Per-bot settings: capital, slots, slice weights, dashboard port |
| `user_data/config.live.json` | Turns real orders on (used only by `live-trade.ps1`) |
| `user_data/config.private.example.json` | Template for API keys, dashboard and Telegram secrets |
| `scripts/` | Paper trade, live trade, backtest, data update, key setup and check |
| `research/` | Signal and trend studies, rejected strategies |
| `.venv/` | Python 3.12 environment with Freqtrade |

## Moving to a cloud server later

Any small Linux VPS (1 vCPU, 1–2 GB RAM) is enough; Freqtrade's official Docker image is the easiest
route. Copy `user_data/` (without `data/` and the `.sqlite` files) and run the same strategy and
config files. A server has a fixed IP, which also makes Binance's IP restriction painless.
