# Backtests a strategy on downloaded history, with Binance's 0.1% fee per side.
# Uses the strategy's own settings from user_data\config.<Strategy>.json when present,
# and sizes the simulated wallet to that file's available_capital so results reflect the
# money the bot would really trade with (small slices below Binance's 5 USDT minimum are skipped).
#
#   scripts\backtest.ps1                                            # TrendRider, Mar 2024 to now
#   scripts\backtest.ps1 -Strategy FlashCrashScalper -Timerange 20260101-
#   scripts\backtest.ps1 -Capital 1000                              # pretend you had 1000 USDT
param(
    [string]$Strategy = "TrendRider",
    [string]$Timerange = "20240301-",
    [double]$Capital = 0
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$configs = @("--config", "user_data/config.json")
$strategyConfig = "user_data/config.$Strategy.json"
if (Test-Path $strategyConfig) {
    $configs += @("--config", $strategyConfig)
    if ($Capital -le 0) {
        $Capital = (Get-Content $strategyConfig -Raw | ConvertFrom-Json).available_capital
    }
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
