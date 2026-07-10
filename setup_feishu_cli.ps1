param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if (-not $SkipInstall) {
    npx @larksuite/cli@latest install
}

if (-not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
    throw "lark-cli was not found in PATH. Restart PowerShell or check npm global bin path."
}

Write-Host "lark-cli version:"
lark-cli --version

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Initialize app credentials:"
Write-Host "   lark-cli config init"
Write-Host "2. Log in and grant recommended permissions:"
Write-Host "   lark-cli auth login --recommend"
Write-Host "3. Verify authentication:"
Write-Host "   lark-cli auth status"
