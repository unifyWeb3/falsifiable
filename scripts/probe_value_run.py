"""Run the value-transfer probe against the live Studio network.

Records observations only. Prints NO private keys.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

PROBE = Path(__file__).resolve().parent.parent / "contracts" / "probe_value.py"


def main() -> int:
    accounts = load_accounts()
    deployer = accounts["deployer"]
    recipient = accounts["staker_c"]

    client = client_for(deployer)
    code = PROBE.read_text()

    print("== deploying probe ==")
    deploy_tx = client.deploy_contract(code, account=deployer)
    print(f"deploy tx id: {deploy_tx}", flush=True)
    receipt = client.wait_for_transaction_receipt(deploy_tx, status=TransactionStatus.FINALIZED)
    print(f"deploy status: {receipt.get('status_name')}")
    addr = receipt.get("recipient")
    print(f"contract address: {addr}", flush=True)

    def bal(a: str) -> int:
        return int(client.w3.eth.get_balance(a))

    print("\n== balances before deposit ==")
    print(f"deployer: {bal(deployer.address)}")
    print(f"contract: {bal(addr)}")
    print(f"recipient: {bal(recipient.address)}")

    print("\n== deposit with 25 GEN attached ==")
    dep_tx = client.write_contract(addr, "deposit", account=deployer, value=25)
    print(f"deposit tx id: {dep_tx}", flush=True)
    r = client.wait_for_transaction_receipt(dep_tx, status=TransactionStatus.FINALIZED)
    print(f"deposit status: {r.get('status_name')}")
    time.sleep(2)

    total_in = client.read_contract(addr, "get_total_in")
    last_value = client.read_contract(addr, "get_last_value")
    self_bal = client.read_contract(addr, "get_self_balance")
    print(f"contract reports total_in={total_in}")
    print(f"contract reports last_value={last_value}")
    print(f"contract reports self_balance={self_bal}")
    print(f"on-chain contract balance: {bal(addr)}")
    print(f"deployer balance now: {bal(deployer.address)}")

    print("\n== payout 10 GEN to recipient ==")
    pre = bal(recipient.address)
    out_tx = client.write_contract(addr, "pay_out", account=deployer, args=[recipient.address, 10])
    print(f"payout tx id: {out_tx}", flush=True)
    r = client.wait_for_transaction_receipt(out_tx, status=TransactionStatus.FINALIZED)
    print(f"payout status: {r.get('status_name')}")
    time.sleep(4)
    post = bal(recipient.address)
    print(f"recipient balance before={pre} after={post} delta={post - pre}")
    print(f"contract on-chain balance now: {bal(addr)}")
    print(f"contract reports payouts={client.read_contract(addr, 'get_payouts')}")

    print("\n== RESULT ==")
    print(json.dumps({
        "contract_address": addr,
        "deploy_tx": deploy_tx,
        "deposit_tx": dep_tx,
        "deposit_value_seen_by_contract": int(last_value),
        "contract_self_balance_reported": int(self_bal),
        "contract_onchain_balance": bal(addr),
        "payout_tx": out_tx,
        "recipient_balance_delta": post - pre,
        "contract_payouts_reported": int(client.read_contract(addr, "get_payouts")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
