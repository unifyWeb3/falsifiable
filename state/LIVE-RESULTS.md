# Live results — GenLayer Studio network

Everything below was observed, not simulated.  "GEN" is simulated testnet
money: there is no market for it and no redemption.  Treat every amount as a
ratio, not as value.

**Network:** GenLayer Studio (`https://studio.genlayer.com/api/rpc`), chain id
61999, running **GenVM v0.2.16**.

**Deployed contract:** `0xdf426A429a9C9Ed25f2FF208aA81190dB3874822`

**Source identity**

| | sha256 |
|---|---|
| `contracts/falsifiable.py` in this repo | `a3291155911ecfd93d817ecb153aea266818f94a930760c32f9952b06bc94e8b` |
| `gen_getContractCode` on the deployed address | `a3291155911ecfd93d817ecb153aea266818f94a930760c32f9952b06bc94e8b` |

Byte-for-byte identical, 23262 bytes.  Deploy transaction
`0x43b139b4a3d89591ca21181c1a3aadf5f0fbd5eaca27fa89f1b5ea13b7b0681a`
→ `FINALIZED / MAJORITY_AGREE`.

---

## Case 1 — resolved YES (market 5)

Rule: `BODY_CONTAINS "Example Domain"` over `https://example.com/`.

| step | transaction | result |
|---|---|---|
| create | `0x9792ad8dee544c326a716534c4a1f6c060bff577d0a189aa7dcc337db1387d5f` | FINALIZED / MAJORITY_AGREE |
| stake YES 10 (staker_a) | `0x66707448bfd0b9f03a1bde4d01d7fbc4330f620d8776c5896ac59693adff1cef` | FINALIZED / MAJORITY_AGREE |
| stake NO 4 (staker_b) | `0x82fad9f3af1f195a75cb784c1d89a9af1e62aa1752e46d21959dc365fea4cb2f` | FINALIZED / MAJORITY_AGREE |
| stake YES 6 (staker_c) | `0xee97e22d7f0a445fae6227ffd2f0358f4e3c98dec975d8e9a25b27b42c0c1625` | FINALIZED / MAJORITY_AGREE |
| close | `0x7a8ac135e066a4bc55fdbacb2a573467218a1fd509f1c6a4feb0346f38031cdf` | FINALIZED / MAJORITY_AGREE |
| resolve | `0x2ff02dd950c17831901ef7e930c33c0d9daa68c2886eebfe44166ac45d67e45f` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_a) | `0x427ed92af1a8f51cbed314bc4ab8d8650244f80a61f7fe22df5404faad715fa2` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_c) | `0x9493d8b55cabe3d7aebfe31df9b471085dac949bbcc3a8069b6f6a664f4ee59f` | FINALIZED / MAJORITY_AGREE |
| withdraw by the loser (staker_b) | `0xf1815a8f0386b9ffb8bd1e19bd0179302e578a052859833ee136ac4a17a1ef6c` | **refused: "nothing to withdraw"** |

State afterwards: `status = RESOLVED_YES`, `rule_outcome = YES`,
`pot_yes = 16 GEN`, `pot_no = 4 GEN`, `payout_pot = 20 GEN`,
`evidence_digest = 25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484`.

That digest is the SHA-256 of `https://example.com/`'s body.  An independent
probe (`scripts/probe_fetch_run.py`) fetched the same page on the same
network and got the same digest — the leader and the validators were reading
the same bytes.

## Case 2 — resolved NO (market 6)

Rule: `TITLE_EQUALS "Zorblax"` over `https://example.com/`.

| step | transaction | result |
|---|---|---|
| create | `0x520edbb72fc95a8b5bd28dcbf1fc28a9005e6f0cbc8c683bcf1b526a3773b33c` | FINALIZED / MAJORITY_AGREE |
| stake YES 5 (staker_a) | `0xba39ed2df5d3c62523c39e8d03fb52a50e92325f40396c182af3243776ce1ca8` | FINALIZED / MAJORITY_AGREE |
| stake NO 7 (staker_b) | `0x78caa8f00125dceca28b80f3c7a2dcdbb3220b4aa54549ee31b4a68a463fe9fd` | FINALIZED / MAJORITY_AGREE |
| close | `0x1e7dd262747677904db07b5780d61ae16e5beae2c478e47f2e985949cd6257d3` | FINALIZED / MAJORITY_AGREE |
| resolve | `0xc14b6e18b324153a090b25df65dcdeddb6e69ab9d4d4c24eed28e5cdf44dc375` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_b) | `0xc88b454be4b3986ff8ee60e4ba483fd0eda506cd837f71874a1baed27ab60390` | FINALIZED / MAJORITY_AGREE |

