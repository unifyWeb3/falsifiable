/**
 * The UI and the contract must not drift apart.
 *
 * This test parses `contracts/falsifiable.py` — the deployed source of truth —
 * and asserts that:
 *
 *   1. the status constants in the web app match the contract's, by name and
 *      by number, with no extras and none missing;
 *   2. for every status, the actions `deriveActions` offers are exactly the
 *      actions the contract's guards accept.
 *
 * A refusal without a positive control proves nothing, so the test also
 * checks, for every action, that there is at least one status where the
 * action is offered *and* at least one where it is not.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  MARKET_STATUS,
  RESOLVED_STATUSES,
  deriveActions,
} from "./market-state";

const CONTRACT_PATH = path.resolve(
  process.cwd(),
  "..",
  "contracts",
  "falsifiable.py",
);

const source = readFileSync(CONTRACT_PATH, "utf-8");

/** The `STATUS_*` constants, parsed out of the contract source. */
function parseStatuses(): Map<string, number> {
  const found = new Map<string, number>();
  const pattern = /^(STATUS_[A-Z_]+)\s*=\s*(\d+)\s*$/gm;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(source)) !== null) {
    found.set(match[1], Number(match[2]));
  }
  return found;
}

/** The body of one contract method, as a list of source lines. */
function methodBody(name: string): string[] {
  const lines = source.split("\n");
  const startIndex = lines.findIndex((line) =>
    new RegExp(`^\\s*def ${name}\\(`).test(line),
  );
  assert.ok(startIndex > -1, `method ${name} not found in the contract source`);
  const indent = lines[startIndex].length - lines[startIndex].trimStart().length;

  const body: string[] = [];
  for (let i = startIndex + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.trim() === "") {
      body.push(line);
      continue;
    }
    const lineIndent = line.length - line.trimStart().length;
    if (lineIndent <= indent) break; // the next member of the class
    body.push(line);
  }
  return body;
}

/**
 * The `if` conditions inside a method, with multi-line conditions joined.
 */
function guardConditions(method: string): string[] {
  const guards: string[] = [];
  let current: string | null = null;
  for (const line of methodBody(method)) {
    const trimmed = line.trim();
    if (current === null) {
      if (trimmed.startsWith("if ")) current = trimmed;
      continue;
    }
    current += " " + trimmed;
    if (trimmed.endsWith(":")) {
      guards.push(current);
      current = null;
    }
  }
  return guards;
}

/**
 * The statuses a guard accepts.
 *
 * `!=` means "only this status"; `==` and `not in` mean "these statuses".
 */
function statusesAcceptedBy(method: string): Set<string> {
  const accepted = new Set<string>();
  for (const guard of guardConditions(method)) {
    if (!guard.includes("status")) continue;
    if (guard.includes("!=")) {
      const name = /STATUS_[A-Z_]+/.exec(guard)?.[0];
      if (name) accepted.add(name);
    } else if (guard.includes("==") || guard.includes("not in")) {
      for (const name of guard.match(/STATUS_[A-Z_]+/g) ?? []) {
        accepted.add(name);
      }
    }
  }
  return accepted;
}

const contractStatuses = parseStatuses();

test("the contract defines the statuses the web app knows about", () => {
  assert.ok(
    contractStatuses.size >= 5,
    "the contract should define the statuses",
  );
  const uiEntries = Object.entries(MARKET_STATUS);
  assert.equal(
    uiEntries.length,
    contractStatuses.size,
    "the web app and the contract disagree on how many statuses there are",
  );
  for (const [name, value] of uiEntries) {
    assert.equal(
      contractStatuses.get(`STATUS_${name}`),
      value,
      `status ${name} differs between the contract and the web app`,
    );
  }
});

test("every status has a name in the web app", () => {
  for (const [name, value] of contractStatuses) {
    assert.equal(
      MARKET_STATUS[name.replace("STATUS_", "") as keyof typeof MARKET_STATUS],
      value,
      `status ${name} is missing from the web app`,
    );
  }
});

test("the resolved statuses are exactly the ones the contract can pay out", () => {
  const withdrawable = statusesAcceptedBy("withdraw");
  const expected = new Set(
    [...withdrawable].map((name) => contractStatuses.get(name) as number),
  );
  assert.deepEqual(new Set(RESOLVED_STATUSES), expected);
});

