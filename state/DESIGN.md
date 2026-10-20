# Falsifiable — design

> A stake market on **checkable claims about a public web page**.
> Not escrow. Not arbitration. Not a court. No appeals, no fees, no admin payouts.

---

## 0. What the product is

One **market** is:

| field | meaning |
|---|---|
| `url` | exactly one `https://` page |
| `claim` | one precisely-worded human sentence describing what the page will show |
| `rule` | a **machine-checkable** rule (closed set, see §3) that decides YES/NO |
| `close_time` | a fixed unix timestamp |

Anyone may stake native **GEN** on **YES** or **NO**. At close, validators
independently fetch the page and evaluate the rule under the market's own
written rule. The whole pot is split pro rata among the winning side.
UNDETERMINED refunds everyone. A single-sided pool refunds everyone.
Winnings are **pulled** by the winner (`withdraw`), never pushed.

The binding artefact is the **rule**, not the prose claim. The prose is shown
to stakers; the rule decides the money. A claim whose prose is ambiguous or
rigged cannot change the outcome, because the outcome is a pure function of
(bytes fetched, rule).

---

## 1. Lifecycle and exact states

```
                    create_market()
                         |
                         v
                     [ OPEN ]  <--------- stakes allowed while now < close_time
                         |
             close_market() |  (permissionless, requires now >= close_time)
                         v
        [ CLOSED_AWAITING_RESOLUTION ]   stakes refused
                         |
            resolve()   |  (permissionless)
                         v
   +--------------------+----------------------------+
   |                                                 |
   v                                                 v
[ RESOLVED_YES ]  [ RESOLVED_NO ]            [ RESOLVED_UNDETERMINED ]
   winners split                                 everyone refunded
   the pot
                         
   +--------------------+----------------------------+
   |                                                 |
   v                                                 v
            [ RESOLVED_REFUNDED ]  (rule was decided YES/NO, but the pool
                                    was one-sided -> everyone refunded)
```

Six states. The five required by the brief plus `RESOLVED_REFUNDED`, which
exists because "the rule said YES" and "the pool was one-sided so the money
went back" are two different facts and the UI must be able to show both.

### Legal actions per state

| state | `stake` | `close_market` | `resolve` | `withdraw` |
|---|---|---|---|---|
| OPEN | yes iff `now < close_time` | yes iff `now >= close_time` | yes iff `now >= close_time` (auto-closes first) | no |
| CLOSED_AWAITING_RESOLUTION | no | no | yes | no |
| RESOLVED_YES | no | no | no | yes, if the caller has an unsettled position |
| RESOLVED_NO | no | no | no | yes, if the caller has an unsettled position |
| RESOLVED_UNDETERMINED | no | no | no | yes (full refund of own stake) |
| RESOLVED_REFUNDED | no | no | no | yes (full refund of own stake) |

Everything is **permissionless**: anybody may close, anybody may resolve,
anybody may call `withdraw` for their own position only. There is no owner,
no admin, no fee, no appeal path, and no way to move a staker's money to
somebody else.

`withdraw` takes **no recipient argument**. It always pays `gl.message.sender`.
There is no method anywhere that writes state about an address the caller did
not prove, and no method that pays a caller-supplied address.

---

## 2. The clock

GenLayer v0.2.16 exposes **no nondeterministic time**. `time.time()` inside a
contract returns the **transaction timestamp**, which is identical for the
leader and every validator (measured on Studionet: the contract clock matched
the wall clock at tx-acceptance time, and lagged it by exactly the consensus
delay when read later).

Consequences, used deliberately:

* `close_time` is enforced against the **transaction timestamp** of the
  staking call, not the wall clock. A stake submitted before `close_time` in
  wall-clock terms but timestamped after it is refused, and vice versa. All
  validators see the same timestamp, so the decision is deterministic.
* The clock is **not** used as evidence. It is only a gate.
* Because the timestamp is set at acceptance, a stake that races the close
  boundary is decided by the node, not by the contract. Documented.

---

## 3. The rule: a closed set, no free text

The rule is `(kind, param, path)`. `kind` is an enum; `param` is a literal
string; `path` is only used by the JSON kinds.

| kind | evidence (the exact bytes the rule is applied to) | outcome |
|---|---|---|
| `BODY_CONTAINS` | the raw response body | YES iff `param` occurs in the body bytes |
| `BODY_EQUALS` | the raw response body | YES iff the body bytes equal `param` |
| `TITLE_CONTAINS` | the text between the first `<title>…</title>`, stripped | YES iff `param` occurs in it |
| `TITLE_EQUALS` | same | YES iff it equals `param` |
| `JSON_FIELD_CONTAINS` | the canonical JSON encoding of the value at `path` | YES iff `param` occurs in it |
| `JSON_FIELD_EQUALS` | same | YES iff it equals `param` |

