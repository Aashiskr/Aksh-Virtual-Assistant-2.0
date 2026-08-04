# Contributing

Thanks for improving Aksh. Keep changes small, testable, and organized under the
existing backend/frontend/infrastructure boundaries.

1. Create a focused branch.
2. Add or update regression tests for behavior changes.
3. Run Python tests, Android gesture tests, and affected platform checks.
4. Run `py -3.10 scripts/check_public_repo.py` before committing.
5. Explain user impact, safety implications, and validation in the pull request.

Never use real names, phone numbers, API keys, pairing tokens, CV content,
meeting transcripts, browser profiles, local paths, or screenshots containing
personal data as fixtures. Use clearly synthetic values.

New agent actions must be registered in the central catalog, validate every
parameter, return an `ActionResult`, and be assigned the correct sensitivity.
Do not add arbitrary shell/code execution as an agent tool.
