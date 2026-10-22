"""Deploy the Falsifiable contract to the configured network.

This is the only deployment path in the repository.  It deploys the file at
`contracts/falsifiable.py`, proves that the deployed source is byte-for-byte
the repository file, and — only when asked with `--write-config` — updates
`web/config/chain.json` so that the board, every CLI command and the docs all
point at the new address.

    python3 scripts/deploy.py                    # deploy, prove, print
    python3 scripts/deploy.py --write-config     # ... and make it current

Prints the contract address and the sha256 digest.  Never prints a key.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chainconfig  # noqa: E402
from studio import address_of, client_for, deploy, load_accounts, wait  # noqa: E402

CONTRACT = Path(__file__).resolve().parent.parent / "contracts" / "falsifiable.py"
FUND_AMOUNT = 1000


def rpc(method: str, params: list) -> object:
    import requests

    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last: Exception | None = None
    for _ in range(6):
        try:
            response = requests.post(chainconfig.rpc_url(), json=payload, timeout=60)
            response.raise_for_status()
            body = response.json()
            break
        except Exception as err:  # noqa: BLE001
            last = err
            import time

            time.sleep(2.0)
    else:
        raise RuntimeError(f"{method} failed: {last}")
    if "error" in body:
        raise RuntimeError(f"{method} failed: {body['error']}")
    return body["result"]


def fund(address: str) -> str:
    """Best effort: Studio exposes sim_fundAccount; other networks do not."""
    try:
        return str(rpc("sim_fundAccount", [address, FUND_AMOUNT]))
    except Exception as err:  # noqa: BLE001
        return f"not funded ({err})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="update web/config/chain.json to point at the new contract",
    )
    args = parser.parse_args()

    print(f"# deploying to {chainconfig.describe()}")
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)

    print("== funding the throwaway accounts ==")
    for name, account in accounts.items():
        print(f"  {name}: {account.address} <- {fund(account.address)}")

    source = CONTRACT.read_bytes()
    local_sha = hashlib.sha256(source).hexdigest()
    print(f"\n== deploying {CONTRACT.name} ==")
    print(f"  repo sha256: {local_sha}")
    deploy_tx = deploy(client, source.decode("utf-8"), deployer)
    print(f"  deploy tx id: {deploy_tx}", flush=True)
    receipt = wait(client, deploy_tx, "deploy")
    address = address_of(receipt)
    print(f"  contract address: {address}")
    if not address:
        raise SystemExit("the deploy receipt carried no contract address")

    print("\n== reading the deployed source back ==")
    encoded = rpc("gen_getContractCode", [address])
    deployed = base64.b64decode(encoded)
    deployed_sha = hashlib.sha256(deployed).hexdigest()
    print(f"  deployed sha256: {deployed_sha}")
    print(f"  repo sha256:     {local_sha}")
    identical = deployed == source
    print(f"  byte identical: {identical}")
    if not identical:
        print(f"  deployed length: {len(deployed)}  repo length: {len(source)}")
        raise SystemExit("the deployed source does not match the repository file")

    if args.write_config:
        config = chainconfig.load()
        config["contract"] = address
        chainconfig.CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
        print(f"\n== wrote {chainconfig.CONFIG_PATH} ==")
        print(f"  {chainconfig.describe()}")
    else:
        print("\n== config unchanged (pass --write-config to make it current) ==")

    print("\n== RESULT ==")
    print(
        json.dumps(
            {
                "network": chainconfig.network(),
                "chain_id": chainconfig.chain_id(),
                "contract_address": address,
                "deploy_tx": deploy_tx,
                "sha256": local_sha,
                "byte_identical": identical,
                "deployed_bytes": len(deployed),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
