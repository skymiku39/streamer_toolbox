# 啟動 OmniVoice Gradio 網頁版

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Model = "k2-fsa/OmniVoice",
    [string]$Device = "cuda:0",
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$omniRoot = Join-Path $ProjectRoot "vendor\OmniVoice"
$demo = Join-Path $omniRoot ".venv\Scripts\omnivoice-demo.exe"

if (-not (Test-Path $demo)) {
    throw "找不到 $demo，請先執行 scripts/setup_omnivoice.ps1"
}

Write-Host "==> OmniVoice Web UI: http://localhost:$Port"
Set-Location $omniRoot
& $demo --model $Model --device $Device --ip 0.0.0.0 --port $Port
