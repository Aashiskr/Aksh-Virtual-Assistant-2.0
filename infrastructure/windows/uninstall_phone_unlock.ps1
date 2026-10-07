$ErrorActionPreference = "Stop"

$scriptPath = $MyInvocation.MyCommand.Path
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal] $identity
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $elevatedArguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ('"' + $scriptPath + '"')
    )
    Start-Process powershell.exe -Verb RunAs -ArgumentList $elevatedArguments
    exit
}

Stop-Service -Name AkshPhoneUnlock -Force -ErrorAction SilentlyContinue
& sc.exe delete AkshPhoneUnlock | Out-Null

$providerGuid = "{B7A1ED4B-58C7-4DB9-91C8-A733E49E8D22}"
$providerKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\$providerGuid"
$classKey = "HKLM:\SOFTWARE\Classes\CLSID\$providerGuid"
Remove-Item -LiteralPath $providerKey -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $classKey -Recurse -Force -ErrorAction SilentlyContinue

$providerRoot = [IO.Path]::GetFullPath((Join-Path $env:ProgramFiles "Aksh\CredentialProvider"))
$expectedProviderRoot = [IO.Path]::GetFullPath((Join-Path $env:ProgramFiles "Aksh\CredentialProvider"))
if ($providerRoot -eq $expectedProviderRoot) {
    Remove-Item -LiteralPath $providerRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "Aksh" -ErrorAction SilentlyContinue

$programDataRoot = [IO.Path]::GetFullPath((Join-Path $env:ProgramData "Aksh"))
$expectedProgramDataRoot = [IO.Path]::GetFullPath((Join-Path $env:ProgramData "Aksh"))
if ($programDataRoot -eq $expectedProgramDataRoot) {
    Remove-Item -LiteralPath $programDataRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Aksh Phone Unlock was removed."
Write-Host "Windows PIN/password sign-in was not changed."
