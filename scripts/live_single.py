"""The remaining live cases, on their own markets:

  4. a single-sided market that refunds
  5. a withdraw attempted twice — the second attempt must be refused

Run after `scripts/live_run.py`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chainconfig  # noqa: E402
from studio import client_for, get, load_accounts, wait as wait_tx, write  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

GEN = 10**18
CONTRACT = chainconfig.contract_address()
PAGE = "https://example.com/"
CLOSE_IN = 150
RULE_TITLE_CONTAINS = 3

OBSERVATIONS: dict = {}


def wait(client, tx_id: str, label: str) -> dict:
    print(f"  {label} tx id: {tx_id}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        tx_id, status=TransactionStatus.FINALIZED, retries=80, interval=3000
    )
    print(
        f"    -> {get(receipt, 'result_name')}/{get(receipt, 'result_name')}", flush=True
    )
    return receipt


def contract_error(client, tx_id: str) -> str | None:
    """A contract that raises still finalizes with MAJORITY_AGREE."""
    import base64

    receipt = client.get_transaction(tx_id)
    for entry in receipt.get("consensus_data", {}).get("leader_receipt", [])[:1]:
        if entry.get("execution_result") != "ERROR":
            continue
        raw = (entry.get("result") or {}).get("raw")
        if raw:
            return base64.b64decode(raw).decode("utf-8", "replace").strip()
        return "contract error"
    return None


def main() -> int:
    accounts = load_accounts()
    deployer = accounts["deployer"]
    client = client_for(deployer)

    def bal(address: str) -> int:
        return int(client.w3.eth.get_balance(address))

    def market(market_id: int) -> dict:
        raw = client.read_contract(CONTRACT, "get_market", args=[market_id])
        digest = raw[13]
        if isinstance(digest, (bytes, bytearray, memoryview)):
            digest = bytes(digest).hex()
        return {
            "id": market_id,
            "url": raw[2],
            "claim": raw[3],
            "rule_kind": raw[4],
            "rule_param": raw[5],
            "close_time": raw[7],
            "status": raw[8],
            "rule_outcome": raw[9],
            "pot_yes": raw[10],
            "pot_no": raw[11],
            "payout_pot": raw[12],
            "evidence_digest": digest,
        }

    def call(who: str, method: str, market_id: int) -> tuple[str | None, str | None]:
        """Call the contract.  A refusal is recorded, not raised."""
        account = accounts[who]
        try:
            tx = write(client, CONTRACT, method, account, args=[market_id])
        except Exception as err:  # noqa: BLE001
            print(f"  {method} m{market_id} REFUSED: {str(err)[:240]}", flush=True)
            return (None, str(err)[:240])
        print(f"  {method} m{market_id} tx id: {tx}", flush=True)
        receipt = wait_tx(client, tx, method, retries=80)
        print(
            f"    -> {get(receipt, 'result_name')}/{get(receipt, 'result_name')}",
            flush=True,
        )
        error = contract_error(client, tx)
        if error:
            print(f"    REFUSED BY THE CONTRACT: {error}", flush=True)
            return (tx, error)
        return (tx, None)

    def triggered(tx: str) -> list[dict]:
        import base64

        out = []
        for triggered_tx in client.get_transaction(tx).get("triggered_transactions") or []:
            info = client.get_transaction(triggered_tx)
            reason = None
            for entry in info.get("consensus_data", {}).get("leader_receipt", [])[:1]:
                raw = (entry.get("result") or {}).get("raw")
                if raw:
                    reason = base64.b64decode(raw).decode("utf-8", "replace").strip()
            out.append(
                {
                    "tx": triggered_tx,
                    "status": info.get("status_name"),
                    "result": info.get("result_name"),
                    "value": str(info.get("value")),
                    "recipient": info.get("recipient"),
                    "reason": reason,
                }
            )
        return out

    claim = "The Example Domain page's title will contain the words 'Example Domain'."
    close_at = int(time.time()) + CLOSE_IN

    print("== creating a single-sided market ==")
    count = int(client.read_contract(CONTRACT, "get_market_count"))
    market_id = None
    for index in range(count):
        info = market(index)
        if (
            info["claim"] == claim
            and info["status"] in (0, 1)
            and info["close_time"] > int(time.time()) + 60
        ):
            market_id = index
            print(f"  reusing market {index}")
            break
    if market_id is None:
        tx = client.write_contract(
            CONTRACT,
            "create_market",
            account=deployer,
            args=[PAGE, claim, RULE_TITLE_CONTAINS, "Example Domain", "", close_at],
        )
        wait(client, tx, "create_market")
        market_id = int(client.read_contract(CONTRACT, "get_market_count")) - 1
    print(f"  single-sided market id: {market_id}")
    OBSERVATIONS["single_sided_market_id"] = market_id

    print("\n== one side only ==")
    stake_tx = client.write_contract(
        CONTRACT,
        "stake",
        account=accounts["staker_c"],
        value=9 * GEN,
        args=[market_id, 0],
    )
    wait(client, stake_tx, "stake staker_c yes")
    OBSERVATIONS["stake_tx"] = stake_tx
    info = market(market_id)
    print(f"  pot_yes={info['pot_yes']} pot_no={info['pot_no']}")

    print("\n== waiting for the close time ==")
    wait_until = info["close_time"] + 25
    while int(time.time()) < wait_until:
        print(f"  {wait_until - int(time.time())}s to go", flush=True)
        time.sleep(15)

    print("\n== closing and resolving ==")
    close_tx, _ = call("staker_a", "close_market", market_id)
    resolve_tx, _ = call("staker_a", "resolve", market_id)
    OBSERVATIONS["close_tx"] = close_tx
    OBSERVATIONS["resolve_tx"] = resolve_tx
    info = market(market_id)
    print(f"  {json.dumps(info, default=str)}")
    OBSERVATIONS["market_after"] = info

    print("\n== withdrawing ==")
    before = bal(accounts["staker_c"].address)
    first_tx, first_error = call("staker_c", "withdraw", market_id)
    time.sleep(4)
    after = bal(accounts["staker_c"].address)
    print(f"  balance {before} -> {after} (delta {after - before} wei)")
    OBSERVATIONS["first_withdraw"] = {
        "tx": first_tx,
        "error": first_error,
        "balance_before": before,
        "balance_after": after,
        "delta": after - before,
    }

    print("\n== withdrawing a second time ==")
    before2 = bal(accounts["staker_c"].address)
    second_tx, second_error = call("staker_c", "withdraw", market_id)
    time.sleep(3)
    after2 = bal(accounts["staker_c"].address)
    print(f"  balance {before2} -> {after2} (delta {after2 - before2} wei)")
    OBSERVATIONS["second_withdraw"] = {
        "tx": second_tx,
        "error": second_error,
        "balance_before": before2,
        "balance_after": after2,
        "delta": after2 - before2,
    }
    print(
        f"  second withdraw refused: {second_tx is None}  ({second_error})",
        flush=True,
    )

    print("\n== somebody with nothing tries to withdraw ==")
    nobody_tx, nobody_error = call("staker_b", "withdraw", market_id)
    OBSERVATIONS["stranger_withdraw"] = {"tx": nobody_tx, "error": nobody_error}

    totals = client.read_contract(CONTRACT, "get_totals")
    OBSERVATIONS["totals"] = {"staked": str(totals[0]), "paid": str(totals[1])}
    print(f"\n== totals == staked {totals[0]}  paid {totals[1]}")
    if OBSERVATIONS["first_withdraw"]["tx"]:
        OBSERVATIONS["first_withdraw"]["triggered"] = triggered(
            OBSERVATIONS["first_withdraw"]["tx"]
        )
        print(
            "  triggered:",
            json.dumps(OBSERVATIONS["first_withdraw"]["triggered"], default=str),
        )

    print("\n== RESULT ==")
    print(json.dumps(OBSERVATIONS, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
