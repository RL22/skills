"""Fetcher registries for the active backend.

The engine fetches creator data through Apify actors (lib/apify_fetchers). Each
registry maps a platform name to the relevant callable; capabilities a backend
doesn't implement are simply absent from that registry.
"""

from . import apify_fetchers


def registries_for(backend):
    """Return the four fetcher registries for a backend.

    Keys: 'profile', 'post', 'comment', 'transcript'. The Apify backend (v1)
    implements profile fetching only; its post/comment/transcript registries are
    empty so URL mode and top-N enrichment degrade cleanly to no-ops.
    """
    if backend == "apify":
        return {
            "profile": apify_fetchers.PROFILE_FETCHERS,
            "post": {},
            "comment": {},
            "transcript": {},
        }
    raise ValueError(f"Unknown backend: {backend!r}")