State afterwards: `status = RESOLVED_NO`, `rule_outcome = NO`,
`pot_yes = 5 GEN`, `pot_no = 7 GEN`, `payout_pot = 12 GEN`,
`evidence_digest = 162b81548a8db0ab220f7137405fb003019c266883d4181869662ad7eafdbc4d`
(the SHA-256 of the title text `Example Domain`).

## Case 3 — resolved UNDETERMINED, refunded (market 7)

URL: `https://example.com/falsifiable-this-path-does-not-exist` (a 404).

| step | transaction | result |
|---|---|---|
| create | `0x0cb88d5d23ab4e18e1da03e4bda404e5b19bdc6b45762e12a6905d710dfc6203` | FINALIZED / MAJORITY_AGREE |
| stake YES 3 (staker_a) | `0x6b55df6a4bbe7f8a347501b501f42bd39c8601d0f3b544448750de706fdef62b` | FINALIZED / MAJORITY_AGREE |
| stake NO 2 (staker_b) | `0xdd5da9aa9bf9b3b3420d7c6203a8130635b55d6c2e46a99718d108ca6609d758` | FINALIZED / MAJORITY_AGREE |
| close | `0x3f05b962887067309ec1b93e69f4f9be783c9825251eeb8a69f073ba8db95bc5` | FINALIZED / MAJORITY_AGREE |
| resolve | `0xe0310af4dcd93624fcc1161b063e020f09ae096c78bfb8732fef3227de794893` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_a) | `0x433488a662fa6ca7f351dba182da7f27511f3438aed0b4cd8993904d32064002` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_b) | `0xa729b6128189148d964072f7bc9c799f8c62948355816160b06598442e466701` | FINALIZED / MAJORITY_AGREE |

State afterwards: `status = RESOLVED_UNDETERMINED`, `rule_outcome =
UNDETERMINED`, `payout_pot = 0`, `evidence_digest =
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` — the
SHA-256 of the empty string, which is exactly what the contract records when
the page could not be read.  Both stakers were made whole by the contract's
internal accounting.

## Case 4 — a single-sided pool refunds (market 10)

Rule: `TITLE_CONTAINS "Example Domain"`.  Only one side was ever staked.

| step | transaction | result |
|---|---|---|
| create | `0x7086928fd3db0fc4299f6e249e16e66c84a307cadbdcc251416a50290d1266d9` | FINALIZED / MAJORITY_AGREE |
| stake YES 9 (staker_c) | `0xac8fe40849a509a2eb2445f9ca88f7cc97d88738f430f117de947d75fc998472` | FINALIZED / MAJORITY_AGREE |
| close | `0x08f61f7d70f2ebcd06935f0cd04a1c426a37c13ab84d10859d6cb6fb74f130a3` | FINALIZED / MAJORITY_AGREE |
| resolve | `0x62d94d9ab46033ae8d55929e9717218ac1554da13582d2e9489d8e83bda86b8b` | FINALIZED / MAJORITY_AGREE |
| withdraw (staker_c) | `0x481d7e224f90f9aa46c944f6e90359475824e539290df38b1589e274f638f55f` | FINALIZED / MAJORITY_AGREE |

State afterwards: `status = RESOLVED_REFUNDED`, `rule_outcome = YES` (the
rule *was* decided), `pot_yes = 9 GEN`, `pot_no = 0`, `payout_pot = 0`.
Both facts are visible: the rule came out YES, and the money went back
because nobody was on the other side.

## Case 5 — withdrawing twice (market 10)

| step | transaction | result |
|---|---|---|
| first withdraw (staker_c) | `0x481d7e224f90f9aa46c944f6e90359475824e539290df38b1589e274f638f55f` | FINALIZED / MAJORITY_AGREE |
| **second withdraw (staker_c)** | `0xbab772b7e6f724b7062ec67f4e7736f689449c61d7cba62e72db5182331bb68f` | **refused: "nothing to withdraw"** |
| withdraw by somebody with no position (staker_b) | `0x00aa4f7771617df5148d1bd52180e274e6dbd30739e41f3597273dcadd228d24` | **refused: "nothing to withdraw"** |

The refusal is visible in the transaction itself: the leader receipt's result
is `nothing to withdraw`, and the state is unchanged.  A contract that
raises still finalizes with `MAJORITY_AGREE`, so the refusal was read out of
the leader receipt rather than inferred from the status.

