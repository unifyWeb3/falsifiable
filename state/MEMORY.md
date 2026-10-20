# Attest — decision log / session memory

> Resume instructions: read this file top to bottom, then `state/DESIGN.md`, then
> `git log --oneline`. Every hard-won fact below is marked `[VERIFIED]` only when a
> command was actually run and its output observed.

---

## 0. Product frame

**Attest** — a stake market on *checkable claims about a public web page*.

- One market = one `https://` URL + one precisely-worded claim about what that page
  will say/show at a fixed close time.
- Anyone stakes native GEN on YES or NO.
- At close, validators independently fetch the page and decide YES / NO /
  UNDETERMINED under the market's own written rule (closed set, never free text).
- Whole pot split pro rata among the winning side. UNDETERMINED refunds everyone.
  Single-sided pool refunds.
- Winnings and refunds are **pulled** through a safe withdraw; never pushed.
- Not escrow, not arbitration, not a court. No appeals, no fees, no admin payouts.

Name: `attest` (one word). Chosen because validators *attest* to a claim.
Rejected: `verdict` (too close to "court/arbitration" framing), `fathom`
(vague), `exegesis` (obscure, academic), `colophon` (obscure), `scry`
(well-known Ruby static-analysis tool), `augur` (well-known project), `oracle`
(too generic, and the thing being checked is a page not a price feed).
GitHub availability under `unifyWeb3` was checked via API for every candidate:
all returned 404 (free) at the time of writing.

---

## 1. Environment facts [VERIFIED]

- Repo root: `/root/market-build`. Python venv at `.venv` (python 3.12).
- `git` initialised, `user.email=build@attest.local`.
- `gh` authenticated as **unifyWeb3** (scopes: gist, read:org, repo, workflow).
- `vercel` authenticated as **oxunifyy**.
- Studio RPC: `https://studio.genlayer.com/api/rpc` (chain id 61999 / `0xf22f`).
  `genlayer_py.chains.studionet` hardcodes `https://studio.genlayer.com/api`.
- Network egress is **intermittent**: DNS for `studio.genlayer.com` intermittently
  fails with `Temporary failure in name resolution`. → `scripts/studio.py` wraps
  the provider in `ResilientProvider` (6 attempts, 2 s backoff) and only retries
  *transport* failures, never JSON-RPC-level errors.
- Chromium: `/root/.config/google-chrome-for-testing` + `/root/browser-tool`
  (puppeteer) are installed and were used for UI verification.
- Skills are installed under `/root/arc-skills` (read before building the UI).

### Tools

| tool | version | notes |
|---|---|---|
| `genvm-lint` | 0.10.0 | `lint` works; `check` (validate) needs SDK |
| `genlayer-test` (gltest) | upgraded 0.28.0 → **0.29.2** | 0.29.2 still expects `genvm-universal.tar.xz` |
| `genlayer-py` | 0.9.0 → **0.16.3** | pulled in by gltest upgrade |
| node / npm | v22.22.1 | |

---

## 2. GenLayer facts learned from source (not memory)

### 2.1 Which GenVM does the hosted Studio run? [VERIFIED]

`gen_getContractSchemaForCode` on a v0.3.0-style contract returned a
`genvm_log` entry:

```
'version': 'v0.2.16-x86_64-linux-release'
```

→ **The hosted Studio runs GenVM v0.2.16.**
The v0.3.0 contract header/API (used by the Studio *repo*'s example contracts)
is **rejected** by the hosted node. The v0.3.0 release also renamed the runner
bundle from `genvm-universal.tar.xz` to `genvm-runners-all.tar.xz`.

### 2.2 Contract source format [VERIFIED]

A contract MUST start with a runner comment. Without it the node rejects the
deploy with `invalid_contract absent_runner_comment` (observed in the leader
receipt of a real deploy tx).

For v0.2.16 the header is:

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

(the hash is the `py-genlayer` runner content hash inside
`genvm-universal-v0.2.16.tar.xz`).

`genvm-lint lint` warns `W010 Missing contract dependency header` when it is
absent, and `W011` if `py-genlayer:` is not mentioned.

**Fast validation loop (no deploy needed):**
`gen_getContractSchemaForCode` on the Studio RPC compiles the contract and
returns its ABI. Use this on every edit before deploying.

### 2.3 `genvm-lint check` 404s on `genvm-universal.tar.xz` [VERIFIED]

Exact output:

```
$ .venv/bin/genvm-lint check contracts/probe_value.py
✓ Lint passed (2 checks)
  Warnings:
    line 1: Missing contract dependency header (# { "Seq": [...] })
✗ Validation failed
  Failed to load SDK: HTTP Error 404: Not Found
```

Cause: `genvm_linter/validate/artifacts.py` resolves "latest" via a HEAD to
`https://github.com/genlayerlabs/genvm/releases/latest`, which now redirects to
`v0.3.0-rc7`, whose assets are named `genvm-runners-all.tar.xz` — there is no
`genvm-universal.tar.xz`, so the download 404s. Confirmed independently:

```
$ curl -o /dev/null -w "%{http_code}" -L https://github.com/genlayerlabs/genvm/releases/latest/download/genvm-universal.tar.xz
404
```

**Supported alternative that passes:** set `GENVMROOT` to a directory laid out
like the Studio's GenVM root, i.e. containing `runners/genlayer-py-std/src` or
`runners/py-lib-genlayer-std/src`. `genvm_linter/validate/sdk_loader.py`
(`get_sdk_paths_from_genvmroot`) checks `GENVMROOT` **before** it tries to
download, so no 404 happens.

---

## 3. Live Studio RPC notes [VERIFIED]

- `sim_fundAccount` takes **flat positional params**: `params: [account, amount]`
  with `amount` an **int** (not a string). `params: [{account, amount}]` fails with
  `Missing required parameter: amount`. Returns a tx hash.
- `eth_getBalance` works for EOAs.
- `gen_getContractCode` / `gen_call` need the contract to actually be stored; a
  deploy whose leader receipt is `ERROR` leaves nothing stored, and the node then
  answers `Contract <addr> not found` (this is what a rejected contract looks
  like from the outside).
- `genlayer_py.read_contract` needs a `TransactionHashVariant` **enum**, not a
  string (a string raises `'str' object has no attribute 'value'`).
- A deploy tx can report `status_name=FINALIZED, result_name=MAJORITY_AGREE`
  while the *contract* was invalid. Always read `consensus_data.leader_receipt`
  and the `result.raw` base64 payload, not just the status.

---

## 4. Money model (decision)

Native GEN is attached to a payable method call; the contract credits the
sender's position from `gl.message.value` only — it never trusts a caller
supplied amount. Payouts are **pulled**: a winner calls `withdraw`, the
contract computes the pro-rata share, zeroes the position **before** the
transfer, and emits the transfer. See `state/DESIGN.md`.

---

## 5. Open items / next steps

- [ ] Confirm attached value actually lands in the contract on Studionet
      (probe running: `scripts/probe_value_run.py`).
- [ ] Confirm a contract can pay value OUT to an EOA.
- [ ] Write `state/DESIGN.md` (states, resolution rule, money model, red team).
- [ ] Build + test the real contract, then the Next.js UI, then deploy, then
      push to GitHub + Vercel.
