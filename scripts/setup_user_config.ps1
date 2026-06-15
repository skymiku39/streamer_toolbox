# 初始化外部設定目錄（方案 A）
# 從 .env 讀取 STREAMER_CONFIG_DIR、TWITCH_CHANNEL，複製範例檔（不覆寫既有檔）

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($value -match '^["''](.*)["'']$') {
                $value = $matches[1]
            }
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$channel = $env:TWITCH_CHANNEL
$args = @("run", "python", "-m", "streamer_config", "bootstrap")
if ($channel) {
    $args += @("--channel", $channel)
}

Write-Host "[setup_user_config] bootstrap external config directory..."
uv @args
if ($LASTEXITCODE -ne 0) {
    throw "setup_user_config failed with exit code $LASTEXITCODE"
}
Write-Host "[setup_user_config] done."
