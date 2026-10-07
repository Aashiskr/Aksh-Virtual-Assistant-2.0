param(
    [switch] $OpenPhoneActivity
)

$ErrorActionPreference = "Stop"

$env:ADB_USB_LEGACY = "1"
$adb = Join-Path (Get-Location) ".tools\android-sdk\platform-tools\adb.exe"
$python = "C:\Users\ar685\AppData\Local\Programs\Python\Python310\python.exe"

$token = & $python -c @"
from backend.config import load_settings
from backend.remote.credentials import PairingTokenStore

settings = load_settings()[0]
print(PairingTokenStore(settings.data_dir).load_or_create(settings.remote_token))
"@

$headers = @{ Authorization = "Bearer $token" }
$brokerLockedSeen = $false
$notificationSeen = $false
$unlockActivitySeen = $false
$phoneActivityOpened = $false
$windowsLockScreenSeen = $false
$windowsUnlocked = $false

function Invoke-PhoneNotificationTap {
    & $adb -s ZA2234CL64 shell cmd statusbar expand-notifications | Out-Null
    Start-Sleep -Milliseconds 900
    & $adb -s ZA2234CL64 shell uiautomator dump /sdcard/aksh-notifications.xml | Out-Null
    $rawXml = (& $adb -s ZA2234CL64 shell cat /sdcard/aksh-notifications.xml) -join ""
    [xml] $ui = $rawXml
    $node = $ui.SelectNodes("//node") |
        Where-Object {
            $_.text -match "Your laptop is ready|Windows is at the lock screen|Unlock with fingerprint"
        } |
        Select-Object -First 1
    if (-not $node) {
        return $false
    }
    if ($node.bounds -notmatch "\[(\d+),(\d+)\]\[(\d+),(\d+)\]") {
        return $false
    }
    $x = ([int] $matches[1] + [int] $matches[3]) / 2
    $y = ([int] $matches[2] + [int] $matches[4]) / 2
    & $adb -s ZA2234CL64 shell input tap $x $y | Out-Null
    return $true
}

Start-Process rundll32.exe -ArgumentList "user32.dll,LockWorkStation"
$deadline = (Get-Date).AddMinutes(4)

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 650

    $locked = [bool](Get-Process -Name LogonUI -ErrorAction SilentlyContinue)
    if ($locked) {
        $windowsLockScreenSeen = $true
    }

    try {
        $health = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8766/v1/health" `
            -Headers $headers `
            -TimeoutSec 2
        if ($health.computer_state -eq "locked") {
            $brokerLockedSeen = $true
        }
    } catch {
    }

    try {
        $notifications = (& $adb -s ZA2234CL64 shell dumpsys notification --noredact) -join "`n"
        if ($notifications -match "0\|com\.aksh\.remote\|120\|") {
            $notificationSeen = $true
            if ($OpenPhoneActivity -and -not $phoneActivityOpened) {
                $phoneActivityOpened = Invoke-PhoneNotificationTap
            }
        }
    } catch {
    }

    try {
        $focus = (& $adb -s ZA2234CL64 shell dumpsys activity activities |
            Select-String "mResumedActivity" |
            Select-Object -First 1) -join ""
        if ($focus -match "UnlockActivity|Biometric") {
            $unlockActivitySeen = $true
        }
    } catch {
    }

    if ($windowsLockScreenSeen -and -not $locked) {
        $windowsUnlocked = $true
        break
    }
}

"WINDOWS_LOCK_SCREEN_SEEN=$windowsLockScreenSeen"
"BROKER_LOCKED_STATE_SEEN=$brokerLockedSeen"
"PHONE_UNLOCK_NOTIFICATION_SEEN=$notificationSeen"
"PHONE_UNLOCK_ACTIVITY_OPENED=$phoneActivityOpened"
"PHONE_UNLOCK_ACTIVITY_SEEN=$unlockActivitySeen"
"WINDOWS_RETURNED_TO_DESKTOP=$windowsUnlocked"

if (-not $windowsUnlocked) {
    exit 3
}
