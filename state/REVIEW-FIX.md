# Stage A — diagnosis (no changes yet)

Everything below is copied from the repository or from a live run. Nothing is
inferred. Where I could not test something, it says so.

## 1. Withdrawals

### Where a position is marked settled and a transfer is emitted

`contracts/falsifiable.py` (current `HEAD`), in `withdraw()`:

```
553:        # Checks before effects: settle the position *before* emitting the
554:        # transfer, so a second call (or a re-entrant one) finds nothing.
555:        position.settled_yes = u256(int(position.yes))
556:        position.settled_no = u256(int(position.no))
557:        market.settled_yes_stake = u256(int(market.settled_yes_stake) + remaining_yes)
558:        market.settled_no_stake = u256(int(market.settled_no_stake) + remaining_no)
559:
560:        if amount > 0:
561:            self.total_paid = u256(int(self.total_paid) + amount)
562:            gl.get_contract_at(gl.message.sender_address).emit_transfer(value=u256(amount))
```

That is the whole proof. Lines 555–559 consume the position (`settled_yes`
becomes `yes` and `settled_no` becomes `no`) and advance the market's
settled-stake counters. Line 561 records the amount as **paid**. Only then, on
line 562, is a message emitted. The function returns immediately afterwards and
never reads back whether the message was delivered. There is no later state that
can be reversed: a second `withdraw()` computes `remaining_yes == 0` and
`remaining_no == 0` (line 535–538) and refuses with `nothing to withdraw`.

So: **settlement and accounting happen before delivery is known, and are
irreversible.** The comment on 553–554 is true about re-entrancy and false about
delivery — it treats "emitted" as "paid".

### What the repository DECLARES as its target

| place | declared value |
|---|---|
| `README.md` (Studio section) | GenLayer Studio, `https://studio.genlayer.com/api/rpc` |
| `web/.env.example` | `NEXT_PUBLIC_STUDIONET_RPC=https://studio.genlayer.com/api/rpc` |
| `web/.env.example` | `NEXT_PUBLIC_FALSIFIABLE_CONTRACT=0xdf426A429a9C9Ed25f2FF208aA81190dB3874822` |
| `scripts/studio.py:17` | `from genlayer_py.chains import studionet` |
| `scripts/studio.py:23` | `https://studio.genlayer.com/api/rpc` |
| `state/LIVE-RESULTS.md:7-8` | chain id **61999**, GenVM **v0.2.16** |

The declared target is therefore **Studionet, chain 61999**, contract
`0xdf426A429a9C9Ed25f2FF208aA81190dB3874822`.

### What was observed on that declared target

`state/LIVE-RESULTS.md:132-153` and `:159-163`, from a real run:

* contract → EOA payout: the withdraw transaction reaches `FINALIZED /
  MAJORITY_AGREE`, but its triggered transaction ends `FINALIZED / NO_MAJORITY`
  with `Contract 0x… not found`.
* "The value is deducted from the contract and never delivered."
* observed failing payouts: `0x481d7e22…` (9 GEN), `0x427ed92a…` (12.5 GEN).

So on the declared target the payout did **not** work, and the contract still
settled the position and incremented `total_paid`.

### What I observed on the announced release-candidate network

**Important: this is a different network from the declared target.** The probe
below ran on chain **61997** (`studio-next.genlayer.com/api`, GenVM
`v0.3.0-rc7`), not on 61999. The repository does not currently declare 61997
anywhere.

Probe contract `probe_evm.py`, deployed at
`0xd9630E5008E50c3368e30E1632A1d6E375520004`, funded with 10 GEN:

| direction | method | main tx | triggered | result |
|---|---|---|---|---|
| EOA → contract | `deposit` 5 GEN | `0x02d37e47…` | — | contract 0 → 5 GEN ✓ |
| contract → contract | `gl.contract.get_at` | `0xf70ba9e9…` | `0xa50b55df…` | child `value_credited=true`, receiver 0 → 1 GEN ✓ |
| **contract → EOA** | `gl.contract.get_at(eoa).emit_transfer` | `0xea55119f…` | **none** | main `FINISHED_WITH_RETURN`; EOA 1200.000000 → 1200.000000 GEN; contract 10 → 10 GEN; state counter advanced to 3 GEN ✗ |
| **contract → EOA** | `@gl.evm.contract_interface … emit_transfer` | `0x5929e368…` | none | EOA **1200.000000 → 1203.000000 GEN**; contract 10 → 7 GEN ✓ |

Failure mode probe, contract `0xd9630E…` holding 1 GEN, EVM send of 5 GEN:

