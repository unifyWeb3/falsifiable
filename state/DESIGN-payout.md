# Stage B — payout design

## Requirement

1. The payout must reach an ordinary externally-owned account on the target the
   repository declares, verified live, not from docs.
2. A payment that was not delivered must never be irreversibly settled or
   accounted as paid.
3. Nobody may be paid twice, and total paid out must never exceed total staked.
4. Product rules and the closed-set resolution stay exactly as they are.

## Options considered

| option | what it is | live result | verdict |
|---|---|---|---|
| 1. Internal message to the caller | `gl.contract.get_at(eoa).emit_transfer(value=…)` (the call the contract uses today) | 61999: child tx `FINALIZED / NO_MAJORITY`, "Contract 0x… not found", value deducted. 61997: **no child tx at all**, EOA balance unchanged, contract balance unchanged — a silent no-op that still lets the caller's code continue | rejected |
| 2. Chain-level account object | `gl.chain.Account(eoa).emit_transfer(value=…)` | not a distinct mechanism: its source is `get_at(address).emit_transfer(value, on=on)`, i.e. option 1 | rejected (same code path) |
| 3. EVM external message | `@gl.evm.contract_interface` + `emit_transfer(value=…)`, which becomes an `EthSend` | 61997: EOA **1200.000000 → 1203.000000 GEN**, contract 10 → 7 GEN, tx `FINISHED_WITH_RETURN` | **chosen transport** |
| 4. Balance-delta verification | read `get_balance_of(recipient)` before/after and settle if it rose by the amount | works for reads, but a recipient can spend or receive unrelated funds, so it gives both false positives and false negatives | not used as the settlement test |
| 5. Per-claim fresh address | pay each claim to a fresh address | a user's EOA is a fixed address; not applicable | rejected |
| 6. Keep settling before emitting | current behaviour | settles a payout that was never delivered | rejected |

## Chosen mechanism

**EVM external message for transport + a second-phase acknowledgement for
settlement.**

New state on each `Position`: `pending` (u256).
New contract state: `total_escrowed` (u256). `total_paid` is now strictly
"payments the payee has acknowledged".

### `withdraw(market_id)` — request

* Refuses if the market is not resolved, if there is no position, if the
  position has nothing left, or if `pending > 0` (`payout pending delivery
  confirmation`).
* Computes the entitlement exactly as before (same `_entitlement`, unchanged).
* Records `position.pending = amount` and `total_escrowed += amount`.
* Emits `_Recipient(Address(sender)).emit_transfer(value=amount)`.
* **Does not touch** `settled_yes`, `settled_no`, `settled_*_stake`,
  `total_paid`.

### `confirm_delivery(market_id)` — settle

* Callable only by the position owner (`gl.message.sender_address` is the
  position key — a caller cannot settle somebody else's claim, and there is no
  beneficiary parameter).
* Refuses if `pending == 0`.
* Requires that the position's remaining stake is still the same as at request
  time (it cannot change after resolution, so this is a sanity check).
* Moves `pending → 0`, advances `settled_*` and `settled_*_stake`, moves the
  amount from `total_escrowed` to `total_paid`, and asserts
  `total_paid <= total_staked`.

### Why this meets requirements 1–3

1. Transport is the EVM route, verified live on 61997 with pinned blocks.
2. Settlement happens only in `confirm_delivery`, which only the payee can call,
   and only while a `pending` record exists. An emitted message alone never
   settles or accounts anything.
3. `withdraw` refuses while `pending > 0`, and `confirm_delivery` refuses when
   `pending == 0`, so a position settles exactly once. `total_paid` grows only
   in `confirm_delivery` and is bounded by `total_staked`.

### Failure modes and their defined outcome

| failure | outcome |
|---|---|
| delivery silently fails | `pending` stays set, position not settled, `total_paid` unchanged. The user can retry `confirm_delivery`, but the contract will not re-emit, because re-emitting could pay twice. |
| delivery succeeds, acknowledgement never sent | the user has the money; the position stays `pending`, so it can never be withdrawn again. `total_paid` under-reports until they confirm. No double payment is possible. |
| user claims "not received" after receiving | there is no path that pays on a claim of non-receipt. The only path is `confirm_delivery`, which settles without paying again. |
| contract balance does not match the ledger | `get_ledger()` exposes `(total_staked, total_paid, total_escrowed, balance)`. A payout that fails on the live network deducts value into the ghost contract, so the balance can be lower than `total_staked - total_paid - total_escrowed`; that is visible and is not hidden by the accounting. |
| reentrant claim | `pending` is written before the message is emitted, and `withdraw` refuses when `pending > 0`; `confirm_delivery` is idempotent-refusing. |
| replayed claim | `confirm_delivery` clears `pending`; the second call raises `no payout pending`. |
| insufficient contract balance | the EVM send reverts the whole transaction (verified: `0xab485582…`, `FINISHED_WITH_ERROR`, state rolled back, no `pending` recorded). |

### What this cannot guarantee

* If the live network's ghost contract accepts the value and then fails to
  credit the EOA, the value is deducted once and cannot be safely re-sent. The
  position stays `pending` for ever and the money is stuck. This is the
  documented external-message behaviour ("if the child transaction fails, the
  value is not automatically returned"). Studio does not model the ghost
  contract, so this case could not be produced there.
* A user who never calls `confirm_delivery` leaves the position pending. That is
  a bookkeeping gap, not a payment risk.
* The acknowledgement is the payee's assertion. The contract cannot
  independently prove that a value transfer arrived.

## Contract-surface changes

* `withdraw(market_id)` keeps its name and its refusal semantics.
* New `confirm_delivery(market_id)`.
* New views `get_pending(market_id, account)` and `get_ledger()`.
* `get_position`, `get_payout_preview`, `get_totals`, `get_market`,
  `get_market_count`, `get_status`, `get_now`, `get_contract_balance` keep
  their shapes.
* No new market, rule, side, outcome or resolution behaviour.
