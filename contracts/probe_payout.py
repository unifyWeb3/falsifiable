# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Throwaway probe #3 (NOT part of the product).

Can a contract on the Studio network pay native GEN out?

  - to another CONTRACT  (the probe pays itself)
  - to an EOA           (the probe pays a plain account)

The money goes out as a posted message, so it lands in a later transaction.
"""

import genlayer.gl as gl
from genlayer.py.types import Address, u256


class ProbePayout(gl.Contract):
    balance_seen: u256
    received: u256

    def __init__(self) -> None:
        self.balance_seen = u256(0)
        self.received = u256(0)

    @gl.public.write.payable
    def deposit(self) -> None:
        self.balance_seen = u256(int(self.balance))
        self.received = u256(int(self.received) + int(gl.message.value))

    @gl.public.write
    def pay_self(self, amount: u256) -> None:
        gl.get_contract_at(gl.message.contract_address).emit_transfer(
            value=u256(int(amount))
        )

    @gl.public.write
    def pay_eoa(self, to: Address, amount: u256) -> None:
        target = to if isinstance(to, Address) else Address(to)
        gl.get_contract_at(target).emit_transfer(value=u256(int(amount)))

    @gl.public.write.payable
    def __receive__(self) -> None:
        self.balance_seen = u256(int(self.balance))
        self.received = u256(int(self.received) + int(gl.message.value))

    @gl.public.view
    def get_balance_seen(self) -> u256:
        return self.balance_seen

    @gl.public.view
    def get_received(self) -> u256:
        return self.received
