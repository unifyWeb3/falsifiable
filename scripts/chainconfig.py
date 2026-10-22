"""The one source of truth for the network and the contract address.

`web/config/chain.json` is read by the web board (at build time) and by every
CLI command (at run time).  Nothing else may carry an address, and a missing or
malformed config is a hard error rather than a silent fallback.

    from chainconfig import load
    config = load()          # raises SystemExit with a clear message
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "web" / "config" / "chain.json"
DISPLAY = "web/config/chain.json"

REQUIRED = ("network", "chainId", "rpcUrl", "contract")


class ConfigError(SystemExit):
    """Raised when the shared config is missing or malformed."""


def load() -> dict:
    if not CONFIG_PATH.exists():
        raise ConfigError(
            f"missing {DISPLAY} ({CONFIG_PATH}). The board and the CLI both read that one "
            "file; create it (or run `python3 scripts/deploy.py --write-config`) "
            "before using any command."
        )
    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{DISPLAY} ({CONFIG_PATH}) is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{DISPLAY} must contain a JSON object")

    missing = [key for key in REQUIRED if key not in raw]
    if missing:
        raise ConfigError(
            f"{DISPLAY} is missing {', '.join(missing)}; all of "
            f"{', '.join(REQUIRED)} are required"
        )

    rpc = raw["rpcUrl"]
    if not isinstance(rpc, str) or not rpc.startswith("https://"):
        raise ConfigError(f"{DISPLAY}: rpcUrl must be an https url")

    contract = raw["contract"]
    if not isinstance(contract, str) or not _is_address(contract):
        raise ConfigError(f"{DISPLAY}: contract must be a 0x-prefixed 20-byte address")

    chain_id = raw["chainId"]
    if not isinstance(chain_id, int) or chain_id <= 0:
        raise ConfigError(f"{DISPLAY}: chainId must be a positive integer")

    if not isinstance(raw["network"], str) or not raw["network"]:
        raise ConfigError(f"{DISPLAY}: network must be a non-empty string")

    return raw


def _is_address(value: str) -> bool:
    if len(value) != 42 or not value.startswith("0x"):
        return False
    try:
        int(value[2:], 16)
    except ValueError:
        return False
    return True


def contract_address() -> str:
    return load()["contract"]


def rpc_url() -> str:
    return load()["rpcUrl"]


def network() -> str:
    return load()["network"]


def chain_id() -> int:
    return load()["chainId"]


def describe() -> str:
    config = load()
    return f"network={config['network']} chain={config['chainId']} contract={config['contract']}"
