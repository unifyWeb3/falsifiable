/**
 * Read-only access to the deployed Falsifiable contract over the public
 * GenLayer Studio JSON-RPC endpoint.
 *
 * Fail-closed: if the public configuration is missing, every call throws a
 * `ConfigError` instead of silently pretending the chain is empty.  There is
 * no key material in this file or anywhere else in `web/` — the app can only
 * read.  Writes are copy-paste commands you run with your own key.
 */

import { decodeCalldata, encodeCalldata, fromHex, toHex, type CalldataValue } from "./calldata";
import { rlpEncodeList } from "./rlp";

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

export class RpcError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RpcError";
  }
}

export function rpcUrl(): string {
  const value = process.env.NEXT_PUBLIC_STUDIONET_RPC;
  if (!value) {
    throw new ConfigError(
      "NEXT_PUBLIC_STUDIONET_RPC is not set. The app cannot read the chain.",
    );
  }
  return value;
}

export function contractAddress(): string {
  const value = process.env.NEXT_PUBLIC_FALSIFIABLE_CONTRACT;
  if (!value) {
    throw new ConfigError(
      "NEXT_PUBLIC_FALSIFIABLE_CONTRACT is not set. The app cannot read the contract.",
    );
  }
  if (!/^0x[0-9a-fA-F]{40}$/.test(value)) {
    throw new ConfigError(
      "NEXT_PUBLIC_FALSIFIABLE_CONTRACT is not a valid contract address.",
    );
  }
  return value;
}

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

async function rpc<T>(method: string, params: unknown[]): Promise<T> {
  let response: Response;
  try {
    response = await fetch(rpcUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      cache: "no-store",
    });
  } catch (error) {
    throw new RpcError(
      `could not reach the Studio RPC: ${(error as Error).message}`,
    );
  }
  if (!response.ok) {
    throw new RpcError(`the Studio RPC answered ${response.status}`);
  }
  const body = (await response.json()) as {
    result?: T;
    error?: { message?: string };
  };
  if (body.error) {
    throw new RpcError(body.error.message ?? "the Studio RPC returned an error");
  }
  return body.result as T;
}

/** Call a read method on the contract. */
export async function readContract(
  method: string,
  args: CalldataValue[] = [],
): Promise<CalldataValue> {
  // The object is built exactly the way the Python SDK builds it: `kwargs` is
  // omitted when it is empty, and the keys are sorted by the encoder.  The
  // node rejects the call if an empty `kwargs` map is included, so this must
  // match the SDK byte for byte.
  const call: { method: string; args?: CalldataValue[] } = { method };
  if (args.length > 0) call.args = args;
  const payload = encodeCalldata(call as unknown as CalldataValue);
  const serialized = rlpEncodeList([payload, Uint8Array.from([0])]);
  const result = await rpc<string>("gen_call", [
    {
      type: "read",
      to: contractAddress(),
      from: ZERO_ADDRESS,
      data: "0x" + toHex(serialized),
      transaction_hash_variant: "latest-final",
    },
  ]);
  if (typeof result !== "string") {
    throw new RpcError("the Studio RPC returned an unexpected read result");
  }
  try {
    return decodeCalldata(fromHex(result));
  } catch (error) {
    throw new RpcError(
      `could not decode the contract answer: ${(error as Error).message}`,
    );
  }
}

export type TransactionState = {
  txId: string;
  status: string;
  result: string;
  present: boolean;
};

/** Look up a transaction by id.  Used by the transaction tracker. */
export async function getTransaction(txId: string): Promise<TransactionState> {
  const raw = await rpc<{
    status?: string | number;
    status_name?: string;
    result?: string | number;
    result_name?: string;
  } | null>("eth_getTransactionByHash", [txId]);
  if (!raw) {
    return { txId, status: "UNKNOWN", result: "UNKNOWN", present: false };
  }
  return {
    txId,
    status: raw.status_name ?? normaliseStatus(raw.status),
    result: raw.result_name ?? normaliseResult(raw.result),
    present: true,
  };
}

const STATUS_NAMES: Record<string, string> = {
  "0": "UNINITIALIZED",
  "1": "PENDING",
  "2": "PROPOSING",
  "3": "COMMITTING",
  "4": "REVEALING",
  "5": "ACCEPTED",
  "6": "UNDETERMINED",
  "7": "FINALIZED",
  "8": "CANCELED",
  "9": "APPEAL_REVEALING",
  "10": "APPEAL_COMMITTING",
  "11": "READY_TO_FINALIZE",
  "12": "VALIDATORS_TIMEOUT",
  "13": "LEADER_TIMEOUT",
};

const RESULT_NAMES: Record<string, string> = {
  "0": "IDLE",
  "1": "AGREE",
  "2": "DISAGREE",
  "3": "TIMEOUT",
  "4": "DETERMINISTIC_VIOLATION",
  "5": "NO_MAJORITY",
  "6": "MAJORITY_AGREE",
  "7": "MAJORITY_DISAGREE",
};

function normaliseStatus(value: string | number | undefined): string {
  if (value === undefined) return "UNKNOWN";
  const asString = String(value);
  return STATUS_NAMES[asString] ?? asString;
}

function normaliseResult(value: string | number | undefined): string {
  if (value === undefined) return "UNKNOWN";
  const asString = String(value);
  return RESULT_NAMES[asString] ?? asString;
}
