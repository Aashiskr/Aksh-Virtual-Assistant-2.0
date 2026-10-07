from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MeetingSchedulingError(RuntimeError):
    """Raised when Aksh cannot safely create the requested Calendar event."""


@dataclass(frozen=True, slots=True)
class ChromeAccount:
    profile_directory: str
    profile_name: str
    account_name: str
    email: str = ""
    aliases: tuple[str, ...] = ()
    primary: bool = False

    @property
    def label(self) -> str:
        return self.account_name or self.email or self.profile_name


class ChromeAccountResolver:
    """Find visible Chrome profile/account metadata without reading cookies."""

    def __init__(self, user_data_dir: Path | None = None):
        local_app_data = os.getenv("LOCALAPPDATA", "")
        self.user_data_dir = user_data_dir or (
            Path(local_app_data) / "Google" / "Chrome" / "User Data"
        )

    def resolve(self, requested: str = "") -> ChromeAccount:
        accounts = self.accounts()
        if not accounts:
            raise MeetingSchedulingError(
                "Chrome mein koi signed-in Google account nahi mila."
            )
        requested = str(requested or "").strip()
        if not requested:
            return next((item for item in accounts if item.primary), accounts[0])

        needle = _normalise_alias(requested)
        exact = [
            account
            for account in accounts
            if needle in {_normalise_alias(alias) for alias in account.aliases}
        ]
        if exact:
            return next((item for item in exact if item.primary), exact[0])

        partial = [
            account
            for account in accounts
            if any(
                needle in _normalise_alias(alias)
                or _normalise_alias(alias) in needle
                for alias in account.aliases
                if _normalise_alias(alias)
            )
        ]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            labels = ", ".join(dict.fromkeys(item.label for item in partial))
            raise MeetingSchedulingError(
                f"'{requested}' multiple accounts se match hua: {labels}. "
                "Exact account name boliye."
            )
        raise MeetingSchedulingError(
            f"Chrome mein '{requested}' account nahi mila. "
            "Meeting kisi doosre account se nahi banayi gayi."
        )

    def accounts(self) -> list[ChromeAccount]:
        local_state = _read_json(self.user_data_dir / "Local State")
        info_cache = (
            local_state.get("profile", {}).get("info_cache", {})
            if isinstance(local_state, dict)
            else {}
        )
        if not isinstance(info_cache, dict):
            return []

        accounts: list[ChromeAccount] = []
        for profile_directory, raw_profile in info_cache.items():
            if not isinstance(raw_profile, dict):
                continue
            profile_name = str(
                raw_profile.get("name")
                or raw_profile.get("shortcut_name")
                or profile_directory
            ).strip()
            primary_email = str(raw_profile.get("user_name") or "").strip()
            primary_name = str(
                raw_profile.get("gaia_name")
                or raw_profile.get("given_name")
                or profile_name
            ).strip()
            preference_accounts = self._preference_accounts(profile_directory)
            primary_added = False
            for raw_account in preference_accounts:
                email = str(raw_account.get("email") or "").strip()
                name = str(
                    raw_account.get("full_name")
                    or raw_account.get("given_name")
                    or email.partition("@")[0]
                ).strip()
                is_primary = bool(
                    primary_email
                    and email.casefold() == primary_email.casefold()
                )
                primary_added = primary_added or is_primary
                aliases = _account_aliases(name, email)
                if is_primary:
                    aliases = (*aliases, profile_name, profile_directory)
                accounts.append(
                    ChromeAccount(
                        profile_directory=profile_directory,
                        profile_name=profile_name,
                        account_name=name or profile_name,
                        email=email,
                        aliases=tuple(dict.fromkeys(filter(None, aliases))),
                        primary=is_primary,
                    )
                )
            if not primary_added:
                aliases = _account_aliases(primary_name, primary_email)
                aliases = (*aliases, profile_name, profile_directory)
                accounts.append(
                    ChromeAccount(
                        profile_directory=profile_directory,
                        profile_name=profile_name,
                        account_name=primary_name,
                        email=primary_email,
                        aliases=tuple(dict.fromkeys(filter(None, aliases))),
                        primary=True,
                    )
                )
        return _deduplicate_accounts(accounts)

    def _preference_accounts(self, profile_directory: str) -> list[dict[str, Any]]:
        preferences = _read_json(
            self.user_data_dir / profile_directory / "Preferences"
        )
        values = preferences.get("account_info", []) if preferences else []
        return [item for item in values if isinstance(item, dict)]


def _account_aliases(name: str, email: str) -> tuple[str, ...]:
    local_part = email.partition("@")[0] if email else ""
    return tuple(dict.fromkeys(filter(None, (name, email, local_part))))


def _normalise_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _deduplicate_accounts(accounts: list[ChromeAccount]) -> list[ChromeAccount]:
    seen: set[tuple[str, str]] = set()
    result: list[ChromeAccount] = []
    for account in accounts:
        identity = (
            account.profile_directory.casefold(),
            (account.email or account.account_name).casefold(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(account)
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
