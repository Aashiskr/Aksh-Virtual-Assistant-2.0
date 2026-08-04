$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $projectRoot

try {
    $version = & py -3.10 -c "import sys; print(sys.version.split()[0])"
} catch {
    Write-Host "Python 3.10 was not found." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/release/python-31011/"
    exit 1
}

Write-Host "Using Python $version"
$virtualEnvironment = Join-Path $projectRoot ".venv"
$python = Join-Path $virtualEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    & py -3.10 -m venv $virtualEnvironment
}
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& (Join-Path $PSScriptRoot "install_cloudflared.ps1")

$environmentFile = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot ".env.example") `
        -Destination $environmentFile
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run run_aksh.bat. First run will privately ask for this laptop's Groq key."
Write-Host "Autostart was not enabled. Use infrastructure\windows\enable_autostart.ps1 if wanted."
