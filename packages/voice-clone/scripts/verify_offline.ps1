# Verify voice_clone offline/unit tests

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$env:VOICE_CLONE_OFFLINE = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

Write-Host "==> uv sync"
uv sync --extra dev

Write-Host "==> pytest"
uv run pytest tests -q

Write-Host ""
Write-Host "VERIFY_OFFLINE_PASS"
