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

The app needs Internet, microphone, notification, biometric, boot receiver, and
foreground-service permissions. The lock-screen action signs a fresh Windows
unlock challenge with a biometric-protected Android Keystore key. Deploy your own
Cloudflare discovery Worker using the repository instructions, then configure
its HTTPS URL, the Device ID, and the pairing token shown by **Aksh pet > Phone
remote setup**. The app encrypts the token with Android Keystore and resolves
the laptop's latest HTTPS URL after future phone or laptop restarts. The manual
URL field is an optional HTTPS fallback. Pairing credentials are never sent
over plain HTTP, and no shared Aksh relay or developer account is built in.

## Daily career and government-exam briefing

The main screen contains a daily briefing switch and a **View latest career
briefing** button. The current owner profile is intentionally fixed to:

- B.Tech, fourth year, all branches
- Uttar Pradesh and Bihar
- relevant All-India technical opportunities
- delivery at 11:00 AM Asia/Kolkata

The phone registers a Firebase Cloud Messaging token with the same authenticated
Cloudflare relay used for discovery. The Worker runs at 05:30 UTC (11:00 AM
IST), collects recent career and recruitment headlines, stores the latest brief,
and pushes a notification. The laptop and Aksh desktop process can both be off.
Always verify eligibility, dates, fees, and application links on the conducting
body's official portal before applying.

### One-time Firebase setup

1. Create a Firebase project and add an Android app with package name
   `com.aksh.remote`.
2. Download `google-services.json` into
   `frontend/mobile/android/app/google-services.json`. This path is Git-ignored.
3. Enable the Firebase Cloud Messaging API.
4. In **Firebase project settings > Service accounts**, generate a private key.
   Keep the downloaded JSON outside this repository.
5. From `infrastructure/cloudflare/discovery-worker`, store the three values as
   encrypted Worker secrets. Paste the matching value from the service-account
   JSON when Wrangler prompts:

```powershell
npx wrangler secret put FIREBASE_PROJECT_ID
npx wrangler secret put FIREBASE_CLIENT_EMAIL
npx wrangler secret put FIREBASE_PRIVATE_KEY
npx wrangler deploy
```

Never commit the service-account JSON, private key, FCM registration token, or
the app's generated APK signing material. After installing the rebuilt APK,
open it once, allow notifications, save the existing relay pairing, leave the
daily briefing switch enabled, and use **View latest career briefing > Send
test** to verify the end-to-end path.

## Remote screen

Right-click the laptop pet, choose **Phone remote setup**, and enable **Remote
screen access**. Then tap **View & control laptop** in the Android app. The
screen uses WebRTC first and protected HTTPS frames as a network fallback.
When phone and laptop are on different networks, an unreachable direct WebRTC
path automatically changes to **LIVE - SECURE INTERNET** without invalidating
the screen session. Temporary Internet interruptions retry with bounded backoff,
and an expired screen session is restored automatically.
Tap to click, double-tap to double-click, and hold to right-click. A deliberate
one-finger vertical swipe scrolls the laptop; horizontal or diagonal movement
still moves/drags the pointer. Two-finger scrolling remains available at 100%
zoom. Quick keys and safe text entry are included.
The visible **Scroll up** and **Scroll down** controls replace Esc and Back;
they scroll whichever laptop page or window is currently under the pointer.
Pinch with two fingers for image-style zoom anchored to the touched area. Above 100%, move both fingers
together to pan across hidden left, right, top, and bottom areas. At 100%, the
same vertical gesture scrolls the laptop. Floating controls support 100% to
250% in 25% steps; tap the percentage to reset. The fullscreen button enters immersive landscape and
returns to normal orientation when tapped again.

Enable the lower **PPT Present** control for a focused presenter
overlay with **Previous**, **Next**, and relative **Laptop zoom** controls.
Tap or pinch the part of the slide you want first; the focus ring marks it and
the PPT tap is not sent as a laptop click. Laptop zoom then drives Windows
Magnifier at that focus point. The separate **Phone zoom** buttons and pinch
gesture enlarge the phone preview around the touched area. Closing or replacing
the active screen session cleans up presentation state and any Magnifier
instance started by Aksh.

Remote-screen permission is off by default. Disabling it closes active sessions
immediately. A new phone connection replaces the previous screen session. The
app blocks screenshots of its own remote-screen activity, and the server accepts
only bounded pointer, scroll, text, allow-listed key events, and dedicated
presentation actions.

Current limitations: only the primary monitor is shown; Windows secure desktop
(login/UAC), DRM-protected content, and a sleeping or powered-off laptop are not
remotely controllable.

## Phone-approved Windows sign-in

The main screen includes **Unlock laptop with fingerprint**. After the Windows
installer has enrolled the local account, Aksh requests a one-time challenge,
shows Android's system biometric prompt, and signs the challenge using an
auth-per-use phone key. Fingerprint data and the Windows password never travel
between devices.

The foreground monitor checks the authenticated health endpoint every few
seconds. When Windows reports its lock state after boot or a later lock, Aksh
posts a high-priority notification whose action opens the fingerprint approval
screen. Allow notification access and set battery use to unrestricted if the
phone vendor aggressively stops background apps.

Windows PIN/password remains available directly on the laptop. See
[`docs/SECURE_REMOTE_LOGIN.md`](../../../docs/SECURE_REMOTE_LOGIN.md).
