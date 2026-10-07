# Privacy and data flow

Aksh is local-first for control and storage, but AI transcription and planning
use Groq. Review this document before using voice, imported profiles, phone
remote access, or Meeting Mode.

## Data sent to Groq

- Voice command audio for transcription
- Command text and recent conversation context for intent planning
- A redacted summary of recent in-memory Session Task Notebook entries when it
  helps resolve a follow-up command
- Names and titles of supported visible applications, plus the focused
  browser's sanitized URL without query parameters or fragments, as ephemeral
  Current Workspace context for intent planning
- Relevant imported profile excerpts when personalization is needed
- Meeting audio/text snippets, questions, and context while Meeting Mode is on

Aksh does not intentionally send the phone pairing token, Cloudflare KV ID, or
Windows DPAPI blobs to Groq. Groq handling and retention are governed by the
user's Groq account and applicable terms.

## Data sent through Cloudflare

Cloudflared forwards authenticated phone requests to the loopback API. The
optional per-user discovery Worker receives the bearer token for authorization
and does not store that pairing token itself. By default it stores the current
HTTPS tunnel URL plus an update timestamp in KV. If the owner enables the daily
career briefing, it also stores the phone's Firebase registration token, the
fixed B.Tech/year/region preferences, and the most recent briefing. The Worker
fetches public career/recruitment feeds and sends the resulting alert through
Firebase Cloud Messaging. Disabling the switch removes the cloud push
registration; rotating the phone pairing token prevents the old phone from
reading the briefing.

## Data stored locally

Secrets, settings, imported profile text, meeting reports, browser automation
profiles, temporary phone audio, and logs stay in ignored local directories.
Uploaded phone audio is removed after processing. Raw Meeting Mode audio is
processed in memory and is not intentionally saved.
Always-listening replay protection stores only SHA-256 fingerprints and
timestamps in `data/voice_replay_guard.json`; it does not store command text or
audio. The file is machine-local and Git-ignored with the rest of `data/`.
When **Double clap to talk** is enabled, Aksh locally samples the microphone for
two short, sharp transients even if voice-command listening is off. These clap
samples are neither transcribed nor saved. Disable double-clap activation when
the microphone must not be sampled at all.

The Session Task Notebook is different from saved reminders and replay
fingerprints: its working state is held in process memory. It records requests,
action plans, confirmations, and outcomes for current-session decisions. When
the user explicitly asks to view it, Aksh writes a temporary PDF (or text
fallback) under `tmp/session_notebook/` and opens it locally. Normal Exit Aksh
deletes these exports and discards the in-memory notebook.
Current Workspace observes only supported top-level visible windows. It does
not read browser history or enumerate hidden/background tabs. Visible window
titles may contain page or document names, so this context can be sent to Groq
when Aksh plans a command. Exit Aksh to clear it immediately.

## Phone-approved Windows sign-in

Android performs biometric matching locally. Aksh receives no fingerprint image,
template, or biometric result data; Android Keystore only permits the phone key
to sign the current one-time challenge after successful authentication.

The Windows account password is entered once into the local administrator setup
prompt. It is encrypted with machine-bound Windows DPAPI and stored under the
restricted Aksh ProgramData directory. It is never sent to the phone, discovery
relay, Cloudflare Tunnel, or any AI provider. After approval, the SYSTEM broker
releases it once to the credential provider through a local restricted pipe.

## User responsibilities

- Obtain participant consent before transcription or AI meeting assistance.
- Keep the paired phone locked and do not share the pairing token.
- Disable Remote Screen when it is not needed.
- Keep Windows PIN/password recovery available, and rerun phone-unlock setup
  immediately after changing the Windows account password.
- Review commands and confirmations before allowing external communications or
  system actions.
- Do not commit or upload `.env`, `data/`, `logs/`, `private/`, browser profiles,
  account-specific `wrangler.jsonc`, APK signing keys, or local Android config.
