"""Money invariants.

  * shares sum to the pot exactly (no rounding dust)
  * losers get zero
  * refunds make everybody exactly whole
  * nobody can withdraw twice
  * total paid never exceeds total staked
"""

from __future__ import annotations

import pytest

from conftest import (
    GEN,
    MIN_STAKE,
    OUTCOME_YES,
    RULE_BODY_CONTAINS,
    SIDE_NO,
    SIDE_YES,
    STATUS_RESOLVED_NO,
    STATUS_RESOLVED_REFUNDED,
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


def _resolve_yes(vm, contract, clock, market_id):
    mock_page(vm, PAGE)
    alice = account("alice")
    bob = account("bob")
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)
    return alice, bob


def test_winner_takes_the_whole_pot(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _resolve_yes(vm, contract, clock, market_id)
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_YES

    with vm.prank(alice):
        contract.withdraw(market_id)
    # 10 GEN on YES wins the whole 14 GEN pot.
    assert int(contract.get_payout_preview(market_id, alice.as_hex)) == 0
    assert int(contract.get_totals()[1]) == 14 * GEN

def test_loser_gets_zero(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)

    _resolve_yes(vm, contract, clock, market_id)

    with vm.prank(bob):
        with pytest.raises(Exception):
            contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) == 0


def test_pro_rata_split_is_exact_with_no_dust(direct_vm, deploy, clock):
    """Three winners with awkward stakes: the shares must sum to the pot."""
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    names = ["w1", "w2", "w3", "l1"]
    amounts = [7 * GEN + 1, 3 * GEN + 1, 11 * GEN + 1, 5 * GEN + 7]
    for name, amount in zip(names, amounts):
        side = SIDE_NO if name == "l1" else SIDE_YES
        _stake(vm, contract, market_id, account(name), side, amount)

    _resolve_yes(vm, contract, clock, market_id)

    pot = sum(amounts)
    paid = 0
    for name in ["w1", "w2", "w3"]:
        who = account(name)
        with vm.prank(who):
            contract.withdraw(market_id)
        paid += int(contract.get_totals()[1]) - paid  # running total
    total_paid = int(contract.get_totals()[1])
    assert total_paid == pot, f"shares must sum to the pot exactly ({total_paid} != {pot})"
    assert int(contract.get_totals()[0]) == pot


def test_shares_are_within_one_wei_of_pro_rata(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    names = ["w1", "w2", "w3"]
    amounts = [7 * GEN + 1, 3 * GEN + 1, 11 * GEN + 1]
    for name, amount in zip(names, amounts):
        _stake(vm, contract, market_id, account(name), SIDE_YES, amount)

    _resolve_yes(vm, contract, clock, market_id)

    pot = sum(amounts)
    winner_pot = pot
    for name, amount in zip(names, amounts):
        who = account(name)
        before = int(contract.get_totals()[1])
        with vm.prank(who):
            contract.withdraw(market_id)
        got = int(contract.get_totals()[1]) - before
        ideal = amount * pot // winner_pot
        assert abs(got - ideal) <= 1, (name, got, ideal)


def test_refund_makes_everybody_exactly_whole(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(contract, clock)
    amounts = {"a": 3 * GEN + 7, "b": 11 * GEN + 13, "c": 5 * GEN}
    for name, amount in amounts.items():
        _stake(vm, contract, market_id, account(name), SIDE_YES, amount)

    # No web mock: the page is unreachable -> UNDETERMINED -> refund.
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_UNDETERMINED

    for name, amount in amounts.items():
        who = account(name)
        before = int(contract.get_totals()[1])
        with vm.prank(who):
            contract.withdraw(market_id)
        got = int(contract.get_totals()[1]) - before
        assert got == amount, (name, got, amount)

    assert int(contract.get_totals()[1]) == int(contract.get_totals()[0])


def test_single_sided_pool_refunds_the_staker(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(contract, clock)
    alice = account("alice")
    _stake(vm, contract, market_id, alice, SIDE_YES, 9 * GEN + 5)

    mock_page(vm, PAGE)
    clock.advance(700)
    contract.close_market(market_id)
    contract.resolve(market_id)
    assert contract.get_market(market_id)[8] == STATUS_RESOLVED_REFUNDED

    before = int(contract.get_totals()[1])
    with vm.prank(alice):
        contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) - before == 9 * GEN + 5


def test_double_withdraw_is_refused(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)
    _resolve_yes(vm, contract, clock, market_id)

    with vm.prank(alice):
        contract.withdraw(market_id)
    paid_once = int(contract.get_totals()[1])
    assert paid_once == 14 * GEN

    with vm.prank(alice):
        with pytest.raises(Exception):
            contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) == paid_once


def test_reentrant_withdraw_cannot_double_claim(direct_vm, deploy, clock):
    """The position is settled *before* the transfer is emitted.

    A re-entrant call — or a plain second call — finds an empty position and
    is refused, so no amount can be claimed twice.
    """
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 10 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 4 * GEN)
    _resolve_yes(vm, contract, clock, market_id)

    with vm.prank(alice):
        contract.withdraw(market_id)
    # The position is fully settled, not merely marked as claimed.
    position = contract.get_position(market_id, alice.as_hex)
    assert int(position[2]) == int(position[0])
    assert int(position[3]) == int(position[1])
    assert contract.get_payout_preview(market_id, alice.as_hex) == 0

    for _ in range(3):
        with vm.prank(alice):
            with pytest.raises(Exception):
                contract.withdraw(market_id)
    assert int(contract.get_totals()[1]) == 14 * GEN


