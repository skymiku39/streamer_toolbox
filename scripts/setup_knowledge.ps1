# 將 config/knowledge 範本複製到 data/knowledge（若尚不存在）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "config\knowledge"
$dst = Join-Path $root "data\knowledge"

if (-not (Test-Path $src)) {
    Write-Error "找不到 $src"
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null

Get-ChildItem -Path $src -Filter "*.md" | Where-Object { $_.Name -ne "README.md" } | ForEach-Object {
    $target = Join-Path $dst $_.Name
    if (-not (Test-Path $target)) {
        Copy-Item $_.FullName $target
        Write-Host "已建立 $target"
    } else {
        Write-Host "已存在，略過 $target"
    }
}

Write-Host "知識庫目錄：$dst"
