# Runs one strategy in paper-trading (dry-run) mode: live Binance prices, simulated money.
# No API keys needed. No real orders are ever sent in this mode.
#
#   scripts\paper-trade.ps1                                # TrendRider (dashboard port 8080)
#   scripts\paper-trade.ps1 -Strategy FlashCrashScalper    # port 8082
#   scripts\paper-trade.ps1 -Strategy CrashReversal        # port 8081
#
# Each strategy is its own bot: open one window per strategy. Its settings (capital,
# slots, dashboard port) live in user_data\config.<Strategy>.json.
param([string]$Strategy = "TrendRider")

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$configs = @("--config", "user_data/config.json")
if (Test-Path "user_data/config.private.json") {
    $configs += @("--config", "user_data/config.private.json")
}
if (Test-Path "user_data/config.$Strategy.json") {
    $configs += @("--config", "user_data/config.$Strategy.json")
}

# TrendRider keeps the original database name so earlier paper trades are not lost.
$db = if ($Strategy -eq "TrendRider") { "user_data/tradesv3.dryrun.sqlite" } else { "user_data/tradesv3.dryrun.$Strategy.sqlite" }

& .\.venv\Scripts\freqtrade.exe trade --userdir user_data @configs `
    --strategy $Strategy `
    --db-url "sqlite:///$db"
