# Backtests a strategy on downloaded history, with a 0.1% fee per side (Binance and OKX
# regular rate). Uses the strategy's own settings from user_data\config.<Strategy>.json and
# sizes the simulated wallet to its available_capital, so results reflect the money the bot
# would really trade with (slices below the exchange minimum are skipped).
#
#   scripts\backtest.ps1                                            # TrendRider on Binance data, Mar 2024 to now
#   scripts\backtest.ps1 -Strategy FlashCrashScalper -Timerange 20260101-
#   scripts\backtest.ps1 -Capital 1000                              # pretend you had 1000 USDT
#   scripts\backtest.ps1 -Exchange okx                              # OKX data (run update-data.ps1 -Exchange okx first)
param(
    [string]$Strategy = "TrendRider",
    [string]$Timerange = "20240301-",
    [double]$Capital = 0,
    [ValidateSet("binance", "okx")][string]$Exchange = "binance"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. "$PSScriptRoot\common.ps1"

$configs = Get-ConfigArgs -Strategy $Strategy -Exchange $Exchange
if ($Capital -le 0) {
    $Capital = Get-Capital -Strategy $Strategy -Exchange $Exchange
}

$extra = @()
if ($Capital -gt 0) {
    $override = Join-Path $env:TEMP "ft-backtest-capital.json"
    [System.IO.File]::WriteAllText($override, "{""available_capital"": $Capital}", (New-Object System.Text.UTF8Encoding $false))
    $extra = @("--config", $override, "--dry-run-wallet", $Capital)
}

& .\.venv\Scripts\freqtrade.exe backtesting --userdir user_data @configs @extra `
    --strategy $Strategy `
    --timerange $Timerange `
    --fee 0.001 `
    --enable-protections
