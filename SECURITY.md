# Security policy

## Supported version

Security fixes target Aksh 2.x. The archived keyword-based prototype is not part
of the public release or supported runtime.

## Reporting a vulnerability

Please use the repository's private **Security advisory > Report a
vulnerability** flow. Do not put API keys, pairing tokens, personal data,
screenshots, transcripts, exploit details, or remote URLs in a public issue.

Include the affected component, reproduction steps using synthetic data, impact,
and a suggested fix if available. Revoke any exposed credential before writing
the report.

## Security model

- Groq can propose only actions in the central catalog; responses are validated
  against a strict JSON schema and converted to bounded plans.
- Sensitive/dangerous actions pause for owner confirmation according to policy.
- The phone API uses a random bearer token. Its public ingress is an HTTPS
  Cloudflare Tunnel while the local FastAPI listener stays on loopback.
- Remote-screen sessions use an additional random, expiring token and are off by
  default. Disabling the feature terminates active sessions.
- Windows secrets use DPAPI; the Android pairing token uses Android Keystore.
- Cloudflare KV stores a tunnel URL and timestamp, never the pairing token.

This model does not protect a machine that is already compromised, an unlocked
trusted phone, a stolen Windows account session, malicious accessibility
software, or a user who approves a harmful action.

## Credential rotation

- **Groq:** revoke the key in the Groq console, stop Aksh, delete
  `data/groq_key.dat` (and remove `GROQ_API_KEY` from `.env` if present), then
  restart and enter a new key.
- **Phone pairing:** stop Aksh, delete `data/remote_token.dat`, restart Aksh, and
  pair every trusted phone again.
- **Cloudflare:** rotate the relevant account/API credential in Cloudflare and
  redeploy your Worker. The Worker source does not require a secret token.

Never send credentials in chat, screenshots, bug reports, commits, release
assets, or meeting reports.
