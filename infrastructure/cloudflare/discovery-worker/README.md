# Aksh device discovery relay

This Cloudflare Worker lets one Aksh Android app find its paired laptop after a
Quick Tunnel URL changes. It also runs the optional 11:00 AM IST B.Tech career
briefing while the laptop is offline. Every installer deploys an independent
Worker and KV namespace; the public project does not ship a shared developer
relay.

The laptop pairing token is never stored in KV. The public Device ID is the
first 24 hexadecimal characters of the token's SHA-256 digest. KV contains the
current HTTPS tunnel URL and update time for 14 days. When career briefing is
enabled, KV also holds the phone's FCM registration token, the fixed B.Tech
profile, and the latest briefing for up to 120 days. Every phone read/write
requires the matching high-entropy pairing token.

## Deploy your relay

Prerequisites: Node.js 22+ and a Cloudflare account.

```powershell
cd infrastructure\cloudflare\discovery-worker
npm ci
npx wrangler login
npx wrangler kv namespace create DEVICES
Copy-Item wrangler.example.jsonc wrangler.jsonc
```

Open the generated `wrangler.jsonc` and replace
`REPLACE_WITH_YOUR_KV_NAMESPACE_ID` with the ID printed by Wrangler. The real
file is Git-ignored so an account-specific namespace ID is never published by
accident.

The example configuration includes `30 5 * * *`; Cloudflare Cron uses UTC, so
this runs daily at 05:30 UTC / 11:00 AM Asia/Kolkata.

## Configure phone push notifications

Create a Firebase Android app for `com.aksh.remote`, download its
`google-services.json` into `frontend/mobile/android/app/`, and enable the
Firebase Cloud Messaging API. Generate a Firebase service-account private key,
keep that JSON outside the repository, and add its values as encrypted Worker
secrets:

```powershell
npx wrangler secret put FIREBASE_PROJECT_ID
npx wrangler secret put FIREBASE_CLIENT_EMAIL
npx wrangler secret put FIREBASE_PRIVATE_KEY
```

The Worker mints short-lived OAuth tokens and sends through the FCM HTTP v1 API;
the service-account private key must never appear in source, Wrangler JSON,
chat, screenshots, or version control.

Then validate and deploy:

```powershell
npm test
npx wrangler deploy
```

Copy the resulting `https://...workers.dev` URL into:

1. `AKSH_DISCOVERY_URL` in the laptop's local `.env` file.
2. **Your Cloudflare discovery relay URL** in the Android app.

Do not put the pairing token in Wrangler configuration, Worker source, GitHub,
or Cloudflare KV. If the token is exposed, delete `data/remote_token.dat` while
Aksh is stopped to generate a new token, then pair the phone again.
