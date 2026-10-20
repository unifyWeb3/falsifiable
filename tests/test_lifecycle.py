"""The full legitimate path: open -> stake -> close -> resolve -> withdraw.

Every resolution test pairs the "happy" case with the control that the
validators actually agree (the local runner executes the leader only, so the
captured validator is run explicitly — that is the consensus check).
"""

from __future__ import annotations

import hashlib

import pytest

from conftest import (
    GEN,
    OUTCOME_NO,
    OUTCOME_UNDETERMINED,
    OUTCOME_YES,
    RESOLUTION_WINDOW,
    RULE_BODY_CONTAINS,
    RULE_BODY_EQUALS,
    RULE_JSON_FIELD_CONTAINS,
    RULE_JSON_FIELD_EQUALS,
    RULE_TITLE_CONTAINS,
    RULE_TITLE_EQUALS,
    SIDE_NO,
    SIDE_YES,
    STATUS_CLOSED,
    STATUS_OPEN,
    STATUS_RESOLVED_NO,
    STATUS_RESOLVED_REFUNDED,
    STATUS_RESOLVED_UNDETERMINED,
    STATUS_RESOLVED_YES,
    account,
    mock_page,
    open_market,
)

PAGE = "<html><head><title>Quarterly report</title></head><body>Revenue up 12%</body></html>"


def _stake(vm, contract, market_id, who, side, amount):
    vm.value = amount
    with vm.prank(who):
        contract.stake(market_id, side)
    vm.value = 0


def _close_and_resolve(vm, contract, clock, market_id):
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)


def test_market_resolves_yes(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, PAGE)

    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="Revenue up 12%"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)

    # The validators agree with the leader.
    assert vm.run_validator() is True

    market = contract.get_market(market_id)
    assert market[8] == STATUS_RESOLVED_YES
    assert market[9] == OUTCOME_YES
    # The recorded digest is over the exact evidence bytes, and it is a value
    # every validator independently recomputed.
    assert market[13] == hashlib.sha256(PAGE.encode()).digest()


def test_market_resolves_no(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, PAGE)

    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="Revenue up 99%"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True

    market = contract.get_market(market_id)
    assert market[8] == STATUS_RESOLVED_NO
    assert market[9] == OUTCOME_NO


def test_market_resolves_undetermined_when_page_unreachable(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    # No web mock registered at all: the fetch raises.

    market_id = open_market(contract, clock)
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True

    market = contract.get_market(market_id)
    assert market[8] == STATUS_RESOLVED_UNDETERMINED
    assert market[9] == OUTCOME_UNDETERMINED
    assert market[12] == 0  # nothing to pay out


def test_market_resolves_undetermined_on_non_2xx(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, "Service Unavailable", status=503)

    market_id = open_market(contract, clock)
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_UNDETERMINED


def test_single_sided_pool_is_refunded(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, PAGE)

    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="Revenue up 12%"
    )
    alice = account("alice")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True

    market = contract.get_market(market_id)
    # The rule was decided (YES) but the pool was one-sided, so the money goes
    # back.  Both facts are visible.
    assert market[9] == OUTCOME_YES
    assert market[8] == STATUS_RESOLVED_REFUNDED
    assert market[12] == 0


def test_resolution_window_expires_into_a_deterministic_refund(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, PAGE)

    market_id = open_market(contract, clock)
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    clock.advance(700)
    contract.close_market(market_id)
    # Past the resolution window: the fallback must not touch the network.
    clock.advance(RESOLUTION_WINDOW + 1)
    contract.resolve(market_id)

    market = contract.get_market(market_id)
    assert market[8] == STATUS_RESOLVED_UNDETERMINED
    assert market[9] == OUTCOME_UNDETERMINED
    # No validator was even captured: the path is fully deterministic.
    with pytest.raises(RuntimeError):
        vm.run_validator()


def test_resolve_from_open_auto_closes(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, PAGE)

    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="Revenue up 12%"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    clock.advance(700)
    contract.resolve(market_id)
    assert vm.run_validator() is True
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_YES


@pytest.mark.parametrize(
    "kind,param,path,body,expected",
    [
        (RULE_BODY_CONTAINS, "Revenue up 12%", "", PAGE, OUTCOME_YES),
        (RULE_BODY_CONTAINS, "nothing like this", "", PAGE, OUTCOME_NO),
        (RULE_BODY_EQUALS, PAGE, "", PAGE, OUTCOME_YES),
        (RULE_BODY_EQUALS, "something else", "", PAGE, OUTCOME_NO),
        (RULE_TITLE_CONTAINS, "Quarterly report", "", PAGE, OUTCOME_YES),
        (RULE_TITLE_CONTAINS, "Annual report", "", PAGE, OUTCOME_NO),
        (RULE_TITLE_EQUALS, "Quarterly report", "", PAGE, OUTCOME_YES),
        (RULE_TITLE_EQUALS, "Quarterly report ", "", PAGE, OUTCOME_NO),
        (
            RULE_JSON_FIELD_CONTAINS,
            "acme",
            "company.name",
            '{"company": {"name": "acme"}}',
            OUTCOME_YES,
        ),
        (
            RULE_JSON_FIELD_CONTAINS,
            "globex",
            "company.name",
            '{"company": {"name": "acme"}}',
            OUTCOME_NO,
        ),
        (
            RULE_JSON_FIELD_EQUALS,
            "acme",
            "company.name",
            '{"company": {"name": "acme"}}',
            OUTCOME_YES,
        ),
        (
            RULE_JSON_FIELD_EQUALS,
            "acme",
            "company.name",
            '{"company": {"name": "acme corp"}}',
            OUTCOME_NO,
        ),
        (
            RULE_JSON_FIELD_CONTAINS,
            "second",
            "items.1",
            '{"items": ["first", "second"]}',
            OUTCOME_YES,
        ),
    ],
)
def test_every_rule_kind(direct_vm, deploy, clock, kind, param, path, body, expected):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, body)

    market_id = open_market(
        contract, clock, rule_kind=kind, rule_param=param, rule_path=path
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True
    assert contract.get_market(market_id)[9] == expected


def test_json_rule_on_a_non_json_page_is_undetermined(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    mock_page(vm, "<html>not json</html>")

    market_id = open_market(
        contract,
        clock,
        rule_kind=RULE_JSON_FIELD_EQUALS,
        rule_param="acme",
        rule_path="company.name",
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _close_and_resolve(vm, contract, clock, market_id)
    assert vm.run_validator() is True
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_UNDETERMINED
