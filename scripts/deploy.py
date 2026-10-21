"""Deploy the Falsifiable contract to the Studio network and prove that the
deployed source is byte-for-byte the repository file.

    python3 scripts/deploy.py

Prints the contract address and the two sha256 digests.  Never prints a key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts, RPC_URL  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

CONTRACT = Path(__file__).resolve().parent.parent / "contracts" / "falsifiable.py"
FUND_AMOUNT = 1000


def rpc(method: str, params: list) -> object:
    import requests

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    last: Exception | None = None
    for attempt in range(6):
        try:
            response = requests.post(RPC_URL, json=payload, timeout=60)
            response.raise_for_status()
            body = response.json()
            break
        except Exception as err:  # noqa: BLE001
            last = err
            time.sleep(2.0)
    else:
        raise RuntimeError(f"{method} failed: {last}")
    if "error" in body:
        raise RuntimeError(f"{method} failed: {body['error']}")
    return body["result"]


def fund(address: str) -> str:
    result = rpc("sim_fundAccount", [address, FUND_AMOUNT])
    return str(result)


def main() -> int:
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)

    print("== funding the throwaway accounts ==")
    for name, account in accounts.items():
        tx = fund(account.address)
        print(f"  {name}: {account.address} <- sim_fundAccount {FUND_AMOUNT} (tx {tx})")

    source = CONTRACT.read_bytes()
    local_sha = hashlib.sha256(source).hexdigest()
    print(f"\n== deploying {CONTRACT.name} ==")
    print(f"  repo sha256: {local_sha}")
    deploy_tx = client.deploy_contract(source.decode("utf-8"), account=deployer)
    print(f"  deploy tx id: {deploy_tx}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        deploy_tx, status=TransactionStatus.FINALIZED, retries=60, interval=3000
    )
    print(f"  deploy -> {receipt.get('status_name')}/{receipt.get('result_name')}")
    address = receipt.get("recipient")
    print(f"  contract address: {address}")

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

    print("\n== RESULT ==")
    print(
        json.dumps(
            {
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
