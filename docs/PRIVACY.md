# Privacy and data flow

Aksh is local-first for control and storage, but AI transcription and planning
use Groq. Review this document before using voice, imported profiles, phone
remote access, or Meeting Mode.

## Data sent to Groq

- Voice command audio for transcription
- Command text and recent conversation context for intent planning
- Relevant imported profile excerpts when personalization is needed
- Meeting audio/text snippets, questions, and context while Meeting Mode is on

Aksh does not intentionally send the phone pairing token, Cloudflare KV ID, or
Windows DPAPI blobs to Groq. Groq handling and retention are governed by the
user's Groq account and applicable terms.

## Data sent through Cloudflare

Cloudflared forwards authenticated phone requests to the loopback API. The
optional per-user discovery Worker receives the bearer token for authorization
and stores only the current HTTPS tunnel URL plus an update timestamp in KV. It
does not store the token itself.

## Data stored locally

Secrets, settings, imported profile text, meeting reports, browser automation
profiles, temporary phone audio, and logs stay in ignored local directories.
Uploaded phone audio is removed after processing. Raw Meeting Mode audio is
processed in memory and is not intentionally saved.

## User responsibilities

- Obtain participant consent before transcription or AI meeting assistance.
- Keep the paired phone locked and do not share the pairing token.
- Disable Remote Screen when it is not needed.
- Review commands and confirmations before allowing external communications or
  system actions.
- Do not commit or upload `.env`, `data/`, `logs/`, `private/`, browser profiles,
  account-specific `wrangler.jsonc`, APK signing keys, or local Android config.
