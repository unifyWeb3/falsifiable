"""Drive probe #3: can a contract pay native GEN out on Studionet?"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

PROBE = Path(__file__).resolve().parent.parent / "contracts" / "probe_payout.py"
GEN = 10**18


def main() -> int:
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)
    code = PROBE.read_text()

    print("== deploying probe_payout ==")
    deploy_tx = client.deploy_contract(code, account=deployer)
    print(f"  deploy tx id: {deploy_tx}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        deploy_tx, status=TransactionStatus.FINALIZED, retries=60, interval=3000
    )
    addr = receipt.get("recipient")
    print(f"  contract address: {addr}", flush=True)

    def call(method, **kwargs):
        tx = client.write_contract(addr, method, account=deployer, **kwargs)
        print(f"  {method} tx id: {tx}", flush=True)
        client.wait_for_transaction_receipt(
            tx, status=TransactionStatus.FINALIZED, retries=60, interval=3000
        )
        time.sleep(2)
        return tx

    def bal(a):
        return int(client.w3.eth.get_balance(a))

    print("\n== 1. an EOA sends 5 GEN into the contract ==")
    before = bal(addr)
    call("deposit", value=5 * GEN)
    time.sleep(2)
    after = bal(addr)
    print(f"  contract balance {before} -> {after} (delta {after - before})")
    print(f"  contract sees: {client.read_contract(addr, 'get_balance_seen')}")

    print("\n== 2. the contract pays 1 GEN to ITSELF ==")
    before = bal(addr)
    tx = call("pay_self", args=[1 * GEN])
    time.sleep(8)
    after = bal(addr)
    print(f"  contract balance {before} -> {after} (delta {after - before})")
    print(f"  received counter: {client.read_contract(addr, 'get_received')}")
    triggered = client.get_transaction(tx).get("triggered_transactions")
    print(f"  triggered transactions: {triggered}")
    for triggered_tx in triggered or []:
        info = client.get_transaction(triggered_tx)
        print(
            f"    {triggered_tx} -> {info.get('status_name')}/{info.get('result_name')}"
        )

    print("\n== 3. the contract pays 1 GEN to an EOA ==")
    eoa = accounts["staker_c"].address
    before_eoa = bal(eoa)
    tx = call("pay_eoa", args=[eoa, 1 * GEN])
    time.sleep(8)
    after_eoa = bal(eoa)
    print(f"  eoa balance {before_eoa} -> {after_eoa} (delta {after_eoa - before_eoa})")
    triggered = client.get_transaction(tx).get("triggered_transactions")
    print(f"  triggered transactions: {triggered}")
    for triggered_tx in triggered or []:
        info = client.get_transaction(triggered_tx)
        print(
            f"    {triggered_tx} -> {info.get('status_name')}/{info.get('result_name')}"
        )
        import base64

        for entry in info.get("consensus_data", {}).get("leader_receipt", [])[:1]:
            raw = (entry.get("result") or {}).get("raw")
            if raw:
                print(
                    "    reason:",
                    base64.b64decode(raw).decode("utf-8", "replace").strip(),
                )

    print("\n== RESULT ==")
    print(
        json.dumps(
            {
                "contract_address": addr,
                "deploy_tx": deploy_tx,
                "contract_balance": bal(addr),
                "eoa_balance": bal(eoa),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
