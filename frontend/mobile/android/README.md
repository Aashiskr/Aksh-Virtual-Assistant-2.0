# Aksh Remote Android app

This native Android app sends voice or typed commands from the phone to the
paired Aksh instance running on the laptop. It can also show and control the
laptop's primary screen after the owner enables that permission on the pet.
For voice, the laptop performs
Groq transcription before executing the command. Typed commands use the same
Aksh command, confirmation, and reporting pipeline without transcription. The
phone shows the recognized/typed command and completion report.

## Build

```powershell
cd frontend\mobile\android
.\gradlew.bat assembleDebug
```

Output:

```text
app/build/outputs/apk/debug/app-debug.apk
```

The app needs only Internet and microphone permissions. Deploy your own
Cloudflare discovery Worker using the repository instructions, then configure
its HTTPS URL, the Device ID, and the pairing token shown by **Aksh pet > Phone
remote setup**. The app encrypts the token with Android Keystore and resolves
the laptop's latest HTTPS URL after future phone or laptop restarts. The manual
URL field is an optional HTTPS fallback. Pairing credentials are never sent
over plain HTTP, and no shared Aksh relay or developer account is built in.

## Remote screen

Right-click the laptop pet, choose **Phone remote setup**, and enable **Remote
screen access**. Then tap **View & control laptop** in the Android app. The
screen uses WebRTC first and protected HTTPS frames as a network fallback.
Tap to click, double-tap to double-click, and hold to right-click. A deliberate
one-finger vertical swipe scrolls the laptop; horizontal or diagonal movement
still moves/drags the pointer. Two-finger scrolling remains available at 100%
zoom. Quick keys and safe text entry are included.
Pinch with two fingers for image-style zoom. Above 100%, move both fingers
together to pan across hidden left, right, top, and bottom areas. At 100%, the
same vertical gesture scrolls the laptop. Floating controls support 100% to
250% in 25% steps; tap the percentage to reset. The fullscreen button enters immersive landscape and
returns to normal orientation when tapped again.

Remote-screen permission is off by default. Disabling it closes active sessions
immediately. A new phone connection replaces the previous screen session. The
app blocks screenshots of its own remote-screen activity, and the server accepts
only bounded pointer, scroll, text, and allow-listed key events.

Current limitations: only the primary monitor is shown; Windows secure desktop
(login/UAC), DRM-protected content, and a sleeping or powered-off laptop are not
remotely controllable.
