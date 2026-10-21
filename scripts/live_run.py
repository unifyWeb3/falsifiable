"""Run the live path against the deployed contract on the Studio network.

Five cases, all on the real network:
  1. a market that resolves YES
  2. a market that resolves NO
  3. a market that resolves UNDETERMINED, and refunds
  4. a single-sided market that refunds
  5. a withdraw attempted twice — the second attempt must be refused

Every transaction id is printed.  Nothing is faked: if a step does not
happen, it is reported as not happening.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio import client_for, load_accounts  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

GEN = 10**18
CONTRACT = "0xdf426A429a9C9Ed25f2FF208aA81190dB3874822"
PAGE = "https://example.com/"
MISSING = "https://example.com/falsifiable-this-path-does-not-exist"
CLOSE_IN = 300

RULE_BODY_CONTAINS = 1
RULE_TITLE_EQUALS = 4
RULE_TITLE_CONTAINS = 3

OBSERVATIONS: dict = {}


def wait(client, tx_id: str, label: str) -> dict:
    print(f"  {label} tx id: {tx_id}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        tx_id, status=TransactionStatus.FINALIZED, retries=80, interval=3000
    )
    print(
        f"    -> {receipt.get('status_name')}/{receipt.get('result_name')}", flush=True
    )
    error = contract_error(client, tx_id)
    if error:
        print(f"    !! CONTRACT ERROR: {error}", flush=True)
        raise SystemExit(f"{label} failed in the contract: {error}")
    return receipt


def contract_error(client, tx_id: str) -> str | None:
    """A contract that raises still finalizes with MAJORITY_AGREE.

    Look inside the leader receipt, otherwise a reverted call looks like a
    success.
    """
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

    def stake_tx(who: str, market_id: int, side: int, amount_gen: float) -> str:
        """Submit a stake.  Submission is cheap; finalising is not."""
        account = accounts[who]
        return client.write_contract(
            CONTRACT,
            "stake",
            account=account,
            value=int(amount_gen * GEN),
            args=[market_id, side],
        )

    def call(who: str, method: str, market_id: int) -> tuple[str | None, str | None]:
        """Call the contract.  A refusal is recorded, not raised."""
        account = accounts[who]
        try:
            tx = client.write_contract(CONTRACT, method, account=account, args=[market_id])
        except Exception as err:  # noqa: BLE001
            print(f"  {method} m{market_id} REFUSED: {str(err)[:200]}", flush=True)
            return (None, str(err)[:200])
        print(f"  {method} m{market_id} tx id: {tx}", flush=True)
        receipt = client.wait_for_transaction_receipt(
            tx, status=TransactionStatus.FINALIZED, retries=80, interval=3000
        )
        print(
            f"    -> {receipt.get('status_name')}/{receipt.get('result_name')}",
            flush=True,
        )
        error = contract_error(client, tx)
        if error:
            print(f"    REFUSED BY THE CONTRACT: {error}", flush=True)
            return (tx, error)
        return (tx, None)

    now = int(time.time())
    close_at = now + CLOSE_IN

    print("== creating four markets ==")
    specs = [
        (
            PAGE,
            "The Example Domain page will show the words 'Example Domain'.",
            RULE_BODY_CONTAINS,
            "Example Domain",
            "",
        ),
        (
            PAGE,
            "The Example Domain page's title will read 'Zorblax'.",
            RULE_TITLE_EQUALS,
            "Zorblax",
            "",
        ),
        (
            MISSING,
            "The page at this address will show a document.",
            RULE_BODY_CONTAINS,
            "document",
            "",
        ),
        (
            PAGE,
            "The Example Domain page's title will contain the words 'Example Domain'.",
            RULE_TITLE_CONTAINS,
            "Example Domain",
            "",
        ),
    ]
    # Always create fresh markets.  The contract gates on the transaction
    # timestamp, so a market that was created a moment ago may already be
    # past its close time; reusing one is a trap.
    pending = []
    for url, claim, kind, param, path in specs:
        tx = client.write_contract(
            CONTRACT,
            "create_market",
            account=deployer,
            args=[url, claim, kind, param, path, close_at],
        )
        pending.append(tx)
    create_txs = []
    for tx in pending:
        wait(client, tx, "create_market")
        create_txs.append(tx)

    count = int(client.read_contract(CONTRACT, "get_market_count"))
    print(f"  market count: {count}")
    base = count - len(pending)
    m_yes, m_no, m_undet, m_single = base, base + 1, base + 2, base + 3
    OBSERVATIONS["market_ids"] = {
        "yes": m_yes,
        "no": m_no,
        "undetermined": m_undet,
        "single_sided": m_single,
    }

    print("\n== staking ==")
    plan = [
        ("staker_a", m_yes, 0, 10),
        ("staker_b", m_yes, 1, 4),
        ("staker_c", m_yes, 0, 6),
        ("staker_a", m_no, 0, 5),
        ("staker_b", m_no, 1, 7),
        ("staker_a", m_undet, 0, 3),
        ("staker_b", m_undet, 1, 2),
        ("staker_c", m_single, 0, 9),
    ]
    stake_txs = []
    for who, market_id, side, amount in plan:
        stake_txs.append((who, market_id, side, amount, stake_tx(who, market_id, side, amount)))
    for who, market_id, side, amount, tx in stake_txs:
        wait(client, tx, f"stake {who} {'yes' if side == 0 else 'no'} m{market_id}")
    OBSERVATIONS["stake_txs"] = [t[4] for t in stake_txs]

    print("\n== waiting for the close time ==")
    wait_until = max(market(m)[ "close_time"] for m in (m_yes, m_no, m_undet, m_single)) + 25
    while int(time.time()) < wait_until:
        remaining = wait_until - int(time.time())
        print(f"  {remaining}s to go", flush=True)
        time.sleep(15)

    print("\n== closing and resolving ==")
    resolve_txs = {}
    for label, market_id in (
        ("yes", m_yes),
        ("no", m_no),
        ("undetermined", m_undet),
        ("single_sided", m_single),
    ):
        close_tx, _ = call("staker_a", "close_market", market_id)
        resolve_tx, _ = call("staker_a", "resolve", market_id)
        resolve_txs[label] = {"close": close_tx, "resolve": resolve_tx}
    OBSERVATIONS["resolve_txs"] = resolve_txs

    print("\n== the markets now ==")
    for label, market_id in (
        ("yes", m_yes),
        ("no", m_no),
        ("undetermined", m_undet),
        ("single_sided", m_single),
    ):
        info = market(market_id)
        print(f"  {label}: {json.dumps(info, default=str)}")
    OBSERVATIONS["markets_after"] = {
        label: market(market_id)
        for label, market_id in (
            ("yes", m_yes),
            ("no", m_no),
            ("undetermined", m_undet),
            ("single_sided", m_single),
        )
    }

    print("\n== withdrawing ==")
    withdraw_txs = {}
    for label, who, market_id in (
        ("yes_winner_a", "staker_a", m_yes),
        ("yes_winner_c", "staker_c", m_yes),
        ("no_winner_b", "staker_b", m_no),
        ("undetermined_a", "staker_a", m_undet),
        ("undetermined_b", "staker_b", m_undet),
        ("single_sided_c", "staker_c", m_single),
    ):
        before = bal(accounts[who].address)
        tx, error = call(who, "withdraw", market_id)
        time.sleep(3)
        after = bal(accounts[who].address)
        withdraw_txs[label] = {
            "tx": tx,
            "error": error,
            "balance_before": before,
            "balance_after": after,
            "delta": after - before,
        }
        print(
            f"  {label}: delta={after - before} wei ({(after - before) / GEN:.6f} GEN)"
        )
    OBSERVATIONS["withdrawals"] = withdraw_txs

    print("\n== the losing side tries to withdraw ==")
    loser_tx, loser_error = call("staker_b", "withdraw", m_yes)
    OBSERVATIONS["loser_withdraw"] = {"tx": loser_tx, "error": loser_error}
    print(f"  loser withdraw: tx={loser_tx} error={loser_error}")

    print("\n== the same account withdraws twice ==")
    first_tx, first_error = call("staker_a", "withdraw", m_yes)
    time.sleep(2)
    second_tx, second_error = call("staker_a", "withdraw", m_yes)
    OBSERVATIONS["double_withdraw"] = {
        "first": {"tx": first_tx, "error": first_error},
        "second": {"tx": second_tx, "error": second_error},
    }
    print(f"  first:  tx={first_tx} error={first_error}")
    print(f"  second: tx={second_tx} error={second_error}")

    print("\n== totals ==")
    totals = client.read_contract(CONTRACT, "get_totals")
    print(f"  total staked: {totals[0]}  total paid: {totals[1]}")
    OBSERVATIONS["totals"] = {"staked": str(totals[0]), "paid": str(totals[1])}

    print("\n== RESULT ==")
    print(json.dumps(OBSERVATIONS, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
