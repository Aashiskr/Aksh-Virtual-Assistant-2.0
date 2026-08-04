$ErrorActionPreference = "Stop"

$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "Aksh Virtual Assistant.lnk"

if (Test-Path -LiteralPath $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath
    Write-Host "Aksh autostart disabled." -ForegroundColor Green
} else {
    Write-Host "Aksh autostart was already disabled."
}
