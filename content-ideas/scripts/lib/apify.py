"""Apify backend client: run an actor synchronously and return dataset items.

Dependency-free (urllib), matching the skill's zero-install constraint. Used by
the per-platform fetchers (lib/apify_fetchers) with the APIFY_TOKEN credential.

`run-sync-get-dataset-items` runs an actor and returns its default dataset's
items in a single HTTP call (Apify hard-caps sync runs at ~300s). On any failure
we log to stderr and return [] so one bad platform never aborts the whole feed.
"""

import json
import sys
import time
import urllib.error
import urllib.request

APIFY_BASE = "https://api.apify.com"
TIMEOUT = 300          # Apify hard-caps run-sync at ~300s
MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _actor_path(actor_id):
    """Apify REST encodes the actor id as `owner~name`, not `owner/name`."""
    return actor_id.replace("/", "~")


def run_actor_sync(actor_id, run_input, token, *, base=APIFY_BASE, timeout=TIMEOUT):
    """Run an actor and return its dataset items as a list of dicts.

    POST /v2/acts/<owner~name>/run-sync-get-dataset-items?token=<token>, with the
    actor input as the JSON body. Retries on 429/transient errors; gives up
    immediately on other 4xx. Returns [] on any failure or non-list response.
    """
    if not token:
        sys.stderr.write("[apify] no token; skipping run\n")
        return []

    url = (
        f"{base}/v2/acts/{_actor_path(actor_id)}"
        f"/run-sync-get-dataset-items?token={urllib.request.quote(token, safe='')}"
    )
    body = json.dumps(run_input).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "content/1.0"}

    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
                if isinstance(parsed, list):
                    return parsed
                # Success returns a bare JSON array; an object is an error/status
                # payload (e.g. {"error": {...}}).
                sys.stderr.write(
                    f"[apify] {actor_id}: unexpected non-list response {str(parsed)[:200]}\n"
                )
                return []
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                sys.stderr.write(f"[apify] HTTP {e.code} for {actor_id}\n")
                return []
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt) if e.code == 429 else RETRY_DELAY
                time.sleep(delay)
        except (urllib.error.URLError, OSError, TimeoutError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return []
