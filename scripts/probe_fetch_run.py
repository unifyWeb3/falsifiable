"""Run probe #2 v2 (clock + web fetch + non-deterministic equivalence)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

PROBE = Path(__file__).resolve().parent.parent / "contracts" / "probe_fetch.py"
TEST_URL = "https://example.com/"
TIMEOUT = 110


def main() -> int:
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)
    code = PROBE.read_text()

    print("== deploying probe_fetch v2 ==", flush=True)
    deploy_tx = client.deploy_contract(code, account=deployer)
    print(f"deploy tx id: {deploy_tx}", flush=True)
    receipt = client.wait_for_transaction_receipt(deploy_tx, status=TransactionStatus.FINALIZED)
    addr = receipt.get("recipient")
    print(f"contract address: {addr}", flush=True)

    def call(method, **kwargs):
        tx = client.write_contract(addr, method, account=deployer, **kwargs)
        print(f"  {method} tx id: {tx}", flush=True)
        try:
            r = client.wait_for_transaction_receipt(
                tx, status=TransactionStatus.FINALIZED, retries=40, interval=3000
            )
            print(f"  {method} -> {r.get('status_name')}/{r.get('result_name')}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {method} -> NOT FINALIZED: {str(exc)[:200]}", flush=True)
        time.sleep(1.5)

    print("\n== A. clock ==", flush=True)
    wall_before = int(time.time())
    call("probe_clock")
    wall_after = int(time.time())
    clock = client.read_contract(addr, "get_clock")
    print(f"contract clock = {clock}  wall={wall_before}..{wall_after}")

    print("\n== E. positive control (no network) ==", flush=True)
    call("probe_control")
    print(f"control ok = {client.read_contract(addr, 'get_ctl')}")

    print("\n== B. plain web fetch (outside nondet block) ==", flush=True)
    call("probe_plain", args=[TEST_URL])
    print(f"plain result = {client.read_contract(addr, 'get_plain_err')!r}")

    print("\n== C. run_nondet_unsafe, both sides fetch ==", flush=True)
    call("probe_nondet", args=[TEST_URL])
    nd = client.read_contract(addr, "get_nd")
    print(f"nondet_unsafe -> ok={nd[0]} status={nd[1]} len={nd[2]} digest={bytes(nd[3]).hex()}")

    print("\n== D. run_nondet (sandboxed validator) ==", flush=True)
    call("probe_sandbox", args=[TEST_URL])
    sb = client.read_contract(addr, "get_sb")
    print(f"sandbox -> ok={sb[0]} status={sb[1]} len={sb[2]} digest={bytes(sb[3]).hex()}")

    print("\n== RESULT ==")
    print(json.dumps({
        "contract_address": addr,
        "deploy_tx": deploy_tx,
        "clock": int(clock),
        "wall_before": wall_before,
        "wall_after": wall_after,
        "control_ok": bool(client.read_contract(addr, "get_ctl")),
        "plain": client.read_contract(addr, "get_plain_err"),
        "nd_ok": bool(nd[0]), "nd_status": int(nd[1]), "nd_len": int(nd[2]),
        "nd_digest": bytes(nd[3]).hex(),
        "sb_ok": bool(sb[0]), "sb_status": int(sb[1]), "sb_len": int(sb[2]),
        "sb_digest": bytes(sb[3]).hex(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
