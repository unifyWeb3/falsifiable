"""Shared helpers for talking to the configured GenLayer network.

There is exactly one configuration: `web/config/chain.json`, read through
`scripts/chainconfig.py`.  The network, the RPC and the contract address all
come from there — no command carries its own copy.

Two SDK generations are supported because the declared target (Studio Devnet,
chain 61997) requires the Consensus v0.6 fee envelope, which only the release
candidate SDK has.  `write` and `deploy` detect the capability instead of
guessing from the network name.
"""

from __future__ import annotations

import inspect
import json
import os
import socket
import time
from pathlib import Path

from eth_account import Account
from eth_account.signers.local import LocalAccount
from genlayer_py import create_client
from genlayer_py.provider.provider import GenLayerProvider
from genlayer_py.exceptions import GenLayerError

from chainconfig import load as load_config

REPO = Path(__file__).resolve().parent.parent
KEYFILE = REPO / "secrets" / "studionet_keys.json"

MAX_ATTEMPTS = 12
BACKOFF_S = 2.5

# Generous enough for a small write; unused budget is refunded at finalization.
FEE_OPTIONS = {
    "leaderTimeunitsAllocation": 100,
    "validatorTimeunitsAllocation": 200,
    "totalMessageFees": 0,
    "rotations": [1],
}


def _dns_warmup(host: str) -> None:
    """Force a DNS resolution, retrying, so transport errors are rarer."""
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
                if "failed:" not in msg and "invalid JSON" not in msg and "403" not in msg:
                    raise
                last = err
                if attempt == MAX_ATTEMPTS:
                    break
                _dns_warmup(_host())
                time.sleep(BACKOFF_S)
        assert last is not None
        raise last


def _host() -> str:
    from urllib.parse import urlparse

    return urlparse(load_config()["rpcUrl"]).hostname or "studio-dev.genlayer.com"


def chain_for(config: dict):
    """Return the SDK chain object matching the configured network."""
    name = config["network"]
    if name == "studionet":
        from genlayer_py.chains import studionet

        return studionet
    if name in ("studio-dev", "studio-devnet"):
        try:
            from genlayer_py.chains import studio_devnet
        except ImportError as exc:  # pragma: no cover - depends on the venv
            raise SystemExit(
                "this SDK cannot talk to Studio Devnet (chain 61997). Install the "
                "release-candidate toolchain documented in README "
                "(python -m venv .venv-rc && pip install -r requirements-rc.txt)."
            ) from exc
        return studio_devnet
    raise SystemExit(f"unsupported network {name!r} in web/config/chain.json")


def load_accounts() -> dict[str, LocalAccount]:
    if not KEYFILE.exists():
        raise SystemExit(f"missing {KEYFILE}; run scripts/keys.py first")
    payload = json.loads(KEYFILE.read_text())
    out: dict[str, LocalAccount] = {}
    for name, rec in payload["accounts"].items():
        out[name] = Account.from_key(rec["private_key"])
    return out


def client_for(account: LocalAccount | None = None):
    config = load_config()
    if account is None:
        # The release-candidate SDK requires a signer even for view calls.  A
        # fresh in-memory key is enough: reads are never signed and it holds
        # nothing.  It is never printed and never persisted.
        account = Account.create()
    client = create_client(
        chain=chain_for(config), endpoint=config["rpcUrl"], account=account
    )
    client.provider = ResilientProvider(config["rpcUrl"])
    client.w3.provider = client.provider
    return client


# -- SDK capability detection ------------------------------------------------


def _supports_fees(client) -> bool:
    try:
        params = inspect.signature(client.write_contract).parameters
    except (TypeError, ValueError):  # pragma: no cover
        return False
    return "fees" in params


def fee_options(client) -> dict | None:
    """The Consensus v0.6 fee envelope, or None on a pre-fee SDK."""
    if not _supports_fees(client):
        return None
    if not hasattr(client, "estimate_transaction_fees"):
        return None
    estimate = client.estimate_transaction_fees(FEE_OPTIONS)
    return {
        "distribution": estimate["distribution"],
        "feeValue": estimate["feeValue"],
    }


def write(client, address: str, function_name: str, account, args=None, value: int = 0):
    kwargs = {"account": account, "args": args or [], "value": value}
    fees = fee_options(client)
    if fees is not None:
        kwargs["fees"] = fees
    return client.write_contract(address, function_name, **kwargs)


def deploy(client, code: str, account):
    kwargs = {"account": account, "args": []}
    fees = fee_options(client)
    if fees is not None:
        kwargs["fees"] = fees
    return client.deploy_contract(code, **kwargs)


def wait(client, tx_id: str, label: str = "tx", retries: int = 100) -> dict:
    """Wait for finalization across both SDK generations."""
    print(f"  {label} tx id: {tx_id}", flush=True)
    params = inspect.signature(client.wait_for_transaction_receipt).parameters
    if "wait_until" in params:
        receipt = client.wait_for_transaction_receipt(
            tx_id, wait_until="finalized", retries=retries, interval=2000
        )
    else:
        from genlayer_py.types import TransactionStatus

        receipt = client.wait_for_transaction_receipt(
            tx_id, status=TransactionStatus.FINALIZED, retries=retries, interval=3000
        )
    print(
        f"  {label} -> {get(receipt, 'result_name')} / {get(receipt, 'txExecutionResultName')}",
        flush=True,
    )
    return receipt


def get(receipt, name: str):
    """Read a field from either a dict-shaped or an object-shaped receipt."""
    if isinstance(receipt, dict):
        return receipt.get(name)
    return getattr(receipt, name, None)


def address_of(receipt) -> str | None:
    return get(receipt, "recipient") or get(receipt, "to_address")
