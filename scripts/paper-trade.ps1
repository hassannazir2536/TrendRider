# Runs one strategy in paper-trading (dry-run) mode: live exchange prices, simulated money.
# No API keys needed. No real orders are ever sent in this mode.
#
#   scripts\paper-trade.ps1                                  # TrendRider on OKX (dashboard port 8090)
#   scripts\paper-trade.ps1 -Strategy CrashReversal          # port 8091
#   scripts\paper-trade.ps1 -Strategy FlashCrashScalper      # port 8092
#   scripts\paper-trade.ps1 -Exchange binance                # TrendRider on Binance (port 8080)
#
# Each strategy on each exchange is its own bot: open one window per bot. Its settings
# (capital, slots, dashboard port) live in user_data\config.<Strategy>.json, with OKX
# overrides in user_data\config.<Strategy>.okx.json.
param(
    [string]$Strategy = "TrendRider",
    [ValidateSet("binance", "okx")][string]$Exchange = "okx"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. "$PSScriptRoot\common.ps1"

$configs = Get-ConfigArgs -Strategy $Strategy -Exchange $Exchange -Secrets

& .\.venv\Scripts\freqtrade.exe trade --userdir user_data @configs `
    --strategy $Strategy `
    --db-url (Get-DbUrl -Strategy $Strategy -Exchange $Exchange)
