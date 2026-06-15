# Install OmniVoice runtime in vendor/OmniVoice (network required)

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$omniRoot = Join-Path $ProjectRoot "vendor\OmniVoice"

if (-not (Test-Path $omniRoot)) {
    throw "找不到 vendor/OmniVoice，請先執行：git submodule update --init --recursive"
}

Write-Host "==> Setup OmniVoice in $omniRoot"
Set-Location $omniRoot
uv venv --python 3.12
uv pip install -e .

Write-Host "SETUP_OMNIVOICE_PASS"
