# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Throwaway probe (NOT part of the product).

Question this answers, empirically, on the live GenLayer Studio network:
  1. Does a transaction with attached native value actually move GEN into a contract?
  2. Does `gl.message.value` report the attached value inside a payable method?
  3. Does the contract's own balance reflect the deposit?
  4. Can a contract pay value OUT to an arbitrary address (emit_transfer)?
  5. Does the recipient's on-chain balance actually go up?
"""

import genlayer.gl as gl
from genlayer.py.types import Address, u256


class Probe(gl.Contract):
    total_in: u256
    last_value: u256
    payouts: u256
    self_balance: u256

    def __init__(self) -> None:
        self.total_in = u256(0)
        self.last_value = u256(0)
        self.payouts = u256(0)
        self.self_balance = u256(0)

    @gl.public.write.payable
    def deposit(self) -> None:
        self.total_in = u256(int(self.total_in) + int(gl.message.value))
        self.last_value = u256(int(gl.message.value))
        self.self_balance = u256(int(self.balance))

    @gl.public.write
    def pay_out(self, to: Address, amount: u256) -> None:
        target = to if isinstance(to, Address) else Address(to)
        gl.get_contract_at(target).emit_transfer(value=u256(int(amount)))
        self.payouts = u256(int(self.payouts) + int(amount))

    @gl.public.view
    def get_total_in(self) -> u256:
        return self.total_in

    @gl.public.view
    def get_last_value(self) -> u256:
        return self.last_value

    @gl.public.view
    def get_payouts(self) -> u256:
        return self.payouts

    @gl.public.view
    def get_self_balance(self) -> u256:
        return u256(int(self.balance))
