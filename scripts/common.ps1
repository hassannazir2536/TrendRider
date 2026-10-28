# Shared helpers for the scripts in this folder. Dot-source it:  . "$PSScriptRoot\common.ps1"
# Every function expects the current directory to be the project root.

# The --config arguments for one bot, in merge order (later files override earlier ones):
#   config.json                        shared settings, Binance by default
#   config.private.json                dashboard/Telegram secrets and the Binance key    (-Secrets)
#   config.<exchange>.json             switches exchange and clears the Binance key       (not Binance)
#   config.private.<exchange>.json     that exchange's API key                            (-Secrets, not Binance)
#   config.<Strategy>.json             the bot's capital, slots, coins and dashboard port
#   config.<Strategy>.<exchange>.json  per-exchange overrides of the file above           (not Binance)
# Files that do not exist are skipped.
function Get-ConfigArgs([string]$Strategy, [string]$Exchange, [switch]$Secrets) {
    $files = @("user_data/config.json")
    if ($Secrets) { $files += "user_data/config.private.json" }
    if ($Exchange -ne "binance") {
        $files += "user_data/config.$Exchange.json"
        if ($Secrets) { $files += "user_data/config.private.$Exchange.json" }
    }
    $files += "user_data/config.$Strategy.json"
    if ($Exchange -ne "binance") { $files += "user_data/config.$Strategy.$Exchange.json" }

    $result = @()
    foreach ($file in $files) {
        if (Test-Path $file) { $result += @("--config", $file) }
    }
    return $result
}

# Each strategy and exchange keeps its own trade database, separately for paper and live.
function Get-DbUrl([string]$Strategy, [string]$Exchange, [switch]$Live) {
    $mode = if ($Live) { "live" } else { "dryrun" }
    if (-not $Live -and $Exchange -eq "binance" -and $Strategy -eq "TrendRider") {
        # The original name, so earlier paper trades are not lost.
        return "sqlite:///user_data/tradesv3.dryrun.sqlite"
    }
    $suffix = if ($Exchange -eq "binance") { "" } else { ".$Exchange" }
    return "sqlite:///user_data/tradesv3.$mode.$Strategy$suffix.sqlite"
}

# available_capital for a bot: the per-exchange file wins over the strategy file.
function Get-Capital([string]$Strategy, [string]$Exchange) {
    $capital = $null
    foreach ($file in @("user_data/config.$Strategy.json", "user_data/config.$Strategy.$Exchange.json")) {
        if (Test-Path $file) {
            $value = (Get-Content $file -Raw | ConvertFrom-Json).available_capital
            if ($value) { $capital = $value }
        }
    }
    return $capital
}

# Freqtrade cannot read files with a UTF-8 byte-order mark, so write without one.
function Save-Json($Object, [string]$Path) {
    $json = $Object | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding $false))
}

# user_data\config.private.json holds the dashboard login shared by all bots.
function Read-PrivateConfig {
    $path = "user_data\config.private.json"
    if (-not (Test-Path $path)) {
        Copy-Item "user_data\config.private.example.json" $path
    }
    return Get-Content $path -Raw | ConvertFrom-Json
}

function New-Token([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return [Convert]::ToBase64String($buffer) -replace "[+/=]", ""
}

# Replaces the dashboard's placeholder secrets with random ones, once. Returns $true if it did.
function Set-DashboardSecrets($Config) {
    if ($Config.api_server.password -notlike "CHANGE_ME*") { return $false }
    $Config.api_server.jwt_secret_key = New-Token 48
    $Config.api_server.ws_token = New-Token 24
    $Config.api_server.password = New-Token 12
    Write-Host "Dashboard login (http://127.0.0.1:8080 and the other bot ports): $($Config.api_server.username) / $($Config.api_server.password)" -ForegroundColor Cyan
    Write-Host "Save this password somewhere safe. It is also in user_data\config.private.json." -ForegroundColor Cyan
    return $true
}

function Read-SecretText([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    return [System.Net.NetworkCredential]::new("", $secure).Password.Trim()
}
