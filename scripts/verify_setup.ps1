# 營運者環境驗證入口（請在 repo 根目錄執行）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$marker = Join-Path $root "pyproject.toml"

if (-not (Test-Path $marker)) {
    Write-Error "請在 streamer_toolbox 根目錄執行此腳本（找不到 $marker）"
}

Push-Location $root
try {
    & uv run python scripts/verify_setup.py @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
