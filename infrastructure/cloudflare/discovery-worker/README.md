# Aksh device discovery relay

This Cloudflare Worker lets one Aksh Android app find its paired laptop after a
Quick Tunnel URL changes. Every installer deploys an independent Worker and KV
namespace; the public project does not ship a shared developer relay.

The laptop pairing token is never stored in KV. The public Device ID is the
first 24 hexadecimal characters of the token's SHA-256 digest. KV contains only
the current HTTPS tunnel URL and update time for 14 days, and every read/write
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
