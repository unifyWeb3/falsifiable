"""Shared helpers for talking to the GenLayer Studio network (Studionet).

The Studio endpoint is reachable but its DNS/connect path is intermittently
flaky from this sandbox, so every RPC call is wrapped in a short retry.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from eth_account import Account
from eth_account.signers.local import LocalAccount
from genlayer_py import create_client
from genlayer_py.chains import studionet
from genlayer_py.provider.provider import GenLayerProvider
from genlayer_py.exceptions import GenLayerError

REPO = Path(__file__).resolve().parent.parent
KEYFILE = REPO / "secrets" / "studionet_keys.json"
RPC_URL = os.environ.get("STUDIONET_RPC", "https://studio.genlayer.com/api/rpc")

MAX_ATTEMPTS = 12
BACKOFF_S = 2.5


def _dns_warmup(host: str) -> None:
    """Force a DNS resolution, retrying, so transport errors are rarer."""
    import socket

    for _ in range(6):
        try:
            socket.getaddrinfo(host, 443, socket.AF_INET)
            return
        except OSError:
            time.sleep(1.0)


class ResilientProvider(GenLayerProvider):
    """GenLayerProvider with bounded retries on transport-level failures."""

    def make_request(self, method, params):  # type: ignore[override]
        last: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return super().make_request(method, params)
            except GenLayerError as err:
                msg = str(err)
                # Only retry transport failures, never JSON-RPC level errors.
                if "failed:" not in msg and "invalid JSON" not in msg:
                    raise
                last = err
                if attempt == MAX_ATTEMPTS:
                    break
                _dns_warmup("studio.genlayer.com")
                time.sleep(BACKOFF_S)
        assert last is not None
        raise last


def load_accounts() -> dict[str, LocalAccount]:
    if not KEYFILE.exists():
        raise SystemExit(f"missing {KEYFILE}; run scripts/keys.py first")
    payload = json.loads(KEYFILE.read_text())
    out: dict[str, LocalAccount] = {}
    for name, rec in payload["accounts"].items():
        out[name] = Account.from_key(rec["private_key"])
    return out


def client_for(account: LocalAccount | None = None):
    client = create_client(chain=studionet, endpoint=RPC_URL, account=account)
    client.provider = ResilientProvider(RPC_URL)
    client.w3.provider = client.provider
    return client
