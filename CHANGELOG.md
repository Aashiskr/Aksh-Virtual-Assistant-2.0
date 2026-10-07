# Changelog

## Unreleased

- Added an Aksh Remote daily 11:00 AM IST career briefing for B.Tech final-year
  opportunities in Uttar Pradesh, Bihar, and relevant All-India recruitment.
- Added authenticated FCM device registration, Cloudflare Cron delivery, a
  latest-briefing screen, source links, and an end-to-end test action that work
  independently of the laptop.

## 2.1.4 - 2026-08-17

- Added an in-memory Session Task Notebook with user/Aksh ownership, real action
  outcomes, confirmation state, and contextual follow-up decisions.
- Added a capture-excluded right-click notebook viewer; all notebook data is
  erased when Aksh exits.
- Added ephemeral Current Workspace detection for supported open apps, visible
  browser page titles, sanitized focused URLs, recent browser actions, and
  reuse of an already-open requested app.
- Changed `task notebook dikhao` to silently generate and open a styled
  temporary PDF, with text fallback and automatic export cleanup on exit.

## 2.1.3 - 2026-08-17

- Added persistent hashed voice replay protection so commands captured before a
  laptop restart are not executed again as fresh always-listening input.
- Added a startup quarantine for non-wake continuous audio, duplicate command
  suppression, and safer uncapped ambient-noise calibration.
- Kept explicit `Hey Aksh ...` and emergency microphone-off phrases available
  during startup protection.
- No-wake-word listening now needs one explicit activation after every Aksh
  restart, so new transcript variants cannot escape the startup replay guard.

## 2.1.2 - 2026-08-09

- Fixed WebRTC track signaling being mistaken for a genuinely connected live
  stream, which could delay Internet fallback for about a minute.
- Fixed manual reconnect treating a stale video element as the new live stream.
- Added automatic discovery re-resolution when an open screen still points at
  an expired Cloudflare Quick Tunnel URL.
- Added failed-offer peer cleanup and separated remote session networking from
  the screen transport state machine.

## 2.1.1 - 2026-08-09

- Fixed different-network remote viewing getting stuck on `RECONNECTING` after
  a direct WebRTC ICE/NAT failure.
- Kept the authenticated screen session alive while switching automatically to
  secure HTTPS frames and input.
- Added session heartbeat/renewal, bounded reconnect backoff, and automatic
  Cloudflare Quick Tunnel process recovery.

## 2.1.0 - 2026-08-05

- Added a phone-authenticated **Unlock / secure remote login** handoff for
  Windows Home using the official Chrome Remote Desktop Android app.
- Added Android biometric/device-credential gating without storing or
  transmitting any Windows or remote-access credential.
- Added one-click laptop host setup guidance and explicit security/privacy
  boundaries for locked-screen access.

## 2.0.1 - 2026-08-04

- Replaced the remote-screen Esc and Back controls with reliable Scroll Up and
  Scroll Down buttons for the currently pointed laptop page.

## 2.0.0 - 2026-08-04

- Added Groq-backed bounded agent planning and natural conversation.
- Added permission-aware plan suspension and exact confirmation resume.
- Added draggable expressive desktop pet, hotkey, typed commands, and Meeting
  Mode.
- Added Android voice/text commands and permission-gated remote screen control.
- Added one-finger remote scrolling, pinch zoom, pan, and landscape fullscreen.
- Added stateful shopping, flexible WhatsApp matching/calls, and real YouTube
  playback resolution.
- Fixed explicit browser routing so requested websites open in Brave, Chrome,
  Edge, or Firefox instead of the Windows default browser.
- Removed shared/personal Cloudflare resources from public configuration.
- Added DPAPI/Android Keystore secret storage, public-file guard, and CI checks.
