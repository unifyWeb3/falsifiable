"""One config, one contract, for the board and for every CLI command.

No test here touches the network.  The point is the wiring: whatever address is
in `web/config/chain.json` is the address every command reads and writes, and a
broken or missing config stops the command instead of falling back to a default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pytest
from eth_account import Account

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import chainconfig  # noqa: E402
import falsifiable  # noqa: E402

ADDRESS_A = "0x1111111111111111111111111111111111111111"
ADDRESS_B = "0x2222222222222222222222222222222222222222"

CONFIG_KEYS = {
    "network": "studio-dev",
    "chainId": 61997,
    "rpcUrl": "https://studio-dev.genlayer.com/api",
    "contract": ADDRESS_A,
}

MARKET = (
    0,
    ADDRESS_A,
    "https://example.com/",
    "the page will say hello",
    1,
    "hello",
    "",
    1_800_000_600,
    0,
    0,
    10 * 10**18,
    4 * 10**18,
    0,
    b"\x00" * 32,
)


def write_config(tmp_path: Path, **overrides) -> Path:
    payload = dict(CONFIG_KEYS)
    payload.update(overrides)
    path = tmp_path / "chain.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def configured(monkeypatch, tmp_path):
    path = write_config(tmp_path)
    monkeypatch.setattr(chainconfig, "CONFIG_PATH", path)
    return path


class FakeClient:
    """Records every contract call and never reaches a network."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.count = 0

    def read_contract(self, address, function_name, args=None):
        self.calls.append(("read", address, function_name, list(args or [])))
        if function_name == "get_market_count":
            return self.count
        if function_name == "get_market":
            return MARKET
        if function_name == "get_position":
            return (1, 2, 3, 4)
        if function_name in ("get_payout_preview", "get_pending"):
            return 0
        if function_name == "get_ledger":
            return (0, 0, 0, 0)
        raise AssertionError(f"unexpected read {function_name}")

    def write_contract(self, address, function_name, account=None, args=None, value=0):
        self.calls.append(("write", address, function_name, list(args or []), value))
        if function_name == "create_market":
            self.count += 1
        return "0x" + "ab" * 32


@pytest.fixture
def fake(monkeypatch):
    client = FakeClient()

    def fake_write(client_arg, address, function_name, account, args=None, value=0):
        return client_arg.write_contract(
            address, function_name, account=account, args=args, value=value
        )

    monkeypatch.setattr(falsifiable, "client_for", lambda account=None: client)
    monkeypatch.setattr(falsifiable, "write", fake_write)
    monkeypatch.setattr(falsifiable, "wait", lambda *a, **k: {})
    return client


KEY_ENV = "FALSIFIABLE_KEY"


@pytest.fixture(autouse=True)
def a_key(monkeypatch):
    """A fresh, throwaway key so write commands can sign.  Never printed."""
    monkeypatch.setenv(KEY_ENV, Account.create().key.hex())


CASES = [
    (["markets"], "read", "get_market_count"),
    (["show", "--market", "0"], "read", "get_market"),
    (
        [
            "create",
            "--url",
            "https://example.com/",
            "--claim",
            "the page will say hello",
            "--rule",
            "BODY_CONTAINS",
            "--param",
            "hello",
            "--close-in",
            "600",
        ],
        "write",
        "create_market",
    ),
    (["stake", "--market", "0", "--side", "yes", "--amount", "1"], "write", "stake"),
    (["close", "--market", "0"], "write", "close_market"),
    (["resolve", "--market", "0"], "write", "resolve"),
    (["withdraw", "--market", "0"], "write", "withdraw"),
    (["confirm-delivery", "--market", "0"], "write", "confirm_delivery"),
    (["position", "--market", "0", "--address", ADDRESS_A], "read", "get_position"),
    (["ledger"], "read", "get_ledger"),
]


@pytest.mark.parametrize("argv,kind,method", CASES)
def test_every_command_uses_the_configured_contract(
    configured, fake, argv, kind, method
):
    parser = falsifiable.build_parser()
    args = parser.parse_args(argv)
    args.func(args)

    assert fake.calls, f"{argv[0]} made no contract call"
    assert [c[1] for c in fake.calls] == [ADDRESS_A] * len(fake.calls)
    assert any(c[0] == kind and c[2] == method for c in fake.calls), fake.calls


