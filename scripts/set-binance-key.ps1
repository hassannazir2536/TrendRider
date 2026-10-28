# Saves your Binance API credentials to user_data\config.private.json (git-ignored),
# then checks the key with Binance. Run it yourself - never paste keys into chat.
#
# "System generated" key (API Key + Secret Key):
#     scripts\set-binance-key.ps1
# "Self-generated" Ed25519/RSA key (API Key only, plus your private key file):
#     scripts\set-binance-key.ps1 -PrivateKeyFile "C:\path\to\private_key.pem"
param([string]$PrivateKeyFile)

$ErrorActionPreference = "Stop"
if ($PrivateKeyFile) {
    if (-not (Test-Path -LiteralPath $PrivateKeyFile -PathType Leaf)) {
        throw "Private key file not found: $PrivateKeyFile  (check the folder and the exact file name, including its extension)"
    }
    # Resolve before changing directory, so relative paths work too.
    $PrivateKeyFile = (Resolve-Path -LiteralPath $PrivateKeyFile).Path
}
Set-Location (Join-Path $PSScriptRoot "..")
. "$PSScriptRoot\common.ps1"

$cfg = Read-PrivateConfig
$key = (Read-Host "Binance API Key").Trim()
if ($PrivateKeyFile) {
    $secret = (Get-Content -LiteralPath $PrivateKeyFile -Raw).Trim() -replace "`r`n", "`n"
    if ($secret -notmatch "PRIVATE KEY") {
        throw "$PrivateKeyFile does not look like a private key file (expected '-----BEGIN PRIVATE KEY-----')."
    }
} else {
    $secret = Read-SecretText "Binance Secret Key"
}
# The exchange block may be missing if only an OKX key was set up so far.
$cfg | Add-Member -NotePropertyName exchange -NotePropertyValue ([pscustomobject]@{ key = $key; secret = $secret }) -Force

$null = Set-DashboardSecrets $cfg
$path = Join-Path (Get-Location) "user_data\config.private.json"
Save-Json $cfg $path
Write-Host "Saved to $path"
Write-Host ""

& .\.venv\Scripts\python.exe scripts\check_binance_key.py
