# Falsifiable — decision log / session memory

> Resume: read this file, then `state/DESIGN.md`, then `git log --oneline`.
> A fact is marked `[VERIFIED]` only when a command was run and its output
> observed.

---

## 0. Product

**Falsifiable** — a stake market on *checkable claims about a public web page*.

- One market = one `https://` URL + one precisely-worded claim + one
  machine-checkable rule + a fixed close time.
- Anyone stakes native GEN on YES or NO.
- At close, validators independently fetch the page and decide YES / NO /
  UNDETERMINED under the market's own written rule (closed set, never free
  text, no LLM in the decision path).
- The whole pot is split pro rata among the winning side. UNDETERMINED refunds
  everybody. A single-sided pool refunds everybody.
- Winnings and refunds are **pulled** through `withdraw`; never pushed.
- Not escrow, not arbitration, not a court. No appeals, no fees, no admin
  payouts, no owner.

### Name

`falsifiable` — the market is about claims that *can* be checked and found
false. Popper's word, and the product's whole argument.

Rejected, and why:

| name | why not |
|---|---|
| `attest` | clashes with the Ethereum Attestation Service (EAS, attest.org) — well known |
| `verdict` | clashes with several prediction markets (verdict.space, verdict.trade) |
| `fathom` | clashes with the Fathom Protocol (XDC) and Fathom Analytics |
| `colophon` | clashes with the Colophon (CLPH) coin and is a generic typography term |
| `exegesis` | clashes with the exegesis-js OpenAPI library; too academic |
| `vouch` | clashes with the Vouch (VOUCH) PulseChain liquid-staking token |
| `oath` | clashes with the OATH Protocol (dispute resolution, has a token) |
| `surety` | an earlier project of ours — not referenced, and not reused |
| `scry` | clashes with the well-known Ruby static-analysis tool |
| `oracle` / `augur` / `ballot` / `quorum` | too generic or already a well-known project |

GitHub availability under `unifyWeb3` was checked via the API for every
candidate (all 404 / free at the time of writing).

---

## 1. Environment [VERIFIED]

- Repo root `/root/market-build`; venv at `.venv` (python 3.12).
- `gh` authenticated as **unifyWeb3**; `vercel` authenticated as **oxunifyy**.
- Studio RPC: `https://studio.genlayer.com/api/rpc`, chain id 61999 / `0xf22f`.
- Network egress is **intermittent**: DNS for `studio.genlayer.com` fails
  intermittently with `Temporary failure in name resolution`. `scripts/studio.py`
  wraps the provider in `ResilientProvider` (12 attempts, 2.5 s backoff, DNS
  warm-up) and retries **only** transport failures, never JSON-RPC errors.
- `genlayer-test` (gltest) upgraded 0.28.0 → **0.29.2**; `genlayer-py`
  0.9.0 → **0.16.3**. The local runner (`direct_vm` / `direct_deploy`) runs
  contracts in-process in ~0.3 s per test — the fast iteration loop.
- Chromium: `/root/.config/google-chrome-for-testing` + `/root/browser-tool`
  (puppeteer) for UI verification.

---

## 2. GenLayer facts learned from source and from the live network

### 2.1 The hosted Studio runs GenVM v0.2.16 [VERIFIED]

`gen_getContractSchemaForCode` on a v0.3.0-style contract returned a
`genvm_log` entry: `'version': 'v0.2.16-x86_64-linux-release'`.

Consequences:

* The v0.3.0 contract header/API used by the Studio *repo*'s example
  contracts is **rejected** by the hosted node.
* The v0.2.16 header is:
  `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`
* The v0.2.16 Python API is `import genlayer.gl as gl`, `gl.Contract`,
  `gl.message.sender_address` (NOT `gl.message.sender`),
  `gl.message.value`, `gl.get_contract_at(addr).emit_transfer(value=...)`.

### 2.2 A contract must start with a runner comment [VERIFIED]

