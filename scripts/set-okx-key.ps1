# Saves your OKX API credentials to user_data\config.private.okx.json (git-ignored),
# then checks the key with OKX. Run it yourself - never paste keys into chat.
#
#   scripts\set-okx-key.ps1          # account on www.okx.com or the global OKX app
#   scripts\set-okx-key.ps1 -Eea     # account registered on my.okx.com (OKX Europe)
#
# OKX shows three values when you create a key: API Key, Secret Key, and the Passphrase
# you chose yourself. You need all three.
param([switch]$Eea)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
. "$PSScriptRoot\common.ps1"

$okx = [ordered]@{
    exchange = [ordered]@{
        name     = if ($Eea) { "myokx" } else { "okx" }
        key      = (Read-Host "OKX API Key").Trim()
        secret   = Read-SecretText "OKX Secret Key"
        password = Read-SecretText "OKX Passphrase (the one you chose when creating the key)"
    }
}
foreach ($field in "key", "secret", "password") {
    if (-not $okx.exchange[$field]) {
        throw "The OKX $field was empty. Nothing was saved."
    }
}
$okxPath = Join-Path (Get-Location) "user_data\config.private.okx.json"
Save-Json $okx $okxPath
Write-Host "Saved to $okxPath"

# The dashboard login is shared by all bots and lives in config.private.json.
$private = Read-PrivateConfig
$changed = Set-DashboardSecrets $private
if ($private.exchange -and $private.exchange.key -like "YOUR_*") {
    # No Binance key set up yet: drop the placeholder so Binance bots do not try to use it.
    $private.PSObject.Properties.Remove("exchange")
    $changed = $true
}
if ($changed) {
    Save-Json $private (Join-Path (Get-Location) "user_data\config.private.json")
}
Write-Host ""

& .\.venv\Scripts\python.exe scripts\check_okx_key.py
