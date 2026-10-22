# Live results — Studio Devnet (chain 61997)

Every number below came from the node.  "GEN" is simulated test money: there is
no market for it and no redemption.

**Network:** Studio Devnet, `https://studio-dev.genlayer.com/api`, chain id
**61997**, GenVM **v0.3.0-rc7**.  `https://studio-next.genlayer.com/api` is the
announced alias for the same deployment (same genesis, same block numbers); the
config uses the canonical name.

**Deployed contract:** `0xA62952F70354355d2915ee2aC66B91effcF3a6cB`

**Source identity**

| | sha256 |
|---|---|
| `contracts/falsifiable.py` | `a024fe206d11ae0a883c08348b02b664eb1e0b1032c5387413944e31a9cd2eda` |
| `gen_getContractCode` on the deployed address | `a024fe206d11ae0a883c08348b02b664eb1e0b1032c5387413944e31a9cd2eda` |

Byte-for-byte identical, 26995 bytes.  Deploy transaction
`0x4fcd703f69f92c7364f8ea692f988f74e678508b751df611d18ecfabf09cd64c`
→ `FINALIZED / MAJORITY_AGREE / FINISHED_WITH_RETURN`.

---

## Market 2 — two-sided, resolved YES, paid out

Rule: `BODY_CONTAINS "Example Domain"` over `https://example.com/`.

| step | transaction | result |
|---|---|---|
| create (staker_a) | `0x73d63e039b41966a0d79ad6d5925dd7f6a04171043dd94ec020535ea5d107e2d` | `MAJORITY_AGREE / FINISHED_WITH_RETURN`, market id 2 |
| stake YES 10 (staker_b) | `0xb8ebc6398a4056266fef250444c2e860b4080a5f0dcd48ed3f88d2e325f24f2a` | `FINISHED_WITH_RETURN` |
| stake NO 4 (staker_c) | `0x5a9ae47107ad6469844ceafd58cc13c0edc83b1f45b17f32fa51f0935096df7b` | `FINISHED_WITH_RETURN` |
| close | `0x125be69ce935ff310b495a76b90c27daa7f54bda7e020e9d8622fd0535895367` | `FINISHED_WITH_RETURN` |
| resolve | `0xa76bdf024ed3e27223f93d27fd1d483d5fa9267e1cd96e316db09549f19e41ff` | `FINISHED_WITH_RETURN`, outcome YES, pot 14 GEN |
| withdraw (staker_b) | `0x2d4128ecdc3c07be3236ba071295928afda27c8dcefbb5eb8534d5e315d24dc4` | `FINISHED_WITH_RETURN` |
| confirm-delivery (staker_b) | `0x54c97e08cb30b95da15bd925a8bf7ad655d61f32bcb7ef89bf32b7b12b731e4d` | `FINISHED_WITH_RETURN` |
| second withdraw (staker_b) | `0x190c0f633301404f7ff62579ec3c87e49b615e5c8fe8648b0a65e713cd6e8723` | **`FINISHED_WITH_ERROR` — refused** |
| loser withdraw (staker_c) | `0x08d604e56aa502930affe873cb42feb72d7c0d6f14f7baa247a8c02b7e425c47` | **`FINISHED_WITH_ERROR` — refused** |

Every transaction above has `recipient = 0xA62952F70354355d2915ee2aC66B91effcF3a6cB`.
`create` calls `create_market` on that address; it does not deploy anything.

### Balances at pinned blocks

| block | staker_b (payout EOA) | contract |
|---|---|---|
| `1792703127` before withdraw | `1000049323293749998357` wei | `14000000000000000000` wei |
| `1792703185` after withdraw | `1014049196988749997534` wei | `0` wei |
| `1792703258` after confirm | `1014049118358249996711` wei | `0` wei |

The EOA rose by **13.999873695 GEN** on the withdraw: the 14 GEN payout minus
the `0.000126305 GEN` fee for that transaction.  The confirmation cost a further
`0.000078631 GEN`; it moves no value.  The contract's own balance dropped by
exactly 14 GEN.

### Contract state around the payout

| | settled_yes | pending | total_paid | total_escrowed |
|---|---|---|---|---|
| before withdraw | 0 | 0 | 10 GEN | 0 |
| **after withdraw** | **0** | **14 GEN** | **10 GEN** | **14 GEN** |
| after confirm | 10 GEN | 0 | 24 GEN | 0 |

The withdrawal emitted the value and the position stayed **unsettled** and
**unpaid**; only `confirm_delivery` moved it.  `get_ledger()` reported
`total_paid + total_escrowed <= total_staked` at every step, and
`total_paid = total_staked = 24 GEN` after the last confirmation.

`triggered_transactions` is empty on the withdraw: on Studio the EVM external
message is applied synchronously in the same transaction, so there is no child
transaction to inspect.  The delivery is proven by the pinned EOA balance.

---

## Market 0 — one-sided pool, refunded

| step | transaction |
|---|---|
| create | `0x56fa0aad20da752cb583fad3d8f817ad3a06dd84679fef3ef65e6640298e4d34` |
| stake YES 10 | `0x833f337d664c04ea4a7de80665f5540fe7ac1749dcdafed26431db2a2d2e8141` |
| withdraw | `0x6d9a2a3a1a82380d57dd326493c423f63f93d9fb81a6420620e2593eb7f37d22` |
| confirm-delivery | `0x2a2b10617f52cb11db779621fcf0429717c2273395338359c7ec747c2e2e77bc` |

The one-sided pool resolved `RESOLVED_REFUNDED`; the 10 GEN refund was emitted,
stayed pending, and was booked only on confirmation.  After this market the
ledger read `total_staked = total_paid = 10 GEN`, `total_escrowed = 0`.

---

## What is not proven here

* Studio applies the EVM send synchronously and does not model the chain-layer
  ghost contract.  A live-network ghost failure that deducts value without
  crediting the EOA cannot be reproduced here.  If it happened, the position
  would stay `pending` for ever and the value would be stuck; the contract
  deliberately does not re-emit, because re-emitting could pay twice.
* The acknowledgement is the payee's assertion.  The contract cannot
  independently prove that a value transfer arrived.
