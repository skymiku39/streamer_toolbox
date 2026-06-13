$pattern = 'streamer_toolbox|app\.(main|publishers|subscribers)|ingress_|sub_llm|sub_stream|stream_record|twitch_connector|streamlink.*skymiku39'
$exclude = 'pytest|verify_dedup|multiprocessing\.spawn|list_procs|stop_all'

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch $exclude }

$groups = @{}
foreach ($p in $procs) {
    $cl = $p.CommandLine
    $key = 'other'
    if ($cl -match '-m app\.main run (.+)"') {
        $key = 'app.main run: ' + $Matches[1].Substring(0, [Math]::Min(70, $Matches[1].Length))
    }
    elseif ($cl -match '-m\s+([\w\.]+)') {
        $key = $Matches[1]
    }
    elseif ($cl -match 'streamlink') {
        $key = 'streamlink (STT audio)'
    }
    if (-not $groups.ContainsKey($key)) {
        $groups[$key] = @()
    }
    $groups[$key] += $p.ProcessId
}

Write-Output '=== streamer_toolbox Python processes ==='
$total = 0
foreach ($k in ($groups.Keys | Sort-Object)) {
    $c = $groups[$k].Count
    $total += $c
    $pids = $groups[$k] -join ', '
    Write-Output ("{0,3}x  {1}  [PID: {2}]" -f $c, $k, $pids)
}
Write-Output "--- Total $total ---"

$keyModules = @(
    'ingress_ttv_read',
    'ingress_twitch_audio',
    'sub_llm',
    'twitch_connector',
    'stream_record',
    'sub_stream_record'
)
Write-Output ''
Write-Output '=== Key modules (should be 1 each) ==='
foreach ($mod in $keyModules) {
    $cnt = 0
    foreach ($k in $groups.Keys) {
        if ($k -match [regex]::Escape($mod)) { $cnt += $groups[$k].Count }
    }
    if ($cnt -gt 0) {
        $flag = if ($cnt -gt 1) { ' DUPLICATE!' } else { '' }
        Write-Output ("  {0}: {1}{2}" -f $mod, $cnt, $flag)
    }
}
