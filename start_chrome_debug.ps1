param(
    [string]$Url = "https://www.douyin.com/chat",
    [int]$Port = 9222
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$profileDir = Join-Path $projectDir ".chrome-profile"

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    throw "Google Chrome was not found. Install Chrome, then run this script again."
}

New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$chromeArgs = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$profileDir",
    "--new-window",
    $Url
)

Start-Process -FilePath $chrome -ArgumentList $chromeArgs
Write-Host "Chrome started with remote debugging at http://127.0.0.1:$Port"
Write-Host "Opened: $Url"
Write-Host "Log in, open the target chat, then run extract.py with --platform."