---

## The money: what moved and what did not

This is the part that has to be said plainly.

**What works on Studio:**

| direction | observed |
|---|---|
| EOA → contract (a stake) | **works.** 46 GEN of stakes landed; the contract's own balance went to 46 GEN. |
| contract → contract | **works.** A probe paid 1 GEN to itself; the receiver's counter went from 5 GEN to 6 GEN and the transfer transaction reached `ACCEPTED / MAJORITY_AGREE`. |

**What does not work on Studio:**

| direction | observed |
|---|---|
| contract → EOA (a payout) | **fails.** The transfer is posted correctly, but the triggered transaction ends `FINALIZED / NO_MAJORITY` with `Contract 0xf391… not found`. The Studio node has no host layer, so a message to an address with no code is treated as a call to a contract that does not exist. The value is deducted from the contract and never delivered. |

The payout transactions that were observed failing, with their triggered
transaction ids:

| withdraw | triggered transaction | outcome |
|---|---|---|
| `0x481d7e22…` (market 10, 9 GEN) | `0xb1d883144aae585f46a227c4ffc432d17fd6f7e3aa6a18b0fd914a760d4d0e0a` | FINALIZED / NO_MAJORITY — "Contract 0xf391… not found" |
| `0x427ed92a…` (market 5, 12.5 GEN) | `0xa0070b9253aa17b3e26fc20809b37cce78daf7f3fc8510ebec4cb6a55ef2f473` | FINALIZED / NO_MAJORITY — "Contract 0x1914… not found" |

This is a **Studio limitation, not a bug in the contract**.  The contract's
internal accounting is correct and is verified by the tests: the position is
settled, `total_paid` increases by exactly the entitlement, and the second
withdraw is refused.  On a network with a full host layer (Bradbury, and the
mainnet) the same `emit_transfer` call routes a plain transfer to an
account.  Until that is tested there, **do not claim that a payout has moved
money on Studio** — only that the contract computed and committed the
payout, and that the network refused to deliver it.

The isolated probe that established this is `scripts/probe_payout_run.py`
(contract `0xa74a9A3790823261385502EBFc683624fcD28E3B`):

| step | transaction | observed |
|---|---|---|
| deploy | `0xa9f00d6f9c8f161f8ca8bf9a89f1aaf9e2c5b4f08fb4508ea83cbbc2772e427a` | FINALIZED / MAJORITY_AGREE |
| deposit 5 GEN from an EOA | `0xdde7721be4e44300070fedf4fd4543b0aceea149c00cfc4e67cb6a3d7ab241e2` | contract balance 0 → 5 GEN ✓ |
| pay 1 GEN to itself | `0xaab99c19cf0a9a8ebfee1e6374a004f821b62a7ed1a0b43b54d310b576e00f7e` | receiver's counter 5 GEN → 6 GEN ✓ |
| pay 1 GEN to an EOA | `0x8aa2ce7572fac76b12717b237a4869fd1c80aedc0f1f9691dd2859c4a02e58a5` | triggered tx `0x3dd59fc8…` → NO_MAJORITY, "Contract 0xf391… not found" ✗ |

## Other live observations

* **The clock is the transaction timestamp.**  A contract that reads
  `time.time()` sees the timestamp of its own transaction, identical for the
  leader and every validator (a probe that stored the clock reached
  `MAJORITY_AGREE`, transaction `0x6996fb442a89683a28d3a42e75eee0cb84ec4296ac892657bfb1ca61046df88f`).
  The same probe also showed that a web fetch **outside** a non-deterministic
  block is rejected with `forbidden`
  (`0xde1bec245305b676ea301829992b6255451787c42bb9cdacc47432a2c7689495`),
  and that a fetch **inside** one is agreed on by the leader and the
  validators (`0xe8d8672e15144c7edf24e59949dfc83908ae5ee6b845847e500850d2f52234bb`
  for the unsafe variant and `0xec2f74a4f3e7dd5e5f2e4c5a3e7a4fc3d6df72fd00445162c594f83ee292c349`
  for the sandboxed one — both `MAJORITY_AGREE` with the same digest).
* **A contract that raises still finalizes with `MAJORITY_AGREE`.**  Every
  refusal above was read out of the leader receipt's result payload, not
  from the transaction status.
* **The contract's clock keeps moving while you wait for consensus.**  Creating
  four markets one at a time burned through a 150 s close-time budget and the
  fourth was refused with "close time is too close".  Submit transactions in
  parallel and then wait for them.
