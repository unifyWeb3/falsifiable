/**
 * Minimal RLP encoder — just enough to serialise a GenLayer read call.
 *
 * The Python SDK sends `rlp.encode([calldata_bytes, b"\x00"])` as the `data`
 * field of a `gen_call` request.
 */

function encodeBytes(bytes: Uint8Array): Uint8Array {
  if (bytes.length === 1 && bytes[0] < 0x80) return bytes;
  // A byte string longer than 55 bytes needs the long form: 0xb8 <len>.
  // Using the short form above 55 produces a prefix that reads as a list.
  const header = encodeLength(bytes.length, 0x80);
  const out = new Uint8Array(header.length + bytes.length);
  out.set(header, 0);
  out.set(bytes, header.length);
  return out;
}

function encodeLength(length: number, offset: number): Uint8Array {
  if (length < 56) return Uint8Array.from([offset + length]);
  const lengthBytes: number[] = [];
  let value = length;
  while (value > 0) {
    lengthBytes.unshift(value & 0xff);
    value >>= 8;
  }
  const out = new Uint8Array(1 + lengthBytes.length);
  out[0] = offset + 55 + lengthBytes.length;
  out.set(Uint8Array.from(lengthBytes), 1);
  return out;
}

export function rlpEncodeList(items: Uint8Array[]): Uint8Array {
  const encoded = items.map(encodeBytes);
  const payloadLength = encoded.reduce((sum, item) => sum + item.length, 0);
  const header = encodeLength(payloadLength, 0xc0);
  const out = new Uint8Array(header.length + payloadLength);
  out.set(header, 0);
  let offset = header.length;
  for (const item of encoded) {
    out.set(item, offset);
    offset += item.length;
  }
  return out;
}
