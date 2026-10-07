# Unlock Windows with your phone fingerprint

Aksh can unlock this Windows 11 Home laptop after it reaches the normal sign-in
screen. Android verifies your fingerprint locally and signs a fresh request.
Windows then uses the account credential that was enrolled locally during setup.

Normal Windows PIN/password sign-in remains enabled and should always be kept as
the recovery path.

## One-time laptop setup

Open PowerShell from the repository and run:

    powershell -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\install_phone_unlock.ps1

Approve the administrator prompt. A private Windows credential dialog then asks
for the account password. Enter the password, not the Windows Hello PIN. Never
paste that password into chat, source files, or the Android app.

The installer:

- builds and registers the 64-bit Aksh credential provider;
- creates the automatic Aksh Phone Unlock Windows service;
- encrypts the account credential using machine-bound Windows DPAPI;
- restricts the saved ciphertext to SYSTEM and Administrators;
- keeps every built-in Windows credential provider enabled.

## Phone setup

1. Install the current Aksh Android APK.
2. Open it once and save the existing discovery URL, Device ID, and pairing
   token.
3. Allow notifications and biometric access.
4. Allow unrestricted background battery use if the phone vendor stops the
   persistent laptop monitor.
5. Tap **Unlock laptop with fingerprint** once while Windows is locked. This
   enrolls the phone public key and displays Android's biometric prompt.

The phone private key is created in Android Keystore and requires a fresh strong
biometric authentication for every signature.

## Normal use

1. Power on the laptop.
2. When Windows reaches its sign-in screen, the pre-login broker starts its
   secure tunnel and publishes the current URL through your discovery relay.
3. The Aksh phone monitor detects the locked state, normally within several
   seconds, and posts **Your laptop is ready**.
4. Tap **Unlock with fingerprint** and authenticate on the phone.
5. The phone signs the 60-second challenge. It does not send the fingerprint,
   account password, or Windows Hello PIN.
6. The broker verifies the signature and releases the credential once through a
   local SYSTEM-only pipe to the Aksh credential provider.
7. Windows validates the normal account credential and opens the session.

You can ignore the notification and enter the Windows PIN/password manually at
any time.

## Security properties

- Every challenge contains a cryptographically random nonce, expires after 60
  seconds, and is removed on its first approval attempt.
- The phone uses P-256 ECDSA with SHA-256. The private key never leaves Android
  Keystore.
- The encrypted Windows password never leaves the laptop.
- The Cloudflare tunnel and discovery relay only carry an authenticated
  challenge, phone public key, and signature.
- A different phone cannot replace an enrolled key remotely.
- Aksh never filters or disables Microsoft's built-in sign-in options.

## Maintenance and recovery

Rerun the installer after changing the Windows account password.

If Android is reinstalled, fingerprints are re-enrolled, or the phone is
replaced, run:

    powershell -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\reset_phone_unlock.ps1

To remove the feature completely:

    powershell -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\uninstall_phone_unlock.ps1

Uninstalling Aksh Phone Unlock does not change or remove the Windows account
password, PIN, or Windows Hello configuration.

The laptop must be powered on, connected to a network at the sign-in screen, and
able to reach Cloudflare. Phone unlock cannot operate while the laptop is fully
powered off or offline.