```
tx 0xab485582…  main FINISHED_WITH_ERROR
state rolled back: total_out 0, contract balance 1 GEN, EOA unchanged
stderr: … emit_transfer(value=amount) …
```

Two separate defects are now visible:

1. `gl.get_contract_at(...).emit_transfer` (the call the contract uses, lines
   562) **does not deliver to an EOA on either network**. On 61999 the child tx
   fails; on 61997 there is no child tx at all and even the contract's own
   balance is unchanged — a silent no-op.
2. Settlement and `total_paid` are written before the message is emitted, so
   defect 1 is invisible in the contract's own state.

## 2. CLI

### Every script and command, and where it gets its address and network

| entry point | network source | address source | writes? |
|---|---|---|---|
| `scripts/falsifiable.py markets` | `scripts/studio.py:23` `STUDIONET_RPC` | **none** — `client.read_contract("get_market_count")` at `:81` passes the method name where the SDK expects an address | read |
| `… show` | same | **none** — `client.read_contract("get_market", args=…)` at `:113` | read |
| `… create` | same | **deploys a new contract** at `:126-131`, then writes to that new address at `:132-144`, then `read_contract("get_market_count")` at `:146` with no address | **deploy + write** |
| `… stake` | same | `_contract_address()` → env `FALSIFIABLE_CONTRACT` (`:194-198`) | write |
| `… close` | same | same | write |
| `… resolve` | same | same | write |
| `… withdraw` | same | same | write |
| `… position` | same | same | read |
| `scripts/deploy.py` | `STUDIONET_RPC` via `studio.py` | deploys, prints the address at `:80`, **never persists it** | deploy |
| `scripts/live_run.py` | `studio.py` | hard-coded `CONTRACT = "0xdf42…"` at `:28` | writes |
| `scripts/live_single.py` | `studio.py` | hard-coded `CONTRACT = "0xdf42…"` at `:23` | writes |
| `scripts/probe_*_run.py` | `studio.py` | deploy their own throwaway contract | deploy |
| web board | `web/lib/chain.ts:30` `NEXT_PUBLIC_STUDIONET_RPC` | `web/lib/chain.ts:38` `NEXT_PUBLIC_FALSIFIABLE_CONTRACT` | read |

### Where the CLI and the board disagree

* **Different variable names for the same two facts.**
  Board: `NEXT_PUBLIC_STUDIONET_RPC`, `NEXT_PUBLIC_FALSIFIABLE_CONTRACT`.
  CLI: `STUDIONET_RPC`, `FALSIFIABLE_CONTRACT`.
  There is no file that both read. `README.md:275` exports only the CLI names;
  `README.md:264-273` tells the user to put the other names in `web/.env.local`.
* **`create` deploys.** `scripts/falsifiable.py:126-131` reads the contract
  source and calls `client.deploy_contract(...)` on every `create`. The market
  is then created on that brand-new contract (`:132-144`) — not on the contract
  the board reads. The new address is printed and lost.
* **Three reads pass no address at all.** `:81`, `:113`, `:146` call
  `read_contract` with the method name as the first positional argument. The
  pinned SDK signature is
  `read_contract(address, function_name, args=None, …)`, so these calls raise
  `TypeError` before reaching the network. The documented `markets` example in
  `README.md:277` is therefore broken today.
* **Stale hard-coded addresses.** `scripts/live_run.py:28`,
  `scripts/live_single.py:23`.
* **No fees.** Every write on chain 61997 requires a `FeesDistribution` and a
  quoted fee value. The pinned `genlayer_py` 0.16.3 has no fee support at all
  (`grep -rn fee .venv/…/genlayer_py` finds only EVM `maxFeePerGas`). The live
  check confirms the network rejects a fee-less write:
  `FeesDistributionMissing`.
* **Docs.** `README.md:277-283` lists `markets/create/stake/close/resolve/
  withdraw`; `markets` and `create` do not target the configured contract.
  `README.md:294` advertises `scripts/deploy.py` but nothing tells the user (or
  the board) the new address afterwards. `web/app/open/page.tsx:8` and
  `web/components/ActionPanel.tsx:23` print `python3 scripts/falsifiable.py …`
  commands from the same list.

## Summary

| reviewer point | what is wrong | evidence |
|---|---|---|
| payout | settlement + `total_paid` precede delivery; the transfer route does not deliver to an EOA | `contracts/falsifiable.py:555-562`; live 61999 failures in `state/LIVE-RESULTS.md:136-153`; live 61997 silent no-op `0xea55119f…` |
| CLI | two config names, `create` deploys, three address-less reads, stale hard-coded addresses, no fees | table above; `scripts/falsifiable.py:81,113,126-146,194-198`; `scripts/live_run.py:28`; `scripts/live_single.py:23` |
