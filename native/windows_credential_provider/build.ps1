$ErrorActionPreference = "Stop"

$sourceRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $sourceRoot)
$output = Join-Path $projectRoot "dist\windows_phone_unlock"
New-Item -ItemType Directory -Force -Path $output | Out-Null

$compiler = Get-Command g++.exe -ErrorAction Stop
$target = & $compiler.Source -dumpmachine
if ($target -notmatch "x86_64") {
    throw "Aksh requires a 64-bit MinGW compiler. Found: $target"
}

$arguments = @(
    "-std=c++20",
    "-O2",
    "-shared",
    "-static",
    "-static-libgcc",
    "-static-libstdc++",
    "-o",
    (Join-Path $output "AkshCredentialProvider.dll"),
    (Join-Path $sourceRoot "AkshCredentialProvider.cpp"),
    (Join-Path $sourceRoot "AkshCredentialProvider.def"),
    "-lole32",
    "-luuid",
    "-lshlwapi",
    "-lsecur32",
    "-lcredui",
    "-ladvapi32"
)
& $compiler.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Credential provider build failed with exit code $LASTEXITCODE"
}
Write-Host "Built $output\AkshCredentialProvider.dll"
