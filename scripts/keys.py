"""Throwaway Studionet key management.

Generates a set of fresh testnet accounts, stores ONLY the secret material in a
chmod-600 file that is gitignored, and prints addresses only.

Secrets are never printed, never logged, never committed.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from eth_account import Account

REPO = Path(__file__).resolve().parent.parent
KEYFILE = REPO / "secrets" / "studionet_keys.json"

ACCOUNTS = ["deployer", "staker_a", "staker_b", "staker_c"]


def main() -> int:
    REPO.joinpath("secrets").mkdir(exist_ok=True)
    if KEYFILE.exists():
        print(f"keyfile already exists at {KEYFILE}; refusing to overwrite")
        return 1

    payload = {"accounts": {}}
    for name in ACCOUNTS:
        acct = Account.create()
        payload["accounts"][name] = {
            "address": acct.address,
            "private_key": acct.key.hex(),
        }
        # never print the key
        print(f"{name}: {acct.address}")

    KEYFILE.write_text(json.dumps(payload, indent=2))
    KEYFILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"wrote {KEYFILE} (mode {oct(stat.S_IMODE(os.stat(KEYFILE).st_mode))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
