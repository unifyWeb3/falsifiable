"""Falsifiable — command line client for the Studio network.

The web app never holds a key, so every write is done here, with the key you
provide.  The key is read from the environment (`FALSIFIABLE_KEY`, a hex
private key) or from a file (`FALSIFIABLE_KEY_FILE`).  It is never printed,
never logged and never written to disk by this program.

    export FALSIFIABLE_KEY=0x...
    python3 scripts/falsifiable.py markets
    python3 scripts/falsifiable.py create --url https://example.com/ \
        --claim "the page will say hello" --rule BODY_CONTAINS --param hello \
        --close-in 3600
    python3 scripts/falsifiable.py stake --market 0 --side yes --amount 10
    python3 scripts/falsifiable.py close --market 0
    python3 scripts/falsifiable.py resolve --market 0
    python3 scripts/falsifiable.py withdraw --market 0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account  # noqa: E402
from eth_account.signers.local import LocalAccount  # noqa: E402

from studio import client_for  # noqa: E402

from genlayer_py.types import TransactionStatus  # noqa: E402

GEN = 10**18

RULES = {
    "BODY_CONTAINS": 1,
    "BODY_EQUALS": 2,
    "TITLE_CONTAINS": 3,
    "TITLE_EQUALS": 4,
    "JSON_FIELD_CONTAINS": 5,
    "JSON_FIELD_EQUALS": 6,
}


def load_key() -> LocalAccount:
    raw = os.environ.get("FALSIFIABLE_KEY")
    if raw:
        raw = raw.strip()
        if raw.startswith("0x"):
            raw = raw[2:]
        return Account.from_key(raw)
    path = os.environ.get("FALSIFIABLE_KEY_FILE")
    if path:
        return Account.from_key(Path(path).read_text().strip())
    raise SystemExit(
        "no key: set FALSIFIABLE_KEY (hex) or FALSIFIABLE_KEY_FILE (path to a file)"
    )


def to_wei(amount: str) -> int:
    return int(float(amount) * GEN)


def wait(client, tx_id: str, label: str) -> dict:
    print(f"  {label} tx id: {tx_id}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        tx_id, status=TransactionStatus.FINALIZED, retries=60, interval=3000
    )
    print(
        f"  {label} -> {receipt.get('status_name')}/{receipt.get('result_name')}",
        flush=True,
    )
    return receipt


def cmd_markets(args) -> int:
    client = client_for()
    count = int(client.read_contract("get_market_count"))
    print(f"markets: {count}")
    for market_id in range(count):
        market = client.read_contract("get_market", args=[market_id])
        print(json.dumps(_market_dict(market_id, market), default=str))
    return 0


def _market_dict(market_id: int, market) -> dict:
    digest = market[13]
    if isinstance(digest, (bytes, bytearray)):
        digest = digest.hex()
    return {
        "id": market_id,
        "creator": market[1],
        "url": market[2],
        "claim": market[3],
        "rule_kind": market[4],
        "rule_param": market[5],
        "rule_path": market[6],
        "close_time": market[7],
        "status": market[8],
        "rule_outcome": market[9],
        "pot_yes": market[10],
        "pot_no": market[11],
        "payout_pot": market[12],
        "evidence_digest": digest,
    }


def cmd_show(args) -> int:
    client = client_for()
    market = client.read_contract("get_market", args=[args.market])
    print(json.dumps(_market_dict(args.market, market), indent=2, default=str))
    return 0


def cmd_create(args) -> int:
    account = load_key()
    client = client_for(account)
    if args.rule not in RULES:
        raise SystemExit(f"unknown rule {args.rule}; pick one of {', '.join(RULES)}")
    kind = RULES[args.rule]
    if kind in (5, 6) and not args.path:
        raise SystemExit("this rule needs --path")
    code = (Path(__file__).resolve().parent.parent / "contracts" / "falsifiable.py").read_text()
    tx_id = client.deploy_contract(code, account=account)
    wait(client, tx_id, "deploy")
    receipt = client.get_transaction(tx_id)
    address = receipt.get("recipient")
    print(f"contract address: {address}")
    create_tx = client.write_contract(
        address,
        "create_market",
        account=account,
        args=[
            args.url,
            args.claim,
            kind,
            args.param,
            args.path or "",
            int(args.close_in) + int(__import__("time").time()),
        ],
    )
    wait(client, create_tx, "create_market")
    count = int(client.read_contract("get_market_count"))
    print(f"market id: {count - 1}")
    return 0


def cmd_stake(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _contract_address(client)
    side = 0 if args.side.lower() in ("yes", "y", "0") else 1
    tx_id = client.write_contract(
        address,
        "stake",
        account=account,
        value=to_wei(args.amount),
        args=[args.market, side],
    )
    wait(client, tx_id, "stake")
    return 0


def cmd_close(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _contract_address(client)
    tx_id = client.write_contract(address, "close_market", account=account, args=[args.market])
    wait(client, tx_id, "close_market")
    return 0


def cmd_resolve(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _contract_address(client)
    tx_id = client.write_contract(address, "resolve", account=account, args=[args.market])
    wait(client, tx_id, "resolve")
    return 0


def cmd_withdraw(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _contract_address(client)
    tx_id = client.write_contract(address, "withdraw", account=account, args=[args.market])
    wait(client, tx_id, "withdraw")
    return 0


def _contract_address(client) -> str:
    value = os.environ.get("FALSIFIABLE_CONTRACT")
    if not value:
        raise SystemExit("set FALSIFIABLE_CONTRACT to the deployed contract address")
    return value


def cmd_position(args) -> int:
    client = client_for()
    address = _contract_address(client)
    position = client.read_contract("get_position", args=[args.market, args.address])
    preview = client.read_contract("get_payout_preview", args=[args.market, args.address])
    print(
        json.dumps(
            {
                "yes": position[0],
                "no": position[1],
                "settled_yes": position[2],
                "settled_no": position[3],
                "payout_preview": preview,
            },
            indent=2,
            default=str,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="falsifiable", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("markets", help="list every market").set_defaults(func=cmd_markets)

    show = sub.add_parser("show", help="show one market")
    show.add_argument("--market", type=int, required=True)
    show.set_defaults(func=cmd_show)

    create = sub.add_parser("create", help="deploy the contract and open a market")
    create.add_argument("--url", required=True)
    create.add_argument("--claim", required=True)
    create.add_argument("--rule", required=True, choices=sorted(RULES))
    create.add_argument("--param", required=True)
    create.add_argument("--path", default="")
    create.add_argument("--close-in", type=int, default=3600)
    create.set_defaults(func=cmd_create)

    stake = sub.add_parser("stake", help="stake GEN on YES or NO")
    stake.add_argument("--market", type=int, required=True)
    stake.add_argument("--side", required=True, choices=["yes", "no"])
    stake.add_argument("--amount", required=True, help="amount of GEN")
    stake.set_defaults(func=cmd_stake)

    close = sub.add_parser("close", help="close a market that has passed its close time")
    close.add_argument("--market", type=int, required=True)
    close.set_defaults(func=cmd_close)

    resolve = sub.add_parser("resolve", help="rule on a market")
    resolve.add_argument("--market", type=int, required=True)
    resolve.set_defaults(func=cmd_resolve)

    withdraw = sub.add_parser("withdraw", help="withdraw your own position")
    withdraw.add_argument("--market", type=int, required=True)
    withdraw.set_defaults(func=cmd_withdraw)

    position = sub.add_parser("position", help="show an account's position")
    position.add_argument("--market", type=int, required=True)
    position.add_argument("--address", required=True)
    position.set_defaults(func=cmd_position)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