Without it the deploy fails with `invalid_contract absent_runner_comment`
(seen in a real deploy's leader receipt). `genvm-lint lint` warns `W010`.

**Fast validation loop (no deploy needed):**
`gen_getContractSchemaForCode` on the Studio RPC compiles the contract and
returns its ABI. Use it on every edit before deploying.

### 2.3 `genvm-lint check` 404s on `genvm-universal.tar.xz` [VERIFIED]

```
$ .venv/bin/genvm-lint check contracts/falsifiable.py
✓ Lint passed (2 checks)
  Warnings:
    line 1: Missing contract dependency header (# { "Seq": [...] })
✗ Validation failed
  Failed to load SDK: HTTP Error 404: Not Found
```

Cause: `genvm_linter/validate/artifacts.py` resolves "latest" with a HEAD to
`https://github.com/genlayerlabs/genvm/releases/latest`, which now redirects
to `v0.3.0-rc7`, whose assets are named `genvm-runners-all.tar.xz`. Confirmed
independently:

```
$ curl -o /dev/null -w "%{http_code}" -L https://github.com/genlayerlabs/genvm/releases/latest/download/genvm-universal.tar.xz
404
```

**The supported alternative that passes** is the `GENVMROOT` path:
`genvm_linter/validate/sdk_loader.py::get_sdk_paths_from_genvmroot` checks
`GENVMROOT` *before* it tries to download, and looks for
`runners/genlayer-py-std/src` or `runners/py-lib-genlayer-std/src`.

```
$ GENVMROOT=/tmp/opencode/genvmroot .venv/bin/genvm-lint check contracts/falsifiable.py
✓ Lint passed (2 checks)
  Warnings:
    line 293: Non-deterministic call 'time.time()'
✓ Validation passed
  Contract: Falsifiable
  Methods: 13 (8 view, 5 write)
```

(The `time.time()` warning is expected: the linter flags it generically; in
GenLayer the clock is pinned to the transaction timestamp, which is identical
for the leader and every validator — verified live, §2.4.)

### 2.4 The in-contract clock is the transaction timestamp [VERIFIED]

`time.time()` inside a contract returns the **transaction timestamp**, not the
wall clock. Measured on Studionet: the contract clock matched the wall clock
at tx-acceptance time, and lagged it by exactly the consensus delay when read
later (506 s in one measurement, 0 s in another read immediately).

* `close_time` is therefore enforced against the *transaction timestamp* of the
  staking call, and all validators see the same value.
* The clock is only a gate, never evidence.
* **Trap:** the contract's clock advances while your script waits for a
  transaction to finalise. Creating four markets one at a time burned through
  a 150 s close-time budget and the fourth was refused with
  "close time is too close". Submit transactions in parallel, then wait.

### 2.5 Web fetching only works inside a non-deterministic block [VERIFIED]

* A `gl.nondet.web.get()` outside a non-deterministic block fails with
  `err:6: forbidden`.
* Inside `gl.vm.run_nondet_unsafe` it works, and **the validators fetch the
  page independently**: on Studionet the leader and the validators all fetched
  `https://example.com/` and agreed on status 200, length 577 and the same
  sha256 (`25ddf2c8…`), and the transaction reached `MAJORITY_AGREE`.
* The sandboxed `gl.vm.run_nondet` also reaches `MAJORITY_AGREE` with the same
  digest.

### 2.6 SDK sharp edges that cost real debugging time [VERIFIED]

| gotcha | consequence | fix |
|---|---|---|
| `genlayer.py.calldata` decodes a **tuple into a list** | `my_tuple == decoded` is always `False`, so every validator disagreed and the tx reached `MAJORITY_DISAGREE` | compare element by element (`_same_result`) |
| `gl.vm.run_nondet_unsafe` is `@_lazy_api` | it returns the value **eagerly**; calling `.get()` on it raises `AttributeError` | do not call `.get()` |
| `gl.nondet.web.get` is `@_lazy_api` | it returns a `Response` **eagerly**; calling `.get()` raises `AttributeError: 'Response' object has no attribute 'get'` | do not call `.get()` |
| `TreeMap.compute_if_absent` never invokes its "exists" callback on insert | `IndexError: list index out of range` | use `tree[key] = value` then read it back |
| `gl.message.sender` does not exist in v0.2.16 | `AttributeError` | `gl.message.sender_address` |
| `gl.get_contract_at` needs a real `Address` | `TypeError: address expected` | `Address(to)` |
| a contract that raises still finalizes with `MAJORITY_AGREE` | a reverted call looks like a success | inspect `consensus_data.leader_receipt[0].result.raw` |

### 2.7 Value transfer out of a contract, on Studio [VERIFIED]

Three directions, three answers:

| direction | observed |
|---|---|
| EOA → contract | **works** — 5 GEN landed, the contract's own balance went to 5 GEN |
| contract → contract | **works** — the receiver's counter went 5 GEN → 6 GEN, the transfer tx reached `ACCEPTED / MAJORITY_AGREE` |
| contract → **EOA** | **fails** — the transfer is posted, but the triggered tx ends `NO_MAJORITY` with *"Contract 0x… not found"*, and the value is deducted without being delivered |

The Studio has no host layer, so a message to an address with no code is
treated as a call to a contract that does not exist.  This is a **Studio
limitation**: the contract's internal accounting is correct and is covered by
the tests, and the same `emit_transfer` call is expected to route a plain
transfer on a network with a full host layer — but that has **not** been
tested here, so nothing in this repository claims it.

### 2.8 Two front-end encoding traps [VERIFIED]

Both were found by running the deployed app against the live contract, not by
reading the code:

* the **RLP byte-string header** must use the long form above 55 bytes.  The
  short form (`0x80 + length`) above 55 produces a prefix that reads as a
  *list* header, so any call whose calldata was longer than 55 bytes was
  rejected by the node.  `get_market` (22 bytes) worked and `get_position`
  (70 bytes) did not — a failure that looks like "some calls work".
* the call object must **omit `kwargs`** when it is empty, exactly as the
  Python SDK's `make_calldata_object` does.

Both are now pinned by fixture tests in `web/lib/calldata.test.ts`, whose
expected bytes were produced by the SDK itself.


---

## 3. Live Studio RPC notes [VERIFIED]

- `sim_fundAccount` takes **flat positional params**: `params: [account, amount]`
  with `amount` an **int**. `params: [{account, amount}]` fails with
  `Missing required parameter: amount`.
- `gen_call` works with `from = 0x000…0` and either
  `transaction_hash_variant`; the result is the hex calldata of the return
  value (no `0x` prefix).
- `gen_getContractCode` returns base64 of the deployed source.
- `genlayer_py.read_contract` needs a `TransactionHashVariant` **enum**, not a
  string.

---

## 4. What was built

| path | what |
|---|---|
| `contracts/falsifiable.py` | the contract (one `gl.Contract`, 13 methods) |
| `state/DESIGN.md` | lifecycle, rule set, equivalence, money model, red team |
| `tests/` | 64 pytest tests against the local GenVM runner |
| `web/` | the Next.js front end (read-only) |
| `web/lib/market-state.ts` | the ONE pure function the UI derives actions from |
| `web/lib/market-state.test.ts` | parses the contract source and asserts parity |
| `scripts/` | keys, deploy, live runs, the CLI the UI tells you to run |

---

## 5. Live results (Studionet)

Contract `0xdf426A429a9C9Ed25f2FF208aA81190dB3874822`
sha256 `a3291155911ecfd93d817ecb153aea266818f94a930760c32f9952b06bc94e8b`
(repo file and `gen_getContractCode` output are byte-identical, 23262 bytes).
Deploy tx `0x43b139b4a3d89591ca21181c1a3aadf5f0fbd5eaca27fa89f1b5ea13b7b0681a`.

See `state/LIVE-RESULTS.md` for the transaction ids of every live step.

---

## 6. Delivered

| | |
|---|---|
| GitHub | https://github.com/unifyWeb3/falsifiable (public) |
| Vercel | https://falsifiable.vercel.app |
| Contract | `0xdf426A429a9C9Ed25f2FF208aA81190dB3874822` on Studionet |
| sha256 | `a3291155911ecfd93d817ecb153aea266818f94a930760c32f9952b06bc94e8b` (repo == deployed, byte identical) |

### Verification numbers (all run, all green)

| check | result |
|---|---|
| `pytest tests/ -q` | **64 passed**, exit 0 |
| `npx tsx --test lib/*.test.ts` | **13 passed**, 0 failed |
| `npx tsc --noEmit` | exit 0 |
| `genvm-lint lint contracts/falsifiable.py` | ✓ Lint passed (2 checks), exit 0 |
| `GENVMROOT=… genvm-lint check contracts/falsifiable.py` | ✓ Validation passed, 13 methods (8 view, 5 write), exit 0 |
| `npx next build` | ✓ compiled, 7 routes, exit 0 |

The one lint warning — `line 293: Non-deterministic call 'time.time()'` — is
expected and explained: in GenLayer the clock is pinned to the transaction
timestamp, which every validator shares (verified live, §2.4).

### The Vercel project

The project was created with `vercel project add`, which left `framework: null`
and `ssoProtection: all_except_custom_domains`.  With the framework unset,
Vercel served the deployment as 404 on every route, and with the protection on
it redirected to the SSO page.  Both are project settings, fixed with
`vercel api --method PATCH /v9/projects/falsifiable`:
`{"framework":"nextjs"}` and `{"ssoProtection":null}`.  No redeploy was
needed for the protection change; the framework change did need one.

### What was deliberately not done

* The GitHub repo is **not** connected to Vercel for automatic redeploys, so
  that the deployment count stayed at one working deployment.
* The three probe contracts (`contracts/probe_*.py`) are kept in the repo on
  purpose: they are how the value-transfer, web-fetch and clock findings
  above were established, and re-running them reproduces the evidence.

---

## 7. Release-candidate review — session log

A release candidate network was announced: **Studio studio-next.genlayer.com**,
RPC `studio-next.genlayer.com/api`, chain id **61997**, CLI `genlayer@0.40.0-rc.3`,
`genlayer-js@2.0.0-rc.1`, `genlayer-py==0.19.0rc2`, `genlayer-test==0.30.0rc2`,
`genvm-linter==0.11.1rc2`, described as a release candidate for the
**Consensus v0.6 fee implementation**.  The announcement was treated as
UNVERIFIED until it was confirmed from official GenLayer sources.

### Stage 1 — what is published [VERIFIED]

| check | result |
|---|---|
| default branch | `master` (`git remote show origin` → `HEAD branch: master`) |
| local HEAD | `195c13b` at the time of the check, then `ad0d35e` (the README fix) |
| `origin/master` | identical to local HEAD at both points; `git log origin/master..HEAD` empty |
| unpushed work | none — the only thing in the tree was untracked `state/SHOWCASE-COPY.md`, now committed |
| live site | `https://falsifiable.vercel.app` → 200, board renders **11 markets** read from the Studionet contract |
| Vercel → GitHub | **not connected**: `vercel api /v9/projects/falsifiable` has **no `link` key**; deployments are uploaded by the CLI |
| deployment provenance | the production deployment records `githubCommitSha: 86a136068f815ca7c5efa2bcc9ec46f9830d4cab` — it was built from that pushed commit |
| deployed code vs pushed code | `git diff --name-only 86a1360 HEAD -- web/` is **empty**: the only commit after the deployment touched `state/MEMORY.md`, so the served `web/` code is byte-identical to the pushed `web/` code |
| the fix is really live | `GET /api/position?id=5&address=0x191489…` returns a real position (`yes=10 GEN`).  `get_position` is a 70-byte calldata, which is exactly the case that the pre-`86a1360` RLP short-form header broke.  The live endpoint therefore runs the **fixed** codec. |

**Grep for the studied project's name / author / URL — empty in the working
tree.**  The four candidate spellings return **no match** in the working tree
(tracked + untracked) after this edit.  One earlier decision-log entry (commit
`c1a92ee`, already published) quoted the candidate strings themselves; that is
left in history rather than rewritten, and the strings are not repeated here.
The only non-npm GitHub URLs in tracked files are
`github.com/unifyWeb3/falsifiable` (ours) and `github.com/genlayerlabs/genvm`
(official GenLayer).  `state/SHOWCASE-COPY.md` was untracked; it is ours and
contains no external project name.

**Secret sweep — clean.**

| where | result |
|---|---|
| `git ls-files` | no key file, no `.env`; only `web/.env.example` (public config, no secret) and `scripts/keys.py` (the generator) |
| working tree | the 4 live private keys appear **only** in `secrets/studionet_keys.json`, which is untracked, gitignored (`git check-ignore` → `.gitignore:6:secrets/`) and mode `600` |
| all git refs | every 64-hex candidate in every blob/tree/commit of every ref and the reflog was compared against the real keys: **0 hits** |
| mnemonics | none: the key file stores only raw private keys, no seed phrase |

**README honesty — one gap found and fixed.**  The four required statements
now sit near the top of the README under *Read this before you stake*:
(1) payout delivery to an EOA was **not** verified on Studionet and why;
(2) a failed Studio delivery **loses the value, because the position is
settled first** and a retry is refused — this was the missing one, the
README said the value was "deducted without being delivered" but never said
the loss was final;
(3) one key is one key;
(4) what is live-verified versus only-tested.  Committed as `ad0d35e` and
pushed to `master`.

*Also fixed, not asked for:* the repo-local git identity was
`attest build <build@attest.local>` — a name that is on this project's own
rejected-names list.  Set back to `falsifiable build <build@falsifiable.local>`
and the unpushed commit was re-authored (no published history was rewritten).



---

## Stage 2 / reviewer follow-up — the declared target and the payout fix

**The reviewer was right about the central defect.**  The shipped contract
settled the position and incremented `total_paid` *before* it emitted the
transfer.  On the target network the internal-message route to an EOA is a
silent no-op, so the ledger could claim "paid" for money that never arrived.
Documenting that was not enough; it is fixed.

**What the network actually is.**  The announcement was chain **61997**
"Studio dev preview".  `https://studio-next.genlayer.com/api` and
`https://studio-dev.genlayer.com/api` are the same deployment (identical
genesis, lockstep blocks); the canonical name is `studio-dev`, and the config
uses it.  The old README named 61999, which was the previous deployment.

**Toolchain.**  The target speaks the Consensus v0.6 fee envelope.  It needs
`genlayer-py==0.19.0rc2` / `genlayer-test==0.30.0rc2`; the original `.venv`
(SDK 0.16.3) cannot even load the new contract ("unexpected end of memory"),
and the RC venv cannot load the old one.  The RC toolchain therefore lives in
`requirements-rc.txt` and a separate `.venv-rc`; the pinned `.venv` was not
upgraded.  Fees had to be supplied explicitly: without the live policy the
deploy fails `FeesDistributionMissing`, and a non-zero `totalMessageFees`
without an allocation tree fails `Mode1MessageFeesRequireGenVMPerEmissionSupport`.
The working preset is `{leaderTimeunitsAllocation: 100,
validatorTimeunitsAllocation: 200, totalMessageFees: 0, rotations: [1]}`.

**Three-direction probe on 61997** (contract `0xd963…0004`):

| direction | result |
|---|---|
| EOA -> contract, 5 GEN | delivered, contract balance +5 |
| contract -> contract | delivered, child tx `value_credited=true` |
| contract -> EOA via internal message (`get_at`) | main tx `FINISHED_WITH_RETURN`, **no child tx**, EOA unchanged, contract unchanged, state advanced — silent no-op |
| contract -> EOA via EVM external message | EOA **+3 GEN**, contract **-3 GEN** |
| EVM send larger than the balance | `FINISHED_WITH_ERROR`, state rolled back, EOA unchanged |

**Chosen mechanism.**  `@gl.evm.contract_interface` + `emit_transfer` for
transport, and two-phase settlement: `withdraw` records a pending claim and
emits, `confirm_delivery` (payee only) settles and books.  A second claim while
pending is refused; a replay of the confirmation is refused; `total_paid` is
bounded by `total_staked`.  If delivery silently fails, the claim stays pending
and is never counted as paid — the contract will not re-emit, because a re-send
could pay twice.  That limit is stated in the README.  Design:
`state/DESIGN-payout.md`.

**Stage A.**  `state/REVIEW-FIX.md`: exact `withdraw()` lines 555–562 of the
old contract, the declared-vs-probed network table, every CLI read/write and
its address/network source, and every hard-coded/stale address.

**Red then green.**  On the old contract under the old `.venv`,
`tests/test_payout.py` fails with `settled_yes moved before delivery was
confirmed` / `assert 10000000000000000000 == 0` (7 failed, 2 passed).  On the
ported contract under `.venv-rc`: **96 passed, 0 failed, 0 skipped**.

**Deployment.**  `scripts/deploy.py --write-config` deployed once to
`0xA62952F70354355d2915ee2aC66B91effcF3a6cB` (tx `0x4fcd703f…`), and
`gen_getContractCode` read back byte-for-byte identical to
`contracts/falsifiable.py` (sha256 `a024fe20…`, 26995 bytes).  The single
config `web/config/chain.json` now points at it.

**Live lifecycle, CLI only.**  Market 2: create, stake YES 10, stake NO 4,
close, resolve YES, withdraw, confirm-delivery.  At pinned block `1792703185`
the payee EOA was **+13.999873695 GEN** (14 GEN minus the 0.000126305 GEN tx
fee) and the contract was **−14 GEN**; after the withdraw the position read
`settled_yes = 0`, `pending = 14 GEN`, `total_paid` unchanged.  A second
withdraw and a loser's withdraw both ended `FINISHED_WITH_ERROR`.  All ids in
`state/LIVE-RESULTS-61997.md`.

**Three bugs found while running it live, all fixed.**  `deploy.py` funded
accounts with `1000` wei instead of `1000 GEN`; the RC SDK requires a signer
even for view calls, so read-only commands now use a fresh in-memory key that
is never printed or persisted; and the web's `gen_call` envelope keyed the
method name as `"method"`, which the target rejects with `malformed_entry` —
the Python SDK keys it under the empty string (`make_calldata_object`).  The
first production Vercel build exposed the third one; `web/lib/chain.test.ts`
now pins the envelope against SDK-produced byte vectors.  A 90-second market
window was also too short for finality; the run uses 300 seconds.
