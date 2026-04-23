"""
API Key service.
In production: back this with Redis or Postgres.
Here: in-memory store seeded with demo keys.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class APIKey:
    key_id:      str
    key_hash:    str          # SHA-256 of the raw key — never store raw
    label:       str
    env:         str          # "live" | "test"
    owner:       str
    created_at:  float = field(default_factory=time.time)
    revoked:     bool  = False
    proofs_used: int   = 0
    monthly_limit: int = 50_000


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class APIKeyService:
    def __init__(self):
        # Seed two demo keys (raw values only shown at creation time)
        self._store: dict[str, APIKey] = {}
        self._seed_demo_keys()

    def _seed_demo_keys(self):
        for raw, label, env in [
            ("zk_live_k9mXpQ2nRtY7vLsJ3hWdFbAeUcN4o8_4a2f", "Production", "live"),
            ("zk_test_r3cVzT5wKnMjXpL8qYdBsGhFuAeN1o6_9c1b", "Test / dev",  "test"),
        ]:
            h = _hash(raw)
            self._store[h] = APIKey(
                key_id=raw[-8:],
                key_hash=h,
                label=label,
                env=env,
                owner="naveen@novusforge.dev",
            )

    # ------------------------------------------------------------------ #

    def validate(self, raw: str) -> Optional[APIKey]:
        """Return the APIKey if valid and not revoked, else None."""
        k = self._store.get(_hash(raw))
        if k and not k.revoked:
            k.proofs_used += 1
            return k
        return None

    def create(self, label: str, env: str, owner: str) -> tuple[str, APIKey]:
        """Returns (raw_key, APIKey). Show raw_key once — we never store it."""
        prefix = "zk_live_" if env == "live" else "zk_test_"
        raw    = prefix + secrets.token_urlsafe(28)
        h      = _hash(raw)
        key    = APIKey(key_id=raw[-8:], key_hash=h, label=label, env=env, owner=owner)
        self._store[h] = key
        return raw, key

    def revoke(self, raw: str) -> bool:
        k = self._store.get(_hash(raw))
        if k:
            k.revoked = True
            return True
        return False

    def list_for_owner(self, owner: str) -> list[APIKey]:
        return [k for k in self._store.values() if k.owner == owner]


api_key_service = APIKeyService()