def test_a_different_config_means_a_different_contract(configured, fake):
    """Positive control: the address really comes from the file, not a default."""
    chainconfig.CONFIG_PATH.write_text(json.dumps({**CONFIG_KEYS, "contract": ADDRESS_B}))
    args = falsifiable.build_parser().parse_args(["markets"])
    args.func(args)
    assert [c[1] for c in fake.calls] == [ADDRESS_B] * len(fake.calls)


def test_create_never_deploys(configured, fake):
    args = falsifiable.build_parser().parse_args(
        [
            "create",
            "--url",
            "https://example.com/",
            "--claim",
            "the page will say hello",
            "--rule",
            "BODY_CONTAINS",
            "--param",
            "hello",
            "--close-in",
            "600",
        ]
    )
    args.func(args)
    assert not hasattr(fake, "deploy_contract"), "the fake was never asked to deploy"
    writes = [c for c in fake.calls if c[0] == "write"]
    assert [c[2] for c in writes] == ["create_market"]
    assert writes[0][1] == ADDRESS_A


def test_the_cli_has_no_deploy_command():
    parser = falsifiable.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["deploy"])


def test_missing_config_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(chainconfig, "CONFIG_PATH", tmp_path / "absent.json")
    with pytest.raises(SystemExit, match="web/config/chain.json"):
        chainconfig.load()


def test_malformed_config_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / "chain.json"
    path.write_text("{not json")
    monkeypatch.setattr(chainconfig, "CONFIG_PATH", path)
    with pytest.raises(SystemExit, match="not valid JSON"):
        chainconfig.load()


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"contract": ""}, "contract"),
        ({"contract": "0x1234"}, "contract"),
        ({"rpcUrl": "http://insecure.example/"}, "https"),
        ({"chainId": 0}, "chainId"),
        ({"network": ""}, "network"),
    ],
)
def test_bad_config_fails_closed(monkeypatch, tmp_path, overrides, message):
    path = write_config(tmp_path, **overrides)
    monkeypatch.setattr(chainconfig, "CONFIG_PATH", path)
    with pytest.raises(SystemExit, match=message):
        chainconfig.load()


def test_missing_key_fails_closed(configured, fake, monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    monkeypatch.delenv("FALSIFIABLE_KEY_FILE", raising=False)
    args = falsifiable.build_parser().parse_args(["withdraw", "--market", "0"])
    with pytest.raises(SystemExit, match="no key"):
        args.func(args)
    assert fake.calls == []
    # Positive control: with a key, the same command writes.
    monkeypatch.setenv(KEY_ENV, Account.create().key.hex())
    args.func(args)
    assert [c[2] for c in fake.calls] == ["withdraw"]


def test_web_and_cli_read_the_same_file():
    raw = json.loads((REPO / "web" / "config" / "chain.json").read_text())
    assert chainconfig.load() == raw
    assert chainconfig.contract_address() == raw["contract"]

    chain_ts = (REPO / "web" / "lib" / "chain.ts").read_text()
    assert 'from "../config/chain.json"' in chain_ts
    assert "NEXT_PUBLIC_STUDIONET_RPC" not in chain_ts
    assert "NEXT_PUBLIC_FALSIFIABLE_CONTRACT" not in chain_ts


def test_no_script_hard_codes_a_contract_address():
    pattern = re.compile(r"0x[0-9a-fA-F]{40}")
    offenders = []
    for path in sorted((REPO / "scripts").glob("*.py")):
        for match in pattern.finditer(path.read_text()):
            if match.group(0).lower() != "0x" + "0" * 40:
                offenders.append((path.name, match.group(0)))
    assert offenders == []


def test_readme_commands_exist():
    readme = (REPO / "README.md").read_text()
    documented = set(
        re.findall(r"python3 scripts/falsifiable\.py ([a-z][a-z-]*)", readme)
    )
    assert documented, "the README documents no CLI commands"
    parser = falsifiable.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert documented <= set(subparsers.choices), (
        documented - set(subparsers.choices)
    )
