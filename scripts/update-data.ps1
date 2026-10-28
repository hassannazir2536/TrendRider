# Downloads the latest candles used by backtests and research scripts.
# Pairs come from pair_whitelist in user_data\config.json unless -Pairs is given.
#
#   scripts\update-data.ps1                                         # OKX, all 20 coins
#   scripts\update-data.ps1 -Pairs "BTC/USDT,ETH/USDT" -SkipScalping  # OKX, two coins, only 1h/4h/1d
#   scripts\update-data.ps1 -Exchange binance                       # Binance (the research scripts read this)
#
# OKX sends only 100 historic candles per request, so a first OKX download of 5-minute
# candles takes a long time. Later runs only fetch what is new.
param(
    [ValidateSet("binance", "okx")][string]$Exchange = "okx",
    [string]$Pairs = "",
    [switch]$SkipScalping
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$pairList = if ($Pairs) {
    $Pairs -split "[,\s]+" | Where-Object { $_ }
} else {
    (Get-Content "user_data\config.json" -Raw | ConvertFrom-Json).exchange.pair_whitelist
}

# The exchange config carries connection settings (for OKX: spot markets only, longer timeout).
$configs = @("--config", "user_data/config.json")
if ($Exchange -ne "binance") { $configs += @("--config", "user_data/config.$Exchange.json") }

$jobs = @(@{ Timeframes = @("1h", "4h", "1d"); Since = "20230701" })
if (-not $SkipScalping) { $jobs += @{ Timeframes = @("5m", "15m"); Since = "20240101" } }

foreach ($job in $jobs) {
    & .\.venv\Scripts\freqtrade.exe download-data --userdir user_data @configs `
        --trading-mode spot `
        --pairs $pairList `
        --timeframes $job.Timeframes `
        --timerange "$($job.Since)-"
    if ($LASTEXITCODE -ne 0) {
        throw "Download of $($job.Timeframes -join '/') candles from $Exchange failed (exit code $LASTEXITCODE). Run the script again; it resumes where it stopped."
    }
}
