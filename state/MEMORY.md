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

