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

$path = Join-Path (Get-Location) "user_data\config.private.json"
if (-not (Test-Path $path)) {
    Copy-Item "user_data\config.private.example.json" $path
}
$cfg = Get-Content $path -Raw | ConvertFrom-Json

$cfg.exchange.key = (Read-Host "Binance API Key").Trim()
if ($PrivateKeyFile) {
    $secret = (Get-Content -LiteralPath $PrivateKeyFile -Raw).Trim() -replace "`r`n", "`n"
    if ($secret -notmatch "PRIVATE KEY") {
        throw "$PrivateKeyFile does not look like a private key file (expected '-----BEGIN PRIVATE KEY-----')."
    }
} else {
    $secure = Read-Host "Binance Secret Key" -AsSecureString
    $secret = [System.Net.NetworkCredential]::new("", $secure).Password.Trim()
}
$cfg.exchange.secret = $secret

function New-Token([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return [Convert]::ToBase64String($buffer) -replace "[+/=]", ""
}

# Replace the dashboard's placeholder secrets with random ones, once.
if ($cfg.api_server.password -like "CHANGE_ME*") {
    $cfg.api_server.jwt_secret_key = New-Token 48
    $cfg.api_server.ws_token = New-Token 24
    $cfg.api_server.password = New-Token 12
    Write-Host "Dashboard login (http://127.0.0.1:8080): $($cfg.api_server.username) / $($cfg.api_server.password)" -ForegroundColor Cyan
    Write-Host "Save this password somewhere safe. It is also in $path." -ForegroundColor Cyan
}

# Freqtrade cannot read files with a UTF-8 byte-order mark, so write without one.
$json = $cfg | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Saved to $path"
Write-Host ""

& .\.venv\Scripts\python.exe scripts\check_binance_key.py
