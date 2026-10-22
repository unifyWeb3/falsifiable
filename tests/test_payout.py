"""Payout delivery: the two-phase claim.

The contract must never treat "a message was emitted" as "the payee was paid".
`withdraw` requests a payout and records it as pending; `confirm_delivery` —
callable only by the payee — is the only thing that settles the position and
books the amount as paid.

Each refusal below is paired with a positive control: the same call, on the
same setup, succeeding under the conditions that should allow it.
"""

from __future__ import annotations

import pytest

from conftest import (
    GEN,
    OUTCOME_YES,
    RULE_BODY_CONTAINS,
    SIDE_NO,
    SIDE_YES,
    STATUS_RESOLVED_UNDETERMINED,
    STATUS_RESOLVED_YES,
    account,
    mock_page,
    open_market,
)

PAGE = "<html><body>the answer is yes</body></html>"


def _stake(vm, contract, market_id, who, side, amount):
    vm.value = amount
    with vm.prank(who):
        contract.stake(market_id, side)
    vm.value = 0


def _resolve(vm, contract, clock, market_id):
    mock_page(vm, PAGE)
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)


def _yes_market(vm, contract, clock, yes_amount=10 * GEN, no_amount=4 * GEN):
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, yes_amount)
    _stake(vm, contract, market_id, bob, SIDE_NO, no_amount)
    _resolve(vm, contract, clock, market_id)
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_YES
    return market_id, alice, bob


def test_payout_is_pending_not_settled_until_confirmed(direct_vm, deploy, clock):
    """A withdrawal whose delivery is not confirmed stays unsettled and unpaid."""
    vm = direct_vm
    contract = deploy()
    market_id, alice, _bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)

    position = contract.get_position(market_id, alice.as_hex)
    assert int(position[2]) == 0, "settled_yes moved before delivery was confirmed"
    assert int(position[3]) == 0, "settled_no moved before delivery was confirmed"
    assert int(contract.get_totals()[1]) == 0, "total_paid counted an unconfirmed payout"
    assert int(contract.get_pending(market_id, alice.as_hex)) == 14 * GEN
    assert int(contract.get_payout_preview(market_id, alice.as_hex)) == 0

    # Positive control: the same setup, with the acknowledgement, does settle.
    with vm.prank(alice):
        contract.confirm_delivery(market_id)
    position = contract.get_position(market_id, alice.as_hex)
    assert int(position[2]) == 10 * GEN
    assert int(contract.get_totals()[1]) == 14 * GEN
    assert int(contract.get_pending(market_id, alice.as_hex)) == 0


def test_delivered_payout_settles_exactly_once(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id, alice, _bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) == 0

    with vm.prank(alice):
        contract.confirm_delivery(market_id)
    assert int(contract.get_totals()[1]) == 14 * GEN

    with vm.prank(alice):
        with pytest.raises(Exception, match="no payout pending"):
            contract.confirm_delivery(market_id)
    assert int(contract.get_totals()[1]) == 14 * GEN, "a replay booked a second payment"


def test_second_claim_after_delivery_is_refused(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id, alice, _bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)
        contract.confirm_delivery(market_id)

    with vm.prank(alice):
        with pytest.raises(Exception, match="nothing to withdraw"):
            contract.withdraw(market_id)

    # Positive control: before delivery, the refusal is the *pending* one, not
    # a silent success and not "nothing to withdraw".
    other_market_id, carol, _dave = _yes_market(vm, contract, clock)
    with vm.prank(carol):
        contract.withdraw(other_market_id)
        with pytest.raises(Exception, match="payout pending"):
            contract.withdraw(other_market_id)


def test_pending_claim_cannot_be_claimed_twice(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id, alice, _bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)
        with pytest.raises(Exception, match="payout pending"):
            contract.withdraw(market_id)

    assert int(contract.get_totals()[1]) == 0
    assert int(contract.get_pending(market_id, alice.as_hex)) == 14 * GEN

    with vm.prank(alice):
        contract.confirm_delivery(market_id)
    assert int(contract.get_totals()[1]) == 14 * GEN


def test_only_the_payee_can_confirm_delivery(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id, alice, bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)

    with vm.prank(bob):
        with pytest.raises(Exception, match="no payout pending"):
            contract.confirm_delivery(market_id)
    assert int(contract.get_totals()[1]) == 0

    # Positive control: the payee can settle it.
    with vm.prank(alice):
        contract.confirm_delivery(market_id)
    assert int(contract.get_totals()[1]) == 14 * GEN


def test_total_paid_never_exceeds_total_staked(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    amounts = [3 * GEN + 1, 3 * GEN + 2, 3 * GEN + 3, 3 * GEN + 4]
    for index, amount in enumerate(amounts):
        _stake(
            vm,
            contract,
            market_id,
            account(f"w{index}"),
            SIDE_YES if index < 3 else SIDE_NO,
            amount,
        )
    _resolve(vm, contract, clock, market_id)

    for index in range(4):
        who = account(f"w{index}")
        with vm.prank(who):
            try:
                contract.withdraw(market_id)
                staked, paid = contract.get_totals()
                assert int(paid) <= int(staked)
                contract.confirm_delivery(market_id)
            except Exception:
                pass
        staked, paid = contract.get_totals()
        assert int(paid) <= int(staked), (index, int(paid), int(staked))

    staked, paid = contract.get_totals()
    assert int(paid) == int(staked), "the winners did not take the whole pot"


def test_refund_path_settles_once_per_account(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 5 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 7 * GEN)

    # No page is mocked, so every fetch fails and the rule is UNDETERMINED.
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_UNDETERMINED

    for who, amount in ((alice, 5 * GEN), (bob, 7 * GEN)):
        before = int(contract.get_totals()[1])
        with vm.prank(who):
            contract.withdraw(market_id)
            assert int(contract.get_totals()[1]) == before
            contract.confirm_delivery(market_id)
        assert int(contract.get_totals()[1]) == before + amount
        position = contract.get_position(market_id, who.as_hex)
        assert int(position[2]) + int(position[3]) == amount

    staked, paid = contract.get_totals()
    assert int(paid) == int(staked) == 12 * GEN


def test_ledger_moves_escrow_to_paid_only_on_confirmation(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id, alice, _bob = _yes_market(vm, contract, clock)

    with vm.prank(alice):
        contract.withdraw(market_id)

    staked, paid, escrowed, balance = contract.get_ledger()
    assert int(staked) == 14 * GEN
    assert int(paid) == 0
    assert int(escrowed) == 14 * GEN
    assert int(balance) >= 0
    assert int(paid) + int(escrowed) <= int(staked)

    with vm.prank(alice):
        contract.confirm_delivery(market_id)

    staked, paid, escrowed, balance = contract.get_ledger()
    assert int(paid) == 14 * GEN
    assert int(escrowed) == 0
    assert int(paid) + int(escrowed) <= int(staked)


def test_a_loser_still_gets_nothing(direct_vm, deploy, clock):
    """Positive control for the payout gate: the fix did not pay the losing side."""
    vm = direct_vm
    contract = deploy()
    market_id, _alice, bob = _yes_market(vm, contract, clock)

    with vm.prank(bob):
        with pytest.raises(Exception, match="nothing to withdraw"):
            contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) == 0