There is **no regex, no LLM, no free-text answer**. The validator's decision
is a pure function of bytes, so the answer is always in the closed set
`{YES, NO, UNDETERMINED}` and never a paragraph.

`path` syntax: dot-separated, e.g. `data.items.0.name`. Segments index objects
by key and arrays by integer index.

Outcome:

* the fetch raised (DNS, TLS, timeout, …) → **UNDETERMINED**
* the HTTP status is not 2xx → **UNDETERMINED**
* the evidence could not be extracted (no `<title>`, body is not JSON, path
  missing) → **UNDETERMINED**
* otherwise the rule is evaluated → **YES** or **NO**

---

## 4. Resolution, equivalence, and the recorded evidence

### The non-deterministic block

`resolve()` runs one non-deterministic block. Inside it:

```
leader():
    try:    resp = gl.nondet.web.get(url)          # https only, GET only
    except: return (UNDETERMINED, sha256(b""))
    if status not in 2xx: return (UNDETERMINED, sha256(b""))
    view = extract_evidence(body, kind, path)
    if view is None:     return (UNDETERMINED, sha256(b""))
    return (evaluate(view, kind, param), sha256(view))

validator(leader_result):
    if leader_result is not a successful return: return False
    return leader() == leader_result          # element-wise
```

The payload is a pair `(outcome:int, digest:bytes)`.

* `outcome` is the answer the market will use.
* `digest` is **sha256 of the exact evidence bytes** — the bytes the rule was
  applied to. For `BODY_*` rules these are literally the page bytes.

**Both fields must match exactly.** The validator fetches the page itself; it
does not trust the leader's bytes, and it does not trust the leader's answer.

### Why element-wise comparison

`genlayer.py.calldata` decodes a tuple into a **list**. `leader_result == my_result`
on the decoded value is therefore *always* `False` (measured: a positive
control that compared tuples reported `False` while the transaction reached
`MAJORITY_AGREE`). The contract compares field by field. This is a real bug
that was found and fixed by a positive control, not by reading the docs.

### What is persisted

Only two fields are written from the non-deterministic block:
`rule_outcome` and `evidence_digest`. Both are values **every validator
independently recomputed and agreed on**, because the transaction only
commits if the equivalence check passes for a majority of validators. Nothing
that a validator did not verify is ever written. In particular the contract
does **not** store the raw body, the HTTP status, or any validator's private
data.

### When the page changes between validators

The validators fetch independently. If they see different bytes, their digests
differ, the equivalence check fails, the transaction does **not** commit, and
**no state changes** (GenLayer reverts the whole transaction). The market stays
`CLOSED_AWAITING_RESOLUTION` and anyone may call `resolve()` again.

To guarantee funds can never be locked, `resolve()` has a **deterministic
fallback**: once `now >= close_time + RESOLUTION_WINDOW` (1 hour),
`resolve()` does not fetch anything at all and resolves the market as
`RESOLVED_UNDETERMINED` — a refund for everybody. This path needs no
consensus about the outside world, so it always succeeds.

So the page-changed case ends in a refund, never in a contested payout and
never in locked funds.

### Honest limitation

The evidence is read **when the validators fetch**, which is after `close_time`.
A page that changes between `close_time` and the fetch is judged on its later
content. The design narrows this window (the resolution window is one hour
and the fetch happens in the first block after close) and makes the outcome
deterministic *given the bytes*, but it cannot make a live web page
time-travel. Markets on pages with per-request noise (rotating tokens,
timestamps, ad slots) will generally fail to reach consensus and will refund.
That is a property of the product, not a bug: it is what "a checkable claim"
means.

---

## 5. Money model

### Staking

* `stake(market_id, side)` is **payable**. The contract credits
  `gl.message.value` — never a caller-supplied amount.
* `MIN_STAKE = 1_000_000_000_000_000` wei (0.001 GEN).
* The **market creator may not stake** on their own market. A creator has no
  stake to protect, so they have no economic reason to manipulate the page.
* A staker may hold both sides of the same market; the math below handles it.
* Total stake is tracked at the contract level: `total_staked`.

### The pool

`pot_yes`, `pot_no` per market. `pot = pot_yes + pot_no`.

