/**
 * Typed reads of the Falsifiable contract.
 *
 * Bigints do not survive the React server/client boundary, so every amount
 * crosses the wire as a decimal string and is parsed back on the other side.
 */

import { readContract } from "./chain";
import type { CalldataValue } from "./calldata";

export type Market = {
  id: number;
  creator: string;
  url: string;
  claim: string;
  ruleKind: number;
  ruleParam: string;
  rulePath: string;
  closeTime: number;
  status: number;
  ruleOutcome: number;
  potYes: string;
  potNo: string;
  payoutPot: string;
  evidenceDigest: string;
};

export type Position = {
  yes: string;
  no: string;
  settledYes: string;
  settledNo: string;
  pending: string;
};

export type MarketSummary = {
  id: number;
  url: string;
  claim: string;
  ruleKind: number;
  ruleParam: string;
  rulePath: string;
  closeTime: number;
  status: number;
  ruleOutcome: number;
  potYes: string;
  potNo: string;
  payoutPot: string;
  evidenceDigest: string;
};

function asArray(value: CalldataValue): CalldataValue[] {
  if (!Array.isArray(value)) {
    throw new Error("the contract returned an unexpected shape");
  }
  return value;
}

function asBigInt(value: CalldataValue): bigint {
  if (typeof value === "bigint") return value;
  if (typeof value === "number") return BigInt(value);
  if (typeof value === "string") return BigInt(value);
  throw new Error(`the contract returned ${typeof value} where a number was expected`);
}

function asText(value: CalldataValue): string {
  if (typeof value === "string") return value;
  if (value instanceof Uint8Array) return new TextDecoder().decode(value);
  throw new Error("the contract returned an unexpected shape");
}

function asNumber(value: CalldataValue): number {
  return Number(asBigInt(value));
}

export async function readMarketCount(): Promise<number> {
  return asNumber(await readContract("get_market_count"));
}

export async function readMarket(id: number): Promise<Market> {
  const raw = asArray(await readContract("get_market", [BigInt(id)]));
  const digest = raw[13];
  return {
    id: asNumber(raw[0]),
    creator: asText(raw[1]),
    url: asText(raw[2]),
    claim: asText(raw[3]),
    ruleKind: asNumber(raw[4]),
    ruleParam: asText(raw[5]),
    rulePath: asText(raw[6]),
    closeTime: asNumber(raw[7]),
    status: asNumber(raw[8]),
    ruleOutcome: asNumber(raw[9]),
    potYes: asBigInt(raw[10]).toString(),
    potNo: asBigInt(raw[11]).toString(),
    payoutPot: asBigInt(raw[12]).toString(),
    evidenceDigest:
      digest instanceof Uint8Array
        ? Array.from(digest)
            .map((byte) => byte.toString(16).padStart(2, "0"))
            .join("")
        : asText(digest),
  };
}

export async function readPosition(
  id: number,
  address: string,
): Promise<Position> {
  const [raw, pending] = await Promise.all([
    readContract("get_position", [BigInt(id), address]),
    readContract("get_pending", [BigInt(id), address]),
  ]);
  const fields = asArray(raw);
  return {
    yes: asBigInt(fields[0]).toString(),
    no: asBigInt(fields[1]).toString(),
    settledYes: asBigInt(fields[2]).toString(),
    settledNo: asBigInt(fields[3]).toString(),
    pending: asBigInt(pending).toString(),
  };
}

export async function readPayoutPreview(
  id: number,
  address: string,
): Promise<string> {
  const raw = await readContract("get_payout_preview", [BigInt(id), address]);
  return asBigInt(raw).toString();
}

export async function readTotals(): Promise<{ staked: string; paid: string }> {
  const raw = asArray(await readContract("get_totals"));
  return {
    staked: asBigInt(raw[0]).toString(),
    paid: asBigInt(raw[1]).toString(),
  };
}

export async function readMarketSummaries(
  limit = 50,
): Promise<MarketSummary[]> {
  const count = await readMarketCount();
  const total = Math.min(count, limit);
  const markets: MarketSummary[] = [];
  for (let id = 0; id < total; id += 1) {
    const market = await readMarket(id);
    markets.push({
      id: market.id,
      url: market.url,
      claim: market.claim,
      ruleKind: market.ruleKind,
      ruleParam: market.ruleParam,
      rulePath: market.rulePath,
      closeTime: market.closeTime,
      status: market.status,
      ruleOutcome: market.ruleOutcome,
      potYes: market.potYes,
      potNo: market.potNo,
      payoutPot: market.payoutPot,
      evidenceDigest: market.evidenceDigest,
    });
  }
  return markets;
}