test("stake is offered for exactly the statuses the contract accepts", () => {
  const accepted = statusesAcceptedBy("stake");
  assert.equal(accepted.size, 1, "stake should be guarded by a single status");
  const status = contractStatuses.get([...accepted][0]) as number;
  const others = [...contractStatuses.values()].filter(
    (value) => value !== status,
  );

  // Positive control: the accepted status offers staking before the close.
  assert.equal(
    deriveActions({ status, now: 100, closeTime: 200, payoutPreview: 0n })
      .canStake,
    true,
  );
  // And every other status refuses.
  for (const other of others) {
    assert.equal(
      deriveActions({
        status: other,
        now: 100,
        closeTime: 200,
        payoutPreview: 0n,
      }).canStake,
      false,
      `status ${other} must not offer staking`,
    );
  }
  // A closed market refuses too.
  assert.equal(
    deriveActions({ status, now: 200, closeTime: 200, payoutPreview: 0n })
      .canStake,
    false,
  );
});

test("close is offered for exactly the statuses the contract accepts", () => {
  const accepted = statusesAcceptedBy("close_market");
  const status = contractStatuses.get([...accepted][0]) as number;
  // Positive control: after the close time.
  assert.equal(
    deriveActions({ status, now: 200, closeTime: 200, payoutPreview: 0n })
      .canClose,
    true,
  );
  // Negative control: before the close time.
  assert.equal(
    deriveActions({ status, now: 100, closeTime: 200, payoutPreview: 0n })
      .canClose,
    false,
  );
  // And no other status offers it.
  for (const [name, value] of contractStatuses) {
    if (value === status) continue;
    assert.equal(
      deriveActions({
        status: value,
        now: 200,
        closeTime: 200,
        payoutPreview: 0n,
      }).canClose,
      false,
      `status ${name} must not offer closing`,
    );
  }
});

test("resolve is offered for exactly the statuses the contract accepts", () => {
  const accepted = statusesAcceptedBy("resolve");
  const statuses = [...accepted].map(
    (name) => contractStatuses.get(name) as number,
  );
  for (const status of statuses) {
    assert.equal(
      deriveActions({ status, now: 200, closeTime: 200, payoutPreview: 0n })
        .canResolve,
      true,
    );
  }
  for (const [name, value] of contractStatuses) {
    if (statuses.includes(value)) continue;
    assert.equal(
      deriveActions({
        status: value,
        now: 200,
        closeTime: 200,
        payoutPreview: 0n,
      }).canResolve,
      false,
      `status ${name} must not offer resolving`,
    );
  }
});

test("withdraw is offered for exactly the statuses the contract accepts", () => {
  const accepted = statusesAcceptedBy("withdraw");
  const statuses = [...accepted].map(
    (name) => contractStatuses.get(name) as number,
  );
  for (const status of statuses) {
    // Positive control: the caller is owed something.
    assert.equal(
      deriveActions({ status, now: 200, closeTime: 200, payoutPreview: 1n })
        .canWithdraw,
      true,
    );
    // Negative control: the caller is owed nothing.
    assert.equal(
      deriveActions({ status, now: 200, closeTime: 200, payoutPreview: 0n })
        .canWithdraw,
      false,
    );
  }
  for (const [name, value] of contractStatuses) {
    if (statuses.includes(value)) continue;
    assert.equal(
      deriveActions({
        status: value,
        now: 200,
        closeTime: 200,
        payoutPreview: 1n,
      }).canWithdraw,
      false,
      `status ${name} must not offer withdrawing`,
    );
  }
});

test("every action has both a positive and a negative case", () => {
  const all = [...contractStatuses.values()];
  const beforeClose = (status: number, payoutPreview = 0n) =>
    deriveActions({ status, now: 100, closeTime: 200, payoutPreview });
  const afterClose = (status: number, payoutPreview = 0n) =>
    deriveActions({ status, now: 500, closeTime: 200, payoutPreview });

  for (const key of ["canStake", "canClose", "canResolve", "canWithdraw"] as const) {
    const offered = all.some(
      (status) => beforeClose(status, 1n)[key] || afterClose(status, 1n)[key],
    );
    const refused = all.some(
      (status) => !beforeClose(status, 1n)[key] && !afterClose(status, 1n)[key],
    );
    assert.ok(
      offered,
      `${key} is never offered: the test would pass for the wrong reason`,
    );
    assert.ok(
      refused,
      `${key} is always offered: the test would pass for the wrong reason`,
    );
  }
});
