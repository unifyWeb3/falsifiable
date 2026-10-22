/**
 * The call envelope must match the Python SDK byte for byte.
 *
 * The declared target rejects anything else with `malformed_entry`, so these
 * vectors were produced by the release-candidate SDK's own encoder
 * (`genlayer_py.abi.calldata.encode(make_calldata_object(...))`).  The live
 * board failed on the old `{"method": ...}` shape; this test is why.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { encodeCall } from "./chain";
import { toHex } from "./calldata";
import { rlpEncodeList } from "./rlp";

test("a no-argument call matches the Python SDK", () => {
  assert.equal(
    toHex(encodeCall("get_market_count")),
    "0e0084016765745f6d61726b65745f636f756e74",
  );
});

test("a call with integer arguments matches the Python SDK", () => {
  assert.equal(
    toHex(encodeCall("get_market", [2n])),
    "1600546765745f6d61726b657404617267730d11",
  );
});

test("a call with an address argument matches the Python SDK", () => {
  assert.equal(
    toHex(
      encodeCall("get_position", [
        2n,
        "0x51c93D73ddF63DbCA23505d0602514Ad1da41328",
      ]),
    ),
    "1600646765745f706f736974696f6e04617267731511d402307835316339334437336464463633446243413233353035643036303235313441643164613431333238",
  );
});

test("the serialized read envelope is the calldata followed by a zero byte", () => {
  assert.equal(
    "0x" +
      toHex(
        rlpEncodeList([encodeCall("get_market_count"), Uint8Array.from([0])]),
      ),
    "0xd6940e0084016765745f6d61726b65745f636f756e7400",
  );
});
