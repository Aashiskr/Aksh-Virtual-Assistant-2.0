$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$installLog = Join-Path $projectRoot "logs\phone_unlock_install.txt"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $installLog) | Out-Null
$stage = "starting"
trap {
    $safeMessage = "Failed at " + $stage + ": " + $_.Exception.Message
    Set-Content -LiteralPath $installLog -Value $safeMessage -Encoding UTF8
    Write-Host $safeMessage -ForegroundColor Red
    exit 1
}

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

Set-Location -LiteralPath $projectRoot
$stage = "preparing the dedicated service environment"
$serviceEnvironment = Join-Path $projectRoot ".phone-unlock-venv"
$python = Join-Path $serviceEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    & py -3.10 -m venv $serviceEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 is required for Aksh Phone Unlock."
    }
}

& $python -m pip install --upgrade pip
& $python -m pip install pywin32 requests fastapi uvicorn cryptography python-dotenv
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
}
$pythonVersion = (& $python -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')").Trim()
$basePrefix = (& $python -c "import sys; print(sys.base_prefix)").Trim()
$pythonRuntime = Join-Path $basePrefix "python$pythonVersion.dll"
if (-not (Test-Path -LiteralPath $pythonRuntime)) {
    throw "Python service runtime DLL was not found: $pythonRuntime"
}
Get-ChildItem -LiteralPath $basePrefix -Filter "python*.dll" | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $serviceEnvironment -Force
}
$pywin32Runtime = Join-Path $serviceEnvironment "Lib\site-packages\pywin32_system32"
Get-ChildItem -LiteralPath $pywin32Runtime -Filter "*.dll" | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $serviceEnvironment -Force
}
$sitePackages = Join-Path $serviceEnvironment "Lib\site-packages"
Set-Content -LiteralPath (Join-Path $sitePackages "aksh_project.pth") -Value $projectRoot -Encoding ASCII
$serviceManagerModule = (& $python -c "import servicemanager; print(servicemanager.__file__)").Trim()
Copy-Item -LiteralPath $serviceManagerModule -Destination $serviceEnvironment -Force
$serviceBootstrap = @"
import sys

sys.path.insert(0, r'$sitePackages')
sys.path.insert(0, r'$sitePackages\win32')
sys.path.insert(0, r'$sitePackages\win32\lib')
sys.path.insert(0, r'$projectRoot')