* **Both sides staked, rule says YES** → the YES side splits the **whole**
  pot (including the NO side's money). NO side gets 0.
* **Both sides staked, rule says NO** → symmetric.
* **One side empty** → `RESOLVED_REFUNDED`: everyone gets their own stake back.
* **UNDETERMINED** → `RESOLVED_UNDETERMINED`: everyone gets their own stake back.

### Pro-rata split with **no dust**

Each winner's share is computed with a **cumulative allocation**, not an
independent `floor`:

```
C            = market.settled_<side>_stake      (Σ of stakes already settled on this side)
W            = market.pot_<side>                (total staked on this side)
P            = market.payout_pot                (the whole pot, when there is a winner)
share(i)     = floor(P * (C + s_i) / W) - floor(P * C / W)
```

where `s_i` is the withdrawing staker's stake on that side. The sum telescopes:
after every winner on that side has settled, the total paid out is exactly
`floor(P * W / W) = P`. **There is no rounding dust** — the shares sum to the
pot exactly, in any withdrawal order.

The only residue is the part of the pot belonging to winners who never
withdraw; it simply stays in the contract. That is a property of a
pull-based design, not a leak: a winner who does not withdraw loses their own
money, and nobody else's.

`settled_<side>_stake` is advanced when a staker's position on that side is
settled, so the cumulative allocation is always relative to the set of
already-settled stakes. It is a single `u256` per market — **no iteration over
stakers, ever**.

### Refund path

On `RESOLVED_UNDETERMINED` / `RESOLVED_REFUNDED` the entitlement per side is
exactly the staker's own stake — no division, so the refunds sum to the pot
exactly, again with no dust.

### Withdraw safety

`withdraw(market_id)`:

1. Reads the caller's position. If nothing is unsettled → refuse
   ("nothing to withdraw").
2. Computes the entitlement per side from the *current* market state
   (deterministic; the pot cannot change after resolution because staking is
   closed).
3. **Zeroes the position first** (sets `settled_yes = stake_yes`,
   `settled_no = stake_no`), then emits the transfer.
   *Checks-effects-interactions*: a re-entrant call sees an empty position
   and refuses.
4. Emits exactly one transfer of `total_amount` to `gl.message.sender`.

* **Double withdraw**: the second call finds nothing unsettled and refuses.
* **Re-entrancy**: the recipient of a transfer is a different account; the
  emitted message is delivered in a later transaction, and the position is
  already zeroed.
* **Over-payment**: `total_paid_out` is incremented by the amount paid and is
  asserted (in tests) never to exceed `total_staked`.

### Invariants (all covered by tests)

1. `sum(all payouts) + unclaimed == pot`; with every winner withdrawing, the
   sum is **exactly** `pot` (no dust).
2. `total_paid_out <= total_staked` at all times.
3. Nobody can withdraw twice.
4. The contract's native balance never goes below the sum of outstanding
   entitlements.
5. A loser withdraws exactly 0.
6. A refunded staker is made exactly whole.

### What GEN is worth on Studionet

GEN on the Studio network is **simulated money** in a local database. There is
no market for it, no liquidity, and no redemption. Every number in this
project is denominated in GEN and is meaningful only as a *ratio*. Do not read
any amount as real money.

---

## 6. Red-team cases (14+) and how each is handled

| # | case | handling | test |
|---|---|---|---|
| 1 | prompt injection inside the page | the page is never interpreted, only compared byte-wise against a literal; there is no LLM in the loop at all | `test_redteam.py::test_prompt_injection_in_page_is_inert` |
| 2 | page changes between close and fetch | validators' digests differ → no consensus → no state change → after the resolution window the deterministic fallback refunds everybody | `test_redteam.py::test_page_changed_between_validators_refunds` |
| 3 | validators read different CDN copies | same as #2: different bytes → different digest → no consensus | `test_redteam.py::test_divergent_bytes_prevent_consensus` |
| 4 | author writes a rigged / ambiguous claim | the prose claim is not the binding artefact; the machine rule decides, and the rule is shown to stakers before they stake | `test_redteam.py::test_claim_text_does_not_affect_outcome` |
| 5 | creator stakes on their own market | refused: `stake` rejects `gl.message.sender == creator` | `test_redteam.py::test_creator_cannot_stake` |
| 6 | last-second staking at close | `stake` requires `now < close_time` against the transaction timestamp; all validators see the same timestamp | `test_redteam.py::test_stake_after_close_time_refused` |
| 7 | one-sided pool | resolves to `RESOLVED_REFUNDED`; everybody is made whole | `test_redteam.py::test_single_sided_pool_refunds` |
| 8 | rounding theft | cumulative allocation: shares sum to the pot exactly, no dust to steal | `test_money.py::test_no_dust_shares_sum_to_pot` |
| 9 | double withdraw | position is zeroed before the transfer; the second call refuses | `test_money.py::test_double_withdraw_refused` |
| 10 | re-entrancy through the payout | position zeroed before emitting; the transfer is delivered in a later transaction; the receiver has no way back into the contract's state | `test_money.py::test_reentrant_withdraw_cannot_double_claim` |
| 11 | unreachable page | fetch exception → UNDETERMINED → refund | `test_redteam.py::test_unreachable_page_refunds` |
| 12 | malformed claim / rule | `create_market` validates url scheme, lengths, rule kind, and the close-time horizon; malformed input is rejected before any state is created | `test_redteam.py::test_malformed_market_rejected` |
| 13 | replay of a resolution | `resolve` requires `CLOSED_AWAITING_RESOLUTION`; a resolved market refuses a second resolution | `test_redteam.py::test_resolve_is_not_replayable` |
| 14 | attacker triggers resolution | resolution is **permissionless by design** and cannot change the outcome: the rule and the evidence decide. What an attacker can do is *not* resolve a market that is still open (refused), and not withdraw anybody else's money | `test_redteam.py::test_resolver_cannot_choose_the_outcome` |
| 15 | huge input | url/claim/param lengths are capped; the body size is not attacker-controlled but the digest is over a bounded view | `test_redteam.py::test_oversized_inputs_rejected` |
| 16 | many tiny stakes | per-staker state is a map entry; there is no loop over stakers in any code path; a withdraw costs O(log n) | `test_money.py::test_many_tiny_stakes_are_all_paid_exactly` |
| 17 | caller-supplied address in state | every state write about an address is keyed by `gl.message.sender`; there is no method taking a beneficiary | `test_redteam.py::test_no_caller_supplied_beneficiary` |
| 18 | rounding on the loser side | losers are settled at exactly 0 | `test_money.py::test_loser_gets_zero` |

---

## 7. Lessons from earlier rejections, and where they are answered

1. *Every persisted evidence or digest field must be checked by validators
   against an independently computed value.* → The only fields written from
   the non-deterministic block are `rule_outcome` and `evidence_digest`, both
   of which every validator recomputed and agreed on. No other field is
   written from outside the transaction's own deterministic code.
2. *No unauthenticated caller may create global state about an arbitrary
   address or label from fabricated input.* → The creator is
   `gl.message.sender`. Stakes are credited to `gl.message.sender`. There is
   no free-text label, no reputation registry, and no caller-supplied address
   anywhere in the write API.
3. *Submitted source and deployed source must match byte for byte.* → The
   deployed contract is fetched back with `gen_getContractCode` and compared
   by sha256 against the repository file. The runner comment header is part
   of the file, so the hash covers it.
4. *A refusal test without a positive control can pass for the wrong reason.*
   → Every refusal test is paired with a positive control that must succeed
   on the same path. This actually caught two real bugs: the tuple-vs-list
   comparison and the `Lazy.get()` misuse.
5. *The UI and docs must never offer an action the contract rejects.* → The
   web app derives the available actions from **one pure function**
   `deriveActions(status, …)` in `web/lib/market-state.ts`. A test parses
   the status enum and the legal-action table **out of the contract source**
   and asserts the two agree, so they cannot drift.
6. *Docs and UI must not claim more than tests and live runs prove.* → The
   README states exactly what was verified live and what was only unit
   tested, and the trust section says plainly what remains.

---

## 8. Trust model (stated plainly)

What a user can rely on:

* The money is real native GEN and moves; the pot is conserved; nobody can
  withdraw twice; there is no admin key and no fee.
* The outcome is a **deterministic function of the fetched bytes and the
  published rule** — there is no LLM in the decision path, so no model can
  be talked into a different answer.
* Every validator independently fetched the page and agreed, byte for byte,
  on the evidence that produced the answer.

What remains trusted:

* **The validator set.** A quorum of GenLayer validators decides. If enough
  of them are malicious or collude, they can agree on a digest that the page
  did not produce. The contract cannot detect a colluding quorum; it can only
  require that a quorum agreed.
* **The single fetch moment.** The page is read after `close_time`, not at it
  (see §4).
* **The rule's author.** The rule decides the money. The UI shows the rule
  before you stake, but a rule can still be written to be trivially true
  ("the page contains the letter a"). Read the rule, not the prose.
* **The page's own honesty.** The page can lie. `Falsifiable` proves what the
  page *said*, not what was true.
* **One key is still one key.** The deployment key in this repository's
  demo scripts is a **throwaway Studio key**; it is gitignored, it is not
  printed, and it controls nothing except testnet funds. On a real network
  the same rule applies to any single deployer key: it is one key, and the
  contract gives it no special powers. The contract has no owner and no
  admin functions, so a leaked key can create markets and stake — nothing more.
