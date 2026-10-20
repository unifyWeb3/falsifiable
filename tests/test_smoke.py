"""Smoke test: the contract deploys, opens a market and takes a stake."""

from __future__ import annotations

from conftest import GEN, SIDE_YES, account, open_market


def test_market_lifecycle_smoke(direct_vm, deploy, clock):
    vm = direct_vm
    contract = deploy()

    assert contract.get_market_count() == 0

    market_id = open_market(contract, clock, close_in=600)
    assert market_id == 0
    assert contract.get_market_count() == 1

    market = contract.get_market(market_id)
    print("market:", market)
    assert market[2] == "https://example.com/"
    assert market[8] == 0  # OPEN

    alice = account("alice")
    vm.value = 5 * GEN
    with vm.prank(alice):
        contract.stake(market_id, SIDE_YES)
    vm.value = 0

    position = contract.get_position(market_id, alice.as_hex)
    print("position:", position)
    assert int(position[0]) == 5 * GEN
    assert int(contract.get_totals()[0]) == 5 * GEN
