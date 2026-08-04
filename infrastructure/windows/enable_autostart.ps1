$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$entryPoint = Join-Path $projectRoot "aksh.py"
$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "Aksh Virtual Assistant.lnk"

$pythonPath = & py -3.10 -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
    throw "Python 3.10 was not found."
}
$pythonwPath = Join-Path (Split-Path -Parent $pythonPath.Trim()) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonwPath)) {
    throw "pythonw.exe was not found beside Python 3.10."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = "`"$entryPoint`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Start Aksh Virtual Assistant at Windows sign-in"
$shortcut.Save()

Write-Host "Aksh autostart enabled: $shortcutPath" -ForegroundColor Green
