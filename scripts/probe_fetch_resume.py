"""Continue probe #2 against an already-deployed probe_fetch contract."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

TEST_URL = "https://example.com/"


def main() -> int:
    addr = sys.argv[1]
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)

    def call(method, **kwargs):
        tx = client.write_contract(addr, method, account=deployer, **kwargs)
        print(f"  {method} tx id: {tx}", flush=True)
        r = client.wait_for_transaction_receipt(tx, status=TransactionStatus.FINALIZED)
        time.sleep(1.5)
        return r

    wall_before = int(time.time())
    clock = client.read_contract(addr, "get_clock")
    wall_after = int(time.time())
    print("== A. clock ==")
    print(f"contract clock = {clock}")
    print(f"wall before/after = {wall_before}/{wall_after}")
    print(f"delta_before={int(clock) - wall_before} delta_after={int(clock) - wall_after}")

    print("\n== B. plain web fetch ==")
    call("probe_plain", args=[TEST_URL])
    plain = client.read_contract(addr, "get_plain")
    print(f"plain -> ok={plain[0]} status={plain[1]} len={plain[2]} digest={plain[3].hex()[:32]}")

    print("\n== C. run_nondet_unsafe (validator fetches independently) ==")
    call("probe_nondet", args=[TEST_URL])
    nd = client.read_contract(addr, "get_nd")
    print(f"nondet_unsafe -> ok={nd[0]} status={nd[1]} len={nd[2]} digest={nd[3].hex()[:32]}")

    print("\n== D. run_nondet (sandboxed validator) ==")
    call("probe_sandbox", args=[TEST_URL])
    sb = client.read_contract(addr, "get_sb")
    print(f"sandbox -> ok={sb[0]} status={sb[1]} len={sb[2]} digest={sb[3].hex()[:32]}")

    print("\n== RESULT ==")
    print(json.dumps({
        "contract_address": addr,
        "clock": int(clock),
        "wall_before": wall_before,
        "wall_after": wall_after,
        "plain_ok": bool(plain[0]), "plain_status": int(plain[1]), "plain_len": int(plain[2]),
        "nd_ok": bool(nd[0]), "nd_status": int(nd[1]), "nd_len": int(nd[2]),
        "sb_ok": bool(sb[0]), "sb_status": int(sb[1]), "sb_len": int(sb[2]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