from backend.windows_unlock.service import AkshUnlockService
"@
Set-Content `
    -LiteralPath (Join-Path $serviceEnvironment "aksh_service_bootstrap.py") `
    -Value $serviceBootstrap `
    -Encoding ASCII
& (Join-Path $projectRoot "native\windows_credential_provider\build.ps1")

Add-Type -AssemblyName System.Security
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class AkshNativeLogon {
    [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool LogonUser(
        string user, string domain, string password,
        int logonType, int provider, out IntPtr token);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
"@

$domain = $env:USERDOMAIN
$username = $env:USERNAME
$stage = "validating the Windows account password"
$credentialArguments = @{
    UserName = "$domain\$username"
    Message = "Enter your Windows account PASSWORD once. Do not enter the Windows Hello PIN."
}
$credential = Get-Credential @credentialArguments
if ($null -eq $credential) {
    throw "Credential enrollment was cancelled."
}
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential.Password)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $tokenHandle = [IntPtr]::Zero
    $valid = [AkshNativeLogon]::LogonUser(
        $username,
        $domain,
        $password,
        2,
        0,
        [ref]$tokenHandle
    )
    if (-not $valid) {
        throw "Windows rejected that password. Use the account password, not the PIN."
    }
    [AkshNativeLogon]::CloseHandle($tokenHandle) | Out-Null

    $tokenScript = @"
from backend.config import load_settings
from backend.remote.credentials import PairingTokenStore
s, _ = load_settings()
print(PairingTokenStore(s.data_dir).load_or_create(s.remote_token))
"@
    $pairingToken = $tokenScript | & $python -
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pairingToken)) {
        throw "Aksh pairing token could not be loaded."
    }

    $settingsPath = Join-Path $projectRoot "data\settings.json"
    $settings = if (Test-Path -LiteralPath $settingsPath) {
        Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    } else {
        [pscustomobject]@{}
    }
    $credentialJson = @{
        domain = $domain
        username = $username
        password = $password
    } | ConvertTo-Json -Compress
    $credentialBytes = [Text.Encoding]::UTF8.GetBytes($credentialJson)
    $tokenBytes = [Text.Encoding]::UTF8.GetBytes($pairingToken.Trim())
    $credentialBlob = [Security.Cryptography.ProtectedData]::Protect(
        $credentialBytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    $tokenBlob = [Security.Cryptography.ProtectedData]::Protect(
        $tokenBytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::LocalMachine
    )

    $stage = "encrypting the local credential"
    $programData = Join-Path $env:ProgramData "Aksh"
    New-Item -ItemType Directory -Force -Path $programData | Out-Null
    $config = @{
        version = 1
        credential_blob = [Convert]::ToBase64String($credentialBlob)
        token_blob = [Convert]::ToBase64String($tokenBlob)
        discovery_url = [string]$settings.remote_discovery_url
        public_port = 8765
        control_port = 8766
    } | ConvertTo-Json
    $configArguments = @{
        LiteralPath = (Join-Path $programData "phone_unlock.json")
        Value = $config
        Encoding = "UTF8"
    }
    Set-Content @configArguments
    & icacls.exe $programData /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $password = $null
    $pairingToken = $null
    $credential = $null
}

$stage = "registering the Windows credential provider"
$providerRoot = Join-Path $env:ProgramFiles "Aksh\CredentialProvider"
New-Item -ItemType Directory -Force -Path $providerRoot | Out-Null
$providerDll = Join-Path $providerRoot "AkshCredentialProvider.dll"
$providerSource = Join-Path $projectRoot "dist\windows_phone_unlock\AkshCredentialProvider.dll"
Copy-Item -LiteralPath $providerSource -Destination $providerDll -Force

$providerGuid = "{B7A1ED4B-58C7-4DB9-91C8-A733E49E8D22}"
$providerKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\$providerGuid"
$classKey = "HKLM:\SOFTWARE\Classes\CLSID\$providerGuid"
New-Item -Path $providerKey -Force | Out-Null
Set-Item -Path $providerKey -Value "Aksh Phone Unlock"
New-Item -Path "$classKey\InprocServer32" -Force | Out-Null
Set-Item -Path $classKey -Value "Aksh Phone Unlock Credential Provider"
Set-Item -Path "$classKey\InprocServer32" -Value $providerDll
$threadingArguments = @{
    Path = "$classKey\InprocServer32"
    Name = "ThreadingModel"
    Value = "Apartment"
    Force = $true
}
New-ItemProperty @threadingArguments | Out-Null

$stage = "installing the Windows unlock service"
$serviceScript = Join-Path $projectRoot "backend\windows_unlock\service.py"
& $python $serviceScript stop 2>$null
& $python $serviceScript remove 2>$null
& $python $serviceScript --startup auto install
if ($LASTEXITCODE -ne 0) {
    throw "Aksh Phone Unlock service installation failed."
}
$servicePythonPath = (
    $serviceEnvironment,
    $sitePackages,
    (Join-Path $sitePackages "win32"),
    (Join-Path $sitePackages "win32\lib"),
    $projectRoot
) -join ";"
New-ItemProperty `
    -Path "HKLM:\SYSTEM\CurrentControlSet\Services\AkshPhoneUnlock" `
    -Name "Environment" `
    -PropertyType MultiString `
    -Value @("PYTHONPATH=$servicePythonPath") `
    -Force | Out-Null
& sc.exe failure AkshPhoneUnlock reset= 86400 actions= restart/5000/restart/15000 | Out-Null
& sc.exe description AkshPhoneUnlock "Receives signed phone approvals at the Windows sign-in screen." | Out-Null
Start-Service -Name AkshPhoneUnlock

$stage = "finishing installation"
$desktopPython = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
if (Test-Path -LiteralPath $desktopPython) {
    $akshScript = Join-Path $projectRoot "aksh.py"
    $runCommand = '"' + $desktopPython + '" "' + $akshScript + '"'
    $runArguments = @{
        Path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
        Name = "Aksh"
        Value = $runCommand
        PropertyType = "String"
        Force = $true
    }
    New-ItemProperty @runArguments | Out-Null
}

Write-Host ""
Write-Host "Aksh Phone Unlock is installed." -ForegroundColor Green
Write-Host "Keep Windows PIN/password available as your recovery sign-in method."
Write-Host "Open the Aksh Android app once to enroll the phone key and allow notifications."
Set-Content -LiteralPath $installLog -Value "Installed successfully" -Encoding UTF8
