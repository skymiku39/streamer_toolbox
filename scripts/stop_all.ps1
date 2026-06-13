# Stop all streamer_toolbox Python processes (excluding pytest).
$pattern = 'streamer_toolbox|app\.(main|publishers|subscribers)|ingress_|sub_llm|sub_stream|stream_record|twitch_connector|streamlink.*skymiku39'
$exclude = 'pytest|verify_dedup|multiprocessing\.spawn|list_procs|stop_all'

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch $exclude }

if (-not $procs) {
    Write-Output 'No streamer_toolbox processes found.'
    exit 0
}

Write-Output "Stopping $($procs.Count) processes..."
foreach ($p in $procs) {
    $short = 'python'
    if ($p.CommandLine -match '-m\s+([\w\.]+)') {
        $short = $Matches[1]
    }
    Write-Output "  Stop PID $($p.ProcessId)  $short"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
$remaining = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch $exclude })
Write-Output "Remaining: $($remaining.Count)"
$lockDir = Join-Path (Get-Location) 'data\process-locks'
if (Test-Path $lockDir) {
    Remove-Item (Join-Path $lockDir '*.pid') -Force -ErrorAction SilentlyContinue
}
