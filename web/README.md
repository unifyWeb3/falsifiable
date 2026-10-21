# Falsifiable — the web front end

A read-only front end for the Falsifiable stake market. It reads the
GenLayer Studio chain over the public JSON-RPC endpoint and it **cannot
write**: there is no key anywhere in this directory, and the configuration is
public (`NEXT_PUBLIC_` variables only).

## Run it

```bash
cp .env.example .env.local     # then set the contract address
npm install
npm run dev
```

## What it does

* **The board** (`/`) — every market, its status, its pool split and its
  countdown.
* **A market** (`/market/<id>`) — the claim, the rule in full, the page, the
  recorded evidence digest, the pool, and the actions the contract will
  accept.
* **Open a market** (`/open`) — builds the command that opens one.
* **Trust** (`/trust`) — what is promised and what is still trusted.

Every write is handed to you as a copy-paste command to run with your own
key. The site never sees a key and cannot move your money.

## The one rule about actions

The interface may only offer an action the contract will accept. That list
comes from a single pure function, `deriveActions` in
[`lib/market-state.ts`](lib/market-state.ts), and
[`lib/market-state.test.ts`](lib/market-state.test.ts) parses
`../contracts/falsifiable.py` and asserts the two agree — so the UI and the
contract cannot drift apart.

```bash
npx tsx --test lib/market-state.test.ts
```

## Reading the chain

The calldata codec in [`lib/calldata.ts`](lib/calldata.ts) and the RLP
encoder in [`lib/rlp.ts`](lib/rlp.ts) are a direct port of the GenLayer
Python SDK's encoding, so the app can call `gen_call` with nothing more than
`fetch`. There is no SDK dependency and no server-side key.

If the public configuration is missing, the app **fails closed**: it says
the chain is unreachable instead of pretending it is empty.
