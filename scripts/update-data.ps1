# Downloads the latest Binance candles used by backtests and research scripts.
# Pairs come from pair_whitelist in user_data\config.json.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$pairs = (Get-Content "user_data\config.json" -Raw | ConvertFrom-Json).exchange.pair_whitelist

& .\.venv\Scripts\freqtrade.exe download-data --userdir user_data `
    --exchange binance --trading-mode spot `
    --pairs $pairs `
    --timeframes 1h 4h 1d `
    --timerange 20230701-

& .\.venv\Scripts\freqtrade.exe download-data --userdir user_data `
    --exchange binance --trading-mode spot `
    --pairs $pairs `
    --timeframes 5m 15m `
    --timerange 20240101-
