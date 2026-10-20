"""Shared fixtures for the Falsifiable contract tests.

The local (direct) GenLayer runner executes the contract in-process, so the
contract's clock can be controlled by patching `time.time` — which is exactly
what the contract reads.  On a real network `time.time()` is pinned by
GenLayer to the transaction timestamp, which every validator shares.
"""

from __future__ import annotations

import time
from typing import Iterator

import pytest

CONTRACT = "contracts/falsifiable.py"

# Rule kinds (mirrors the contract's constants)
RULE_BODY_CONTAINS = 1
RULE_BODY_EQUALS = 2
RULE_TITLE_CONTAINS = 3
RULE_TITLE_EQUALS = 4
RULE_JSON_FIELD_CONTAINS = 5
RULE_JSON_FIELD_EQUALS = 6

SIDE_YES = 0
SIDE_NO = 1

STATUS_OPEN = 0
STATUS_CLOSED = 1
STATUS_RESOLVED_YES = 2
STATUS_RESOLVED_NO = 3
STATUS_RESOLVED_UNDETERMINED = 4
STATUS_RESOLVED_REFUNDED = 5

OUTCOME_NONE = 0
OUTCOME_YES = 1
OUTCOME_NO = 2
OUTCOME_UNDETERMINED = 3

MIN_STAKE = 1_000_000_000_000_000
RESOLUTION_WINDOW = 3600
GEN = 10**18


class Clock:
    """A controllable clock.  `now` is a unix timestamp in seconds."""

    def __init__(self, start: int | None = None) -> None:
        self.value = float(start if start is not None else int(time.time()))

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds

    def set(self, timestamp: int) -> None:
        self.value = float(timestamp)


BASE_TIME = 1_800_000_000


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Clock]:
    c = Clock(BASE_TIME)
    monkeypatch.setattr(time, "time", c)
    yield c


@pytest.fixture
def deploy(direct_deploy):
    def _deploy():
        return direct_deploy(CONTRACT)

    return _deploy


def open_market(
    contract,
    clock,
    *,
    url: str = "https://example.com/",
    claim: str = "the page will say hello",
    rule_kind: int = RULE_BODY_CONTAINS,
    rule_param: str = "hello",
    rule_path: str = "",
    close_in: int = 600,
):
    """Create a market and return its id."""
    return contract.create_market(
        url, claim, rule_kind, rule_param, rule_path, int(clock.value) + close_in
    )


def mock_page(vm, body: str, status: int = 200, url: str = r"https://example\.com/.*"):
    vm.mock_web(url, {"method": "GET", "status": status, "body": body})


def account(name: str):
    """A deterministic test address."""
    from gltest.direct.loader import create_address

    return create_address(name)
