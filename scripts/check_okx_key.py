"""
Checks the OKX API key in user_data/config.private.okx.json. Read-only: places no orders.

Prints the key's permissions, the account mode and your balances, and warns if withdrawals
are enabled, the key is not bound to an IP address, or your USDT is still in the Funding
account (the bot only sees the Trading account). Never prints the key itself.
"""

import json
import sys
import time
from pathlib import Path

import ccxt


CONFIG = Path(__file__).resolve().parent.parent / "user_data" / "config.private.okx.json"
ACCOUNT_MODES = {"1": "Spot mode", "2": "Futures mode", "3": "Multi-currency margin", "4": "Portfolio margin"}


def main() -> int:
    exchange_cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))["exchange"]
    exchange = getattr(ccxt, exchange_cfg.get("name", "okx"))(
        {
            "apiKey": exchange_cfg["key"],
            "secret": exchange_cfg["secret"],
            "password": exchange_cfg["password"],
            "timeout": 30000,
        }
    )

    def call(fn, *args):
        # OKX's edge network drops the odd request; retry those, never authentication errors.
        for attempt in range(3):
            try:
                return fn(*args)
            except ccxt.NetworkError:
                if attempt == 2:
                    raise
                time.sleep(3)

    try:
        account = call(exchange.private_get_account_config)["data"][0]
        trading = call(exchange.fetch_balance)
        funding = call(exchange.fetch_balance, {"type": "funding"})
    except ccxt.NetworkError as e:
        print(f"Could not reach OKX: {e}")
        print("Check your internet connection and run the check again: .venv\\Scripts\\python.exe scripts\\check_okx_key.py")
        return 1
    except ccxt.BaseError as e:
        # OKX reports bad keys with several codes (e.g. 50119 "API key doesn't exist"), not all
        # of which ccxt maps to AuthenticationError.
        print(f"OKX rejected the key: {e}")
        print("Check the API key, secret key and passphrase, and that this PC's IP address is allowed on the key.")
        print("Registered on my.okx.com (OKX Europe)? Run scripts\\set-okx-key.ps1 -Eea instead.")
        return 1

    permissions = {p.strip() for p in account.get("perm", "").split(",") if p.strip()}
    ips = [ip for ip in account.get("ip", "").split(",") if ip.strip()]
    mode_id = str(account.get("acctLv", ""))
    mode = ACCOUNT_MODES.get(mode_id, f"unknown ({mode_id})")
    trading_usdt = trading.get("free", {}).get("USDT") or 0
    funding_usdt = funding.get("free", {}).get("USDT") or 0

    print("Key accepted by OKX.")
    print(f"  Permissions:          {', '.join(sorted(permissions)) or 'none'}")
    print(f"  Bound IP addresses:   {', '.join(ips) or 'none'}")
    print(f"  Account mode:         {mode}")
    print(f"  Trading account USDT: {trading_usdt}")
    for coin in ("BTC", "ETH"):
        print(f"  Trading account {coin}:  {trading.get('free', {}).get(coin) or 0}")
    print(f"  Funding account USDT: {funding_usdt}")

    ok = True
    if "trade" not in permissions:
        print("PROBLEM: enable the 'Trade' permission on this key, or the bot cannot place orders.")
        ok = False
    if "withdraw" in permissions:
        print("WARNING: withdrawals are enabled. Create a new key without them - the bot never needs them.")
        ok = False
    if not ips:
        print("WARNING: the key is not bound to an IP address. OKX deletes such keys after 14 days")
        print("         without use, and an IP binding protects you if the key ever leaks.")
    if mode_id != "1":
        print(f"NOTE: the account is in {mode}. Spot mode is the simplest setting for a spot-only bot")
        print("      (OKX app: Assets > Trading account > Account mode).")
    if funding_usdt and trading_usdt < funding_usdt:
        print("NOTE: most of your USDT is in the Funding account. Transfer it to the Trading account,")
        print("      because the bot can only use the Trading account (OKX app: Assets > Transfer).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
