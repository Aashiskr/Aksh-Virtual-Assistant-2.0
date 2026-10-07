$ErrorActionPreference = "Stop"

$scriptPath = $MyInvocation.MyCommand.Path
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal] $identity
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ('"' + $scriptPath + '"')
    )
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments
    exit
}

$phoneKey = [IO.Path]::GetFullPath(
    (Join-Path $env:ProgramData "Aksh\phone_unlock_key.json")
)
$expected = [IO.Path]::GetFullPath(
    (Join-Path $env:ProgramData "Aksh\phone_unlock_key.json")
)
if ($phoneKey -ne $expected) {
    throw "Unexpected Aksh phone-key path."
}
Remove-Item -LiteralPath $phoneKey -Force -ErrorAction SilentlyContinue
Restart-Service -Name AkshPhoneUnlock -ErrorAction Stop
Write-Host "Phone enrollment was reset. Open Aksh on the phone to enroll again."
