"""Falsifiable — command line client for the configured contract.

The web app never holds a key, so every write is done here, with the key you
provide.  The key is read from the environment (`FALSIFIABLE_KEY`, a hex
private key) or from a file (`FALSIFIABLE_KEY_FILE`).  It is never printed,
never logged and never written to disk by this program.

The network and the contract address come from one file,
`web/config/chain.json`, which the web board reads too.  No command here
deploys a contract; deployment is `scripts/deploy.py` and nothing else.

    export FALSIFIABLE_KEY=0x...
    python3 scripts/falsifiable.py markets
    python3 scripts/falsifiable.py create --url https://example.com/ \
        --claim "the page will say hello" --rule BODY_CONTAINS --param hello \
        --close-in 3600
    python3 scripts/falsifiable.py stake --market 0 --side yes --amount 10
    python3 scripts/falsifiable.py close --market 0
    python3 scripts/falsifiable.py resolve --market 0
    python3 scripts/falsifiable.py withdraw --market 0
    python3 scripts/falsifiable.py confirm-delivery --market 0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account  # noqa: E402
from eth_account.signers.local import LocalAccount  # noqa: E402

import chainconfig  # noqa: E402
from studio import client_for, wait, write  # noqa: E402

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


def _say_where() -> str:
    """Print the one configured network/contract; return the address."""
    address = chainconfig.contract_address()
    print(f"# {chainconfig.describe()}", file=sys.stderr, flush=True)
    return address


def _market_dict(market_id: int, market) -> dict:
    digest = market[13]
    if isinstance(digest, memoryview):
        digest = bytes(digest).hex()
    elif isinstance(digest, (bytes, bytearray)):
        digest = bytes(digest).hex()
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


def cmd_markets(args) -> int:
    client = client_for()
    address = _say_where()
    count = int(client.read_contract(address, "get_market_count"))
    print(f"markets: {count}")
    for market_id in range(count):
        market = client.read_contract(address, "get_market", args=[market_id])
        print(json.dumps(_market_dict(market_id, market), default=str))
    return 0


def cmd_show(args) -> int:
    client = client_for()
    address = _say_where()
    market = client.read_contract(address, "get_market", args=[args.market])
    print(json.dumps(_market_dict(args.market, market), indent=2, default=str))
    return 0


def cmd_create(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    if args.rule not in RULES:
        raise SystemExit(f"unknown rule {args.rule}; pick one of {', '.join(RULES)}")
    kind = RULES[args.rule]
    if kind in (5, 6) and not args.path:
        raise SystemExit("this rule needs --path")
    before = int(client.read_contract(address, "get_market_count"))
    tx_id = write(
        client,
        address,
        "create_market",
        account,
        args=[
            args.url,
            args.claim,
            kind,
            args.param,
            args.path or "",
            int(args.close_in) + int(time.time()),
        ],
    )
    wait(client, tx_id, "create_market")
    after = int(client.read_contract(address, "get_market_count"))
    if after != before + 1:
        raise SystemExit(
            f"create_market did not create a market on {address} "
            f"(count {before} -> {after})"
        )
    print(f"market id: {after - 1}")
    return 0


def cmd_stake(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    side = 0 if args.side.lower() in ("yes", "y", "0") else 1
    tx_id = write(
        client,
        address,
        "stake",
        account,
        value=to_wei(args.amount),
        args=[args.market, side],
    )
    wait(client, tx_id, "stake")
    return 0


def cmd_close(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    tx_id = write(client, address, "close_market", account, args=[args.market])
    wait(client, tx_id, "close_market")
    return 0


def cmd_resolve(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    tx_id = write(client, address, "resolve", account, args=[args.market])
    wait(client, tx_id, "resolve")
    return 0


def cmd_withdraw(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    tx_id = write(client, address, "withdraw", account, args=[args.market])
    wait(client, tx_id, "withdraw")
    return 0


def cmd_confirm_delivery(args) -> int:
    account = load_key()
    client = client_for(account)
    address = _say_where()
    tx_id = write(client, address, "confirm_delivery", account, args=[args.market])
    wait(client, tx_id, "confirm_delivery")
    return 0


def cmd_ledger(args) -> int:
    client = client_for()
    address = _say_where()
    staked, paid, escrowed, balance = client.read_contract(address, "get_ledger")
    print(
        json.dumps(
            {
                "total_staked": int(staked),
                "total_paid": int(paid),
                "total_escrowed": int(escrowed),
                "contract_balance": int(balance),
            },
            indent=2,
        )
    )
    return 0


def cmd_position(args) -> int:
    client = client_for()
    address = _say_where()
    position = client.read_contract(
        address, "get_position", args=[args.market, args.address]
    )
    preview = client.read_contract(
        address, "get_payout_preview", args=[args.market, args.address]
    )
    pending = client.read_contract(
        address, "get_pending", args=[args.market, args.address]
    )
    print(
        json.dumps(
            {
                "yes": position[0],
                "no": position[1],
                "settled_yes": position[2],
                "settled_no": position[3],
                "payout_preview": preview,
                "pending": pending,
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

    create = sub.add_parser(
        "create", help="open a market on the configured contract"
    )
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

    withdraw = sub.add_parser(
        "withdraw", help="request your payout (does not settle it)"
    )
    withdraw.add_argument("--market", type=int, required=True)
    withdraw.set_defaults(func=cmd_withdraw)

    confirm = sub.add_parser(
        "confirm-delivery",
        help="acknowledge receipt; this is what settles the position",
    )
    confirm.add_argument("--market", type=int, required=True)
    confirm.set_defaults(func=cmd_confirm_delivery)

    ledger = sub.add_parser("ledger", help="show the contract's money ledger")
    ledger.set_defaults(func=cmd_ledger)

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