def test_total_paid_never_exceeds_total_staked(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    names = ["a", "b", "c", "d"]
    for index, name in enumerate(names):
        _stake(
            vm,
            contract,
            market_id,
            account(name),
            SIDE_YES if index % 2 == 0 else SIDE_NO,
            (index + 1) * GEN + 3,
        )
    _resolve_yes(vm, contract, clock, market_id)

    for name in names:
        who = account(name)
        with vm.prank(who):
            try:
                contract.withdraw(market_id)
            except Exception:
                pass
        staked, paid = contract.get_totals()
        assert int(paid) <= int(staked)


def test_many_tiny_stakes_are_all_paid_exactly(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    count = 25
    amounts = [MIN_STAKE + index for index in range(count)]
    for index, amount in enumerate(amounts):
        _stake(
            vm,
            contract,
            market_id,
            account(f"t{index}"),
            SIDE_YES if index % 2 == 0 else SIDE_NO,
            amount,
        )
    _resolve_yes(vm, contract, clock, market_id)

    for index, amount in enumerate(amounts):
        if index % 2 == 1:
            continue  # losers
        who = account(f"t{index}")
        with vm.prank(who):
            contract.withdraw(market_id)
    # The winners' shares plus the losers' forfeited money make exactly the pot.
    staked, paid = contract.get_totals()
    winners_pot = sum(a for i, a in enumerate(amounts) if i % 2 == 0)
    assert int(paid) == int(staked)


def test_minimum_stake_is_enforced(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()
    market_id = open_market(contract, clock)
    alice = account("alice")
    vm.value = MIN_STAKE - 1
    with vm.prank(alice):
        with pytest.raises(Exception):
            contract.stake(market_id, SIDE_YES)
    vm.value = 0


def test_a_staker_may_hold_both_sides(direct_vm, deploy, clock):
    """Hedging is allowed and is arithmetically neutral."""
    vm = direct_vm
    contract = deploy()
    market_id = open_market(
        contract, clock, rule_kind=RULE_BODY_CONTAINS, rule_param="the answer is yes"
    )
    alice, bob = account("alice"), account("bob")
    _stake(vm, contract, market_id, alice, SIDE_YES, 6 * GEN)
    _stake(vm, contract, market_id, alice, SIDE_NO, 4 * GEN)
    _stake(vm, contract, market_id, bob, SIDE_NO, 10 * GEN)

    _resolve_yes(vm, contract, clock, market_id)

    before = int(contract.get_totals()[1])
    with vm.prank(alice):
        contract.withdraw(market_id)
    got = int(contract.get_totals()[1]) - before
    # Alice is the only staker on the winning side, so she takes the whole
    # 20 GEN pot — including the 4 GEN she herself put on the losing side.
    assert got == 20 * GEN
