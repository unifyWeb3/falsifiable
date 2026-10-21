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
- **Live results (transaction ids):** [`state/LIVE-RESULTS.md`](state/LIVE-RESULTS.md)
- **Web app:** [`web/`](web/)

---

## Read this before you stake

Four things, in plain words.

**1. Paying out to your own account was NOT verified on Studio.** On the
GenLayer Studio network a contract **cannot deliver native GEN to an
externally-owned account**. The contract computes the payout correctly and
writes it into its own ledger, but the Studio node has no host layer, so the
delivery transaction ends `NO_MAJORITY` with *"Contract … not found"* and the
value is deducted without arriving. This is a **network** limitation, not a
bug in the contract, and this repository does not claim the payout works.
[Details and the transaction ids](#what-was-actually-verified).

**2. On Studio a failed delivery loses the value, and you cannot try again.**
`withdraw` settles your position **first** and emits the transfer **second** —
on purpose, so that a second call, or a re-entrant one, finds nothing to pay.
That ordering is what stops double payment. It is also why a Studio payout
failure is final: your position is already marked settled and the value has
already left the contract, so a retry is refused with *"nothing to withdraw"*.
Value **into** a contract and value **between** contracts both work on Studio;
only the last hop, to a plain account, does not.

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

**Live, on the GenLayer Studio network** (transaction ids in
[`state/LIVE-RESULTS.md`](state/LIVE-RESULTS.md)):

- the contract deployed, and the deployed source is **byte-for-byte** the file
  in this repository (sha256 `a3291155911ecfd93d817ecb153aea266818f94a930760c32f9952b06bc94e8b`,
  23262 bytes);
- a market staked on both sides, closed, and resolved **YES** — with the
  validators independently fetching the page and agreeing on its digest;
- a market resolved **NO**;
- a market resolved **UNDETERMINED** on a 404 and refunded both sides;
- a **one-sided** market that refunded;
- a **second withdraw refused** by the contract, and a withdraw by somebody
  with no position refused;
- a **loser** refused.

**One thing did not work on Studio, and it is stated rather than hidden:**
a contract **cannot pay native GEN to an externally-owned account** on the
Studio network. The transfer is posted correctly and the contract's internal
accounting is right, but the Studio node has no host layer, so the delivery
transaction ends `NO_MAJORITY` with *"Contract … not found"*, and the value
is deducted without being delivered. Value **into** a contract and value
**between** contracts both work on Studio. The same `emit_transfer` call is
expected to route a plain transfer on a network with a full host layer
(Bradbury, mainnet), but that has not been tested here, so this repository
does not claim it.

**The loss is final on Studio, because the position is settled first.**
`withdraw` marks the position settled and adds the amount to `total_paid`
*before* it emits the transfer, so that a second call — or a re-entrant one —
finds nothing to pay. When the Studio delivery then fails, the value has
already left the contract and the position is already settled, so **there is
nothing left to retry for**: a second `withdraw` is refused with *"nothing to
withdraw"*. The contract cannot know the delivery failed, because the failure
happens outside the contract, after it has already committed. That ordering is
what prevents double payment; on a network without a host layer it is also
why a failed payout is a loss rather than a delay.

**Only by the test suite** (not on a live network):

- the refund of a market that nobody rules on within the resolution window;
- re-entrancy in the payout path;
- a validator that sees different bytes from the leader;
- the exact behaviour of a market whose rule is decided but whose pool is
  empty (that one *was* run live, on market 10).

---

## Running it

### The contract

The contract is plain Python in the GenLayer Intelligent Contract style. The
header comment is load-bearing: it pins the runner the node must use.

```bash
python3 -m venv .venv && .venv/bin/pip install genlayer-test genlayer-py
```

`genvm-lint` checks it:

```bash
.venv/bin/genvm-lint lint contracts/falsifiable.py
GENVMROOT=/path/to/genvmroot .venv/bin/genvm-lint check contracts/falsifiable.py
```

> The `check` command resolves "latest" from the GenVM releases, and the
> newest release renamed the bundle from `genvm-universal.tar.xz` to
> `genvm-runners-all.tar.xz`, so the download 404s. Point `GENVMROOT` at a
> GenVM root (a directory with `runners/genlayer-py-std/src`) and it passes.

### The tests

```bash
.venv/bin/python -m pytest tests/ -q
```

The suite runs the contract in a real GenVM: the full path for YES, NO and
UNDETERMINED, the money invariants, and twenty red-team cases. Every refusal
is paired with a positive control, because a refusal that is not paired with
a control can pass for the wrong reason — that rule caught two real bugs
during development (the calldata codec decodes a tuple into a *list*, and the
SDK's lazy API is eager).

### The web app

```bash
cd web
cp .env.example .env.local      # then set the contract address
npm install
npm run dev
```

It reads the chain over the public RPC and **cannot write**: there is no key
anywhere in `web/`, and the configuration is public (`NEXT_PUBLIC_` only).
Every write is a command you run yourself with your own key:

```bash
export FALSIFIABLE_KEY=0x...
export FALSIFIABLE_CONTRACT=0xdf426A429a9C9Ed25f2FF208aA81190dB3874822

python3 scripts/falsifiable.py markets
python3 scripts/falsifiable.py create --url https://example.com/ \
    --claim "The page will say hello" --rule BODY_CONTAINS --param hello --close-in 3600
python3 scripts/falsifiable.py stake --market 0 --side yes --amount 10
python3 scripts/falsifiable.py close --market 0
python3 scripts/falsifiable.py resolve --market 0
python3 scripts/falsifiable.py withdraw --market 0
```

The web app builds the same commands for you, and the front end only ever
offers an action the contract will accept: that list comes from one pure
function, `deriveActions` in [`web/lib/market-state.ts`](web/lib/market-state.ts),
and a test parses `contracts/falsifiable.py` and asserts the two agree.

### Deploying to a network of your own

```bash
python3 scripts/deploy.py     # deploys and proves the source matches
```

`scripts/keys.py` writes throwaway keys to a gitignored, mode-600 file and
prints only addresses.

---

## Layout

```
contracts/falsifiable.py   the contract
state/DESIGN.md            lifecycle, rule set, equivalence, money model, red team
state/LIVE-RESULTS.md      every live transaction id, and what was observed
state/MEMORY.md            decision log, and the SDK traps that cost time
tests/                     64 tests against a real GenVM
web/                       the read-only front end
web/lib/market-state.ts    the one pure function the UI derives actions from
scripts/                   keys, deploy, live runs, the CLI
```

## Licence

MIT.
