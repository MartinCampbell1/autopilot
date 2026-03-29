"""Account manager for profile discovery, rotation, and cooldown handling."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from autopilot.core.adapters import get_adapter, list_provider_families
from autopilot.core.models import Profile


class AccountManager:
    """Manage CLI profiles across providers with round-robin rotation."""

    def __init__(self, profiles_dir: Path, cooldown_base: int = 300):
        self.profiles_dir = profiles_dir
        self.cooldown_base = cooldown_base
        self.pools: dict[str, list[Profile]] = {}
        self._indexes: dict[str, int] = {}

    def discover(self) -> None:
        """Scan profiles directory and populate provider pools."""
        self.pools.clear()
        self._indexes.clear()

        for provider in list_provider_families():
            adapter = get_adapter(provider)
            provider_dir = self.profiles_dir / provider
            if not provider_dir.exists():
                continue

            profiles: list[Profile] = []
            for account_dir in sorted(provider_dir.iterdir()):
                if not account_dir.is_dir() or not account_dir.name.startswith("acc"):
                    continue

                if not adapter.profile_is_valid(account_dir):
                    continue

                profiles.append(
                    Profile(
                        name=account_dir.name,
                        provider=provider,
                        adapter_id=adapter.adapter_id,
                        path=str(account_dir),
                    )
                )

            if profiles:
                self.pools[provider] = profiles
                self._indexes[provider] = 0

    def get_next(self, provider: str) -> Profile | None:
        """Get the next available profile using round-robin."""
        profiles = self.pools.get(provider, [])
        if not profiles:
            return None

        start_idx = self._indexes.get(provider, 0)

        for offset in range(len(profiles)):
            idx = (start_idx + offset) % len(profiles)
            profile = profiles[idx]
            profile.check_available()

            if profile.is_available:
                self._indexes[provider] = (idx + 1) % len(profiles)
                profile.last_used = time.time()
                profile.requests_made += 1
                return profile

        return None

    def mark_rate_limited(self, provider: str, profile_name: str) -> None:
        """Mark a specific profile as rate limited."""
        for profile in self.pools.get(provider, []):
            if profile.name == profile_name:
                profile.mark_rate_limited(self.cooldown_base)
                return

    def mark_success(self, provider: str, profile_name: str) -> None:
        """Reset error counters for a profile."""
        for profile in self.pools.get(provider, []):
            if profile.name == profile_name:
                profile.mark_success()
                return

    def pool_status(self, provider: str) -> list[dict]:
        """Return status info for all profiles in a provider pool."""
        now = time.time()
        return [
            {
                "name": profile.name,
                "available": profile.is_available or now >= profile.cooldown_until,
                "requests_made": profile.requests_made,
                "cooldown_remaining_sec": (
                    max(0, round(profile.cooldown_until - now))
                    if not profile.is_available and now < profile.cooldown_until
                    else 0
                ),
            }
            for profile in self.pools.get(provider, [])
        ]

    def save_profile(self, provider: str, source_dir: Path) -> str:
        """Copy a profile from source into the managed profiles directory."""
        provider_dir = self.profiles_dir / provider
        provider_dir.mkdir(parents=True, exist_ok=True)

        existing = sorted(
            account_dir.name
            for account_dir in provider_dir.iterdir()
            if account_dir.is_dir() and account_dir.name.startswith("acc")
        )
        name = f"acc{len(existing) + 1}"
        destination = provider_dir / name
        shutil.copytree(source_dir, destination)
        return name

    def build_env(self, profile: Profile) -> dict[str, str]:
        """Build environment variables for a CLI invocation using this profile."""
        env = os.environ.copy()
        adapter = get_adapter(profile.resolved_adapter_id)
        return adapter.build_env(profile, env)
