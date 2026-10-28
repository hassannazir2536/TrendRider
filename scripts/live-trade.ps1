# Trades one strategy with REAL money. Paper trade first (scripts\paper-trade.ps1).
#
#   scripts\live-trade.ps1                                   # TrendRider on OKX
#   scripts\live-trade.ps1 -Strategy FlashCrashScalper
#   scripts\live-trade.ps1 -Exchange binance                 # TrendRider on Binance
#
# Each bot has its own capital: "available_capital" in user_data\config.<Strategy>.json
# (or config.<Strategy>.okx.json for OKX) is the most USDT that bot may use. If you run
# several bots on one exchange, the sum of their available_capital must not exceed your
# USDT balance there.
param(
    [string]$Strategy = "TrendRider",
    [ValidateSet("binance", "okx")][string]$Exchange = "okx"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. "$PSScriptRoot\common.ps1"

if ($Exchange -eq "binance") {
    $keyFile = "user_data/config.private.json"
    $setup = "scripts\set-binance-key.ps1"
    $fields = @("key", "secret")
} else {
    $keyFile = "user_data/config.private.$Exchange.json"
    $setup = "scripts\set-$Exchange-key.ps1"
    $fields = @("key", "secret", "password")
}
if (-not (Test-Path $keyFile)) {
    throw "Missing $keyFile. Run $setup first."
}
$keys = (Get-Content $keyFile -Raw | ConvertFrom-Json).exchange
foreach ($field in $fields) {
    $value = $keys.$field
    if (-not $value -or $value -like "YOUR_*") {
        throw "The $Exchange API $field is not set in $keyFile. Run $setup."
    }
}

if (-not (Test-Path "user_data/config.$Strategy.json")) {
    throw "Missing user_data/config.$Strategy.json. Create it with at least {""available_capital"": <USDT this strategy may use>}."
}
$capital = Get-Capital -Strategy $Strategy -Exchange $Exchange
if (-not $capital) {
    throw "available_capital is not set for $Strategy."
}

Write-Host ""
Write-Host "LIVE TRADING with real money." -ForegroundColor Red
Write-Host "Strategy: $Strategy | Exchange: $Exchange | Capital this bot may use: $capital USDT" -ForegroundColor Yellow
Write-Host "Losses are possible. Past results do not guarantee future profits." -ForegroundColor Yellow
$answer = Read-Host "Type LIVE to start"
if ($answer -cne "LIVE") {
    Write-Host "Cancelled."
    exit 1
}

$configs = Get-ConfigArgs -Strategy $Strategy -Exchange $Exchange -Secrets
$configs += @("--config", "user_data/config.live.json")

& .\.venv\Scripts\freqtrade.exe trade --userdir user_data @configs `
    --strategy $Strategy `
    --db-url (Get-DbUrl -Strategy $Strategy -Exchange $Exchange -Live)
