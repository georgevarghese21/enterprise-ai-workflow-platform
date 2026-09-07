"""Embedding provider abstraction.

Mirrors the `LLM_MODE` pattern used for the (Phase 3+) LLM provider: the
default `mock` provider needs no external API and no ML dependencies, so
local dev, tests, and CI never make a network call. It's not random noise —
it's a deterministic hashing-trick bag-of-words vectorizer, so texts that
share vocabulary end up with genuinely similar vectors, which is enough for
meaningful nearest-neighbor retrieval during development. Swap in a real
provider (OpenAI/local sentence-transformers) in a later phase by adding a
branch to `get_embedding_provider`.
"""

import hashlib
import math
import re
from typing import Protocol

from app.core.config import get_settings

EMBEDDING_DIMENSIONS = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class MockHashingEmbeddingProvider:
    """Deterministic feature-hashing embedding requiring no external calls."""

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockHashingEmbeddingProvider()
    raise NotImplementedError(
        f"Embedding provider {settings.embedding_provider!r} is not implemented yet; "
        "only 'mock' is available until a later phase adds a real provider."
    )
