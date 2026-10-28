# Trades one strategy with REAL money on Binance. Paper trade first (scripts\paper-trade.ps1).
#
#   scripts\live-trade.ps1                                 # TrendRider
#   scripts\live-trade.ps1 -Strategy FlashCrashScalper
#
# Each strategy is its own bot with its own capital: "available_capital" in
# user_data\config.<Strategy>.json is the most USDT that bot may use. If you run several
# bots at once, the sum of their available_capital must not exceed your USDT balance.
param([string]$Strategy = "TrendRider")

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$private = "user_data/config.private.json"
if (-not (Test-Path $private)) {
    throw "Missing $private. Run scripts\set-binance-key.ps1 first."
}
$exchange = (Get-Content $private -Raw | ConvertFrom-Json).exchange
if (-not $exchange.key -or $exchange.key -like "YOUR_*" -or -not $exchange.secret -or $exchange.secret -like "YOUR_*") {
    throw "Binance API key/secret are not set in $private. Run scripts\set-binance-key.ps1."
}

$strategyConfig = "user_data/config.$Strategy.json"
if (-not (Test-Path $strategyConfig)) {
    throw "Missing $strategyConfig. Create it with at least {""available_capital"": <USDT this strategy may use>}."
}
$capital = (Get-Content $strategyConfig -Raw | ConvertFrom-Json).available_capital
if (-not $capital) {
    throw "available_capital is not set in $strategyConfig."
}

Write-Host ""
Write-Host "LIVE TRADING with real money." -ForegroundColor Red
Write-Host "Strategy: $Strategy | Capital this bot may use: $capital USDT" -ForegroundColor Yellow
Write-Host "Losses are possible. Past results do not guarantee future profits." -ForegroundColor Yellow
$answer = Read-Host "Type LIVE to start"
if ($answer -cne "LIVE") {
    Write-Host "Cancelled."
    exit 1
}

& .\.venv\Scripts\freqtrade.exe trade --userdir user_data `
    --config user_data/config.json `
    --config $private `
    --config $strategyConfig `
    --config user_data/config.live.json `
    --strategy $Strategy `
    --db-url "sqlite:///user_data/tradesv3.live.$Strategy.sqlite"
