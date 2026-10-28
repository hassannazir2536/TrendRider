"""
Checks the Binance API key in user_data/config.private.json. Read-only: places no orders.

Prints the key's permissions and your free balances, and warns if withdrawals are
enabled or the key is not restricted to your IP address. Never prints the key itself.
"""

import json
import sys
from pathlib import Path

import ccxt


CONFIG = Path(__file__).resolve().parent.parent / "user_data" / "config.private.json"


def main() -> int:
    exchange_cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))["exchange"]
    exchange = ccxt.binance({"apiKey": exchange_cfg["key"], "secret": exchange_cfg["secret"]})

    try:
        restrictions = exchange.sapi_get_account_apirestrictions()
        balance = exchange.fetch_balance()
    except ccxt.AuthenticationError as e:
        print(f"Binance rejected the key: {e}")
        print("Check the API key and secret, and that this PC's IP address is allowed on the key.")
        return 1
    except ccxt.BaseError as e:
        print(f"Could not check the key: {e}")
        return 1

    trading = bool(restrictions.get("enableSpotAndMarginTrading"))
    withdrawals = bool(restrictions.get("enableWithdrawals"))
    ip_restricted = bool(restrictions.get("ipRestrict"))
    print("Key accepted by Binance.")
    print(f"  Spot trading enabled: {trading}")
    print(f"  Withdrawals enabled:  {withdrawals}")
    print(f"  IP restricted:        {ip_restricted}")
    for coin in ("USDT", "BTC", "ETH"):
        print(f"  Free {coin}: {balance.get('free', {}).get(coin) or 0}")

    ok = True
    if not trading:
        print("PROBLEM: enable 'Spot & Margin Trading' on this key, or the bot cannot place orders.")
        ok = False
    if withdrawals:
        print("WARNING: withdrawals are enabled. Turn them off - the bot never needs them.")
        ok = False
    if not ip_restricted:
        print("WARNING: the key is not restricted to your IP address. Add your IP for safety.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
