# Falsifiable

**A stake market on claims you can check.**

Anyone opens a market on one `https://` page with one precisely-worded claim
about what that page will show at a fixed close time. Other people stake
native **GEN** on **YES** or **NO**. When the window closes, validators
independently fetch the page and rule **YES**, **NO** or **UNDETERMINED**
under the market's own written rule. The whole pot is split pro rata among
the winning side. UNDETERMINED refunds everybody. A single-sided pool refunds
everybody. Winnings are pulled by the winner, never pushed to them.

Not escrow. Not arbitration. Not a court. No appeals, no fees, no admin
payouts, and no owner.

- **Contract:** [`contracts/falsifiable.py`](contracts/falsifiable.py)
- **Design:** [`state/DESIGN.md`](state/DESIGN.md)
- **Live results on the declared target (transaction ids):**
  [`state/LIVE-RESULTS-61997.md`](state/LIVE-RESULTS-61997.md)
- **Live results on the previous deployment:**
  [`state/LIVE-RESULTS.md`](state/LIVE-RESULTS.md)
- **Network and contract (one file):** [`web/config/chain.json`](web/config/chain.json)
- **Web app:** [`web/`](web/)

---

## Read this before you stake

Four things, in plain words.

**1. Paying out to your own account works on the declared target, and the
proof is live.** On Studio Devnet (chain 61997) a contract cannot reach an
externally-owned account with an internal message: the call returns
successfully and nothing arrives. The contract therefore sends payouts as an
EVM external message, and that route did deliver. A payee's balance rose by
14 GEN at pinned block `1792703185`, while the contract's balance fell by
exactly 14 GEN. [The transaction ids and the balances](#what-was-actually-verified).

**2. A payout is not "settled" until the payee says it arrived.** `withdraw`
records a pending claim and emits the value; it does **not** touch the
settled counters and does **not** add to `total_paid`. `confirm_delivery`,
callable only by the payee, is the only path that settles the position and
books the amount as paid. While a payout is pending a second `withdraw` is
refused. If the value never arrives, the claim stays pending and is never
counted as paid: the contract will not re-emit it, because a second emission
could pay twice. That is the limit — an undelivered payout becomes stuck
rather than being retried. It is never marked settled without the payee's
confirmation.

**3. One key is one key.** The deployer key in this repository is a throwaway
Studio testnet key. It is gitignored, it is never printed, and the contract
gives it no powers beyond opening markets and staking. There is no owner
function to abuse, no admin key, no upgrade path and no fee to skim. One key
holds one key's worth of power, and that power is small.

**4. Live-verified versus only-tested.** Everything in
[What was actually verified](#what-was-actually-verified) marked **live** was
run on a real network with real transactions, and the transaction ids are
public. Everything marked *only by the test suite* was never run on a live
network and is **not** claimed as live. Nothing in this README is asserted
without a command that was run and whose output was read.

---

## How it works

### A market is four things

| | |
|---|---|
| **the page** | exactly one `https://` URL |
| **the claim** | one sentence about what the page will show |
| **the rule** | a machine-checkable check, from a closed set of six |
| **the close time** | a fixed unix timestamp |

The **rule decides the money**, not the sentence. The claim is shown to you
before you stake; the rule is what the validators apply. A claim whose prose
is misleading cannot change the outcome, because the outcome is a pure
function of the bytes the page returned and the rule you were shown.

### The six rules

| rule | YES when |
|---|---|
| `BODY_CONTAINS` | the raw response body contains the text |
| `BODY_EQUALS` | the raw response body is exactly the text |
| `TITLE_CONTAINS` | the text of the first `<title>` contains the text |
| `TITLE_EQUALS` | the text of the first `<title>` is exactly the text |
| `JSON_FIELD_CONTAINS` | the JSON value at the dotted path contains the text |
| `JSON_FIELD_EQUALS` | the JSON value at the dotted path is exactly the text |

No regex, no language model, no free text. The answer is always one of
YES, NO or UNDETERMINED.

### How the answer is reached

At resolution the contract runs one non-deterministic block. The **leader**
fetches the page, extracts the evidence bytes the rule applies to, evaluates
the rule, and produces a pair: `(outcome, sha256(evidence))`.

Every **validator** fetches the page again, on its own, and produces its own
pair. The ruling only commits if the validators agree on **both** halves —
the answer and the digest of the exact bytes they read. The digest is stored
on chain, so you can see afterwards precisely what the page said.

If the validators see different bytes, the ruling does not commit, the market
stays unresolved, and anyone may try again. An hour after the close time the
market resolves deterministically as UNDETERMINED and everybody is refunded —
so funds can never be locked.

**There is no model in the decision path.** A page that tries to instruct the
validators is just a page: it is compared against a literal string, byte for
byte, like any other. Prompt injection is not defended against; it is
structurally impossible.

### The money

* Stakes are attached to the call itself. The contract credits
  `gl.message.value` — never an amount the caller supplies.
* The winning side splits the **whole** pot, including the other side's
  money.
* Shares are computed with a **cumulative allocation**, so they sum to the
  pot *exactly*: there is no rounding dust for anybody to skim.
* UNDETERMINED and one-sided pools refund every staker to the wei.
* `withdraw` pays the caller and only the caller. It takes no address
  argument, so nobody can move somebody else's money. The position is
  settled **before** the transfer is emitted, so a second call — or a
  re-entrant one — finds nothing and is refused.
* A loser withdrawing is refused, not silently paid zero.
* Nobody can withdraw twice, and the total paid never exceeds the total
  staked. Both are asserted by the test suite.
* Minimum stake: 0.001 GEN. The market creator may not stake on their own
  market.

There are no fees and no commission, so there is nothing for a creator to
skim and no reason for them to touch the page.

### The clock

GenLayer pins the contract clock to the **transaction timestamp**, which is
identical for the leader and every validator. The close time is enforced
against that timestamp, so every validator reaches the same answer about
whether a stake was in time.

---

## The trust model, plainly

**What you can rely on**

- The money is real native GEN and the pot is conserved; the tests assert it.
- The answer is decided by bytes and a published rule, not by a model.
- Every validator fetched the page itself and agreed on the evidence.
- There is no owner, no admin key, no fee, no appeal path. Anyone may close,
  rule and withdraw; a market nobody rules on refunds itself.

**What is still trusted**

- **The validator set.** A quorum of GenLayer validators decides. The
  contract cannot tell a colluding quorum from an honest one; it can only
  require that a quorum agreed on the same bytes.
- **The moment of the reading.** The page is read when the validators fetch
  it, which is *after* the close time, not at it. A page that changes in
  between is judged on its later content. The design narrows that window; it
  cannot make a live page time-travel. This is why markets are for pages
  whose bytes are stable.
- **The author of the rule.** The rule decides the money. It is shown before
  you stake and cannot be changed afterwards, but a rule can still be written
  to be trivially true. Read the rule, not the sentence.
- **The page's own honesty.** Falsifiable proves what the page *said*, not
  what was true. A page can lie to every validator at once and the market
  will still resolve honestly on the lie.
- **One key is still one key.** The deployer key in this repository is a
  throwaway Studio key; it is gitignored, it is never printed, and the
  contract gives it no powers beyond opening markets and staking. There is
  no owner function to abuse.

---

## What was actually verified

**Live, on Studio Devnet (chain 61997), the declared target** — every
transaction id and balance in
[`state/LIVE-RESULTS-61997.md`](state/LIVE-RESULTS-61997.md):

- the contract is deployed at `0xA62952F70354355d2915ee2aC66B91effcF3a6cB`,
  and `gen_getContractCode` on that address is **byte-for-byte** the file in
  this repository (sha256 `a024fe206d11ae0a883c08348b02b664eb1e0b1032c5387413944e31a9cd2eda`,
  26995 bytes; deploy tx `0x4fcd703f…`);
- a market was created, staked on both sides, closed, and resolved **YES**;
  the validators fetched the page and agreed on its digest;
- the payout **arrived in an externally-owned account**: the payee's balance
  rose by 14 GEN at pinned block `1792703185`, and the contract's balance fell
  by exactly 14 GEN;
- the withdraw left the position **unsettled** (`settled_yes = 0`,
  `pending = 14 GEN`, `total_paid` unchanged) until `confirm_delivery` ran;
- a **second withdraw was refused**, a **loser was refused**;
- a **one-sided** market refunded through the same two-phase path;
- `total_paid + total_escrowed <= total_staked` held at every step, and
  `total_paid = total_staked = 24 GEN` after the last confirmation.

**Live, on the previous Studionet deployment (chain 61999)** — transaction ids
in [`state/LIVE-RESULTS.md`](state/LIVE-RESULTS.md). That deployment is kept
for history and is **not** the declared target:

- a market staked on both sides, closed, and resolved **YES**, and one resolved
  **NO**;
- a market resolved **UNDETERMINED** on a 404 and refunded both sides;
- a **one-sided** market that refunded;
- a **second withdraw refused**, and a withdraw by somebody with no position
  refused.

**The old defect, stated plainly.** The contract that produced those Studionet
results settled the position and added to `total_paid` *before* it emitted the
transfer. On that network the internal-message delivery to a plain account
silently did nothing, so the ledger said "paid" for money that never arrived.
That ordering is gone: the fix is the two-phase path above, and the red test
in `tests/test_payout.py` fails on the old contract with
`settled_yes moved before delivery was confirmed`.

**Only by the test suite** (not on a live network):

- the refund of a market that nobody rules on within the resolution window;
- re-entrancy in the payout path;
- a validator that sees different bytes from the leader;
- the exact behaviour of a market whose rule is decided but whose pool is
  empty (that one *was* run live, on market 10).

---

## Running it

### One config, one contract

`web/config/chain.json` is the only place the network and the contract address
live. The board imports it, every CLI command reads it, and a missing or
malformed file stops the command instead of falling back to a default. It
currently reads:

```json
{
  "network": "studio-dev",
  "chainId": 61997,
  "rpcUrl": "https://studio-dev.genlayer.com/api",
  "contract": "0xA62952F70354355d2915ee2aC66B91effcF3a6cB"
}
```

`create` calls `create_market` on that contract. It never deploys. Deploying
is `scripts/deploy.py`, and nothing else.

### The toolchain

The declared target uses the Consensus v0.6 fee envelope, which only the
release-candidate SDK understands. It lives in its own environment; the
repository's original `.venv` is left untouched.

```bash
python3 -m venv .venv-rc
.venv-rc/bin/pip install -r requirements-rc.txt
```

The contract header (`py-genlayer:latest`) is load-bearing: it selects the
runner the node must use.

`genvm-lint` checks the source:

```bash
.venv-rc/bin/genvm-lint lint contracts/falsifiable.py
GENVMROOT=/path/to/genvmroot .venv-rc/bin/genvm-lint check contracts/falsifiable.py
```

> `check` downloads a GenVM release. If that download cannot finish, point
> `GENVMROOT` at an extracted GenVM root (a directory with
> `runners/genlayer-py-std/src`) and it runs offline. The report states which
> of the two actually passed.

### The tests

```bash
.venv-rc/bin/python -m pytest tests/ -q
```

The suite runs the contract in a real GenVM: the full path for YES, NO and
UNDETERMINED, the money invariants, the payout-delivery cases, and the
red-team cases. Every refusal is paired with a positive control, because a
refusal that is not paired with a control can pass for the wrong reason.

### The web app

```bash
cd web
npm install
npm run dev
```

It reads the chain over the public RPC and **cannot write**: there is no key
anywhere in `web/`. Every write is a command you run yourself with your own
key. Each command prints the network and contract it used to stderr.

```bash
export FALSIFIABLE_KEY=0x...

python3 scripts/falsifiable.py markets
python3 scripts/falsifiable.py create --url https://example.com/ \
    --claim "The page will say hello" --rule BODY_CONTAINS --param hello --close-in 3600
python3 scripts/falsifiable.py stake --market 0 --side yes --amount 10
python3 scripts/falsifiable.py close --market 0
python3 scripts/falsifiable.py resolve --market 0
python3 scripts/falsifiable.py withdraw --market 0
python3 scripts/falsifiable.py confirm-delivery --market 0
python3 scripts/falsifiable.py position --market 0 --address 0x...
python3 scripts/falsifiable.py ledger
```

`withdraw` requests the payout. `confirm-delivery` is what settles the
position and books it as paid; run it from the same account that withdrew,
after the value lands.

The web app builds the same commands for you, and the front end only ever
offers an action the contract will accept: that list comes from one pure
function, `deriveActions` in [`web/lib/market-state.ts`](web/lib/market-state.ts),
and a test parses `contracts/falsifiable.py` and asserts the two agree.

### Deploying

```bash
python3 scripts/deploy.py                  # deploy, prove the source, print
python3 scripts/deploy.py --write-config   # ... and make it the configured contract
```

`scripts/deploy.py` is the only deployment path. It prints the address and
proves that `gen_getContractCode` is byte-for-byte the repository file. Only
`--write-config` updates `web/config/chain.json`. `scripts/keys.py` writes
throwaway keys to a gitignored, mode-600 file and prints only addresses.

---

## Layout

```
contracts/falsifiable.py   the contract
state/DESIGN.md            lifecycle, rule set, equivalence, money model, red team
state/LIVE-RESULTS-61997.md  the current deployment: ids, balances, ledger
state/LIVE-RESULTS.md      the previous deployment, kept for history
state/MEMORY.md            decision log, and the SDK traps that cost time
tests/                     96 tests against a real GenVM
web/                       the read-only front end
web/lib/market-state.ts    the one pure function the UI derives actions from
web/config/chain.json      the one place the network and contract live
scripts/                   keys, deploy, live runs, the CLI
```

## Licence

MIT.
