# One-time download of OmniVoice model weights (network required)

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ModelId = "k2-fsa/OmniVoice"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$omniRoot = Join-Path $ProjectRoot "vendor\OmniVoice"
if (-not (Test-Path $omniRoot)) {
    throw "找不到 vendor/OmniVoice，請先執行 git submodule update --init"
}

$python = Join-Path $omniRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "找不到 $python，請先執行 scripts/setup_omnivoice.ps1"
}

Write-Host "==> Download $ModelId"
& $python -c "from huggingface_hub import snapshot_download; snapshot_download('$ModelId'); print('FETCH_MODELS_PASS')"
