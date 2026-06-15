# Check GPU and recommend training profile

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

Write-Host "==> GPU check"
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $nvidia) {
    Write-Host "nvidia-smi not found. NVIDIA GPU required for training."
    exit 1
}

$raw = nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version,compute_cap --format=csv,noheader 2>$null
if (-not $raw) {
    Write-Host "nvidia-smi query failed."
    exit 1
}

Write-Host $raw
$quote = [char]34
$parts = $raw.Split(",") | ForEach-Object { $_.Trim().Trim($quote) }
$name = $parts[0]
$totalMiB = [int]($parts[1] -replace "[^0-9]", "")
$freeMiB = [int]($parts[2] -replace "[^0-9]", "")
$driver = $parts[3]
$compute = $parts[4]

Write-Host ""
Write-Host "GPU          : $name"
Write-Host "VRAM total   : $totalMiB MiB (~$([math]::Round($totalMiB / 1024, 1)) GB)"
Write-Host "VRAM free    : $freeMiB MiB"
Write-Host "Driver       : $driver"
Write-Host "Compute Cap  : $compute"

$profile = "streamer"
$batchNote = "batch=2"
if ($totalMiB -ge 12000) {
    $profile = "streamer_hq"
    $batchNote = "batch=2 + DPO"
} elseif ($totalMiB -lt 7000) {
    $profile = "streamer"
    $batchNote = "batch=1 (low VRAM)"
}

Write-Host ""
Write-Host "Recommended profile : $profile ($batchNote)"
Write-Host "Suggested .env      : VOICE_CLONE_GPU=0"
Write-Host ""
Write-Host "CHECK_GPU_PASS"
