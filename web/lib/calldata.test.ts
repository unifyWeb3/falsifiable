/**
 * The calldata codec must match the GenLayer Python SDK byte for byte.
 *
 * These fixtures were produced by the SDK itself:
 *
 *   from genlayer_py.abi import calldata
 *   from genlayer_py.abi.transactions import serialize
 *   from genlayer_py.contracts.utils import make_calldata_object
 *   serialize([calldata.encode(make_calldata_object(method=..., args=...)), b"\x00"])
 *
 * A mismatch is not a cosmetic problem: the node rejects a call whose
 * object carries an empty `kwargs` map, so `get_position` failed while
 * `get_market` did not.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { encodeCalldata, toHex } from "./calldata";
import { rlpEncodeList } from "./rlp";

/** The SDK's `make_calldata_object`: no `kwargs` key when it is empty. */
function sdkCall(method: string, args: (bigint | string)[] = []) {
  const call: { method: string; args?: (bigint | string)[] } = { method };
  if (args.length > 0) call.args = args;
  return encodeCalldata(call as never);
}

function sdkRequest(method: string, args: (bigint | string)[] = []): string {
  return "0x" + toHex(rlpEncodeList([sdkCall(method, args), Uint8Array.from([0])]));
}

const FIXTURES: {
  name: string;
  method: string;
  args: (bigint | string)[];
  bytes: string;
}[] = [
  {
    name: "get_market_count",
    method: "get_market_count",
    args: [],
    bytes:
      "0xdc9a0e066d6574686f6484016765745f6d61726b65745f636f756e7400",
  },
  {
    name: "get_market",
    method: "get_market",
    args: [5n],
    bytes:
      "0xdc9a1604617267730d29066d6574686f64546765745f6d61726b657400",
  },
  {
    name: "get_position",
    method: "get_position",
    args: [5n, "0x191489309397a77e4d6De1d91Ae6B21647F54F72"],
    bytes:
      "0xf84bb8481604617267731529d402307831393134383933303933393761373765346436446531643931416536423231363437463534463732066d6574686f64646765745f706f736974696f6e00",
  },
  {
    name: "get_payout_preview",
    method: "get_payout_preview",
    args: [5n, "0x191489309397a77e4d6De1d91Ae6B21647F54F72"],
    bytes:
      "0xf852b84f1604617267731529d402307831393134383933303933393761373765346436446531643931416536423231363437463534463732066d6574686f6494016765745f7061796f75745f7072657669657700",
  },
];

for (const fixture of FIXTURES) {
  test(`the encoding of ${fixture.name} matches the SDK`, () => {
    assert.equal(sdkRequest(fixture.method, fixture.args), fixture.bytes);
  });
}

test("the call this app sends never carries an empty kwargs map", () => {
  const good = sdkRequest("get_position", [
    5n,
    "0x191489309397a77e4d6De1d91Ae6B21647F54F72",
  ]);
  assert.ok(!good.includes("6b7761726773"), "the word kwargs was sent");

  // The same call, built the wrong way, is a different request — and the
  // node rejects it.
  const bad = "0x" + toHex(
    rlpEncodeList([
      encodeCalldata({
        method: "get_position",
        args: [5n, "0x191489309397a77e4d6De1d91Ae6B21647F54F72"],
        kwargs: {},
      } as never),
      Uint8Array.from([0]),
    ]),
  );
  assert.ok(bad.includes("6b7761726773"), "the bad request should carry kwargs");
  assert.notEqual(bad, good);
});
