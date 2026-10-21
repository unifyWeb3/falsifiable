/**
 * GenLayer calldata codec.
 *
 * This is a direct port of the encoding used by the GenLayer Python SDK
 * (`genlayer_py.abi.calldata`).  It is a self-describing binary format:
 * a 3-bit type tag plus a ULEB128 payload.
 *
 * The web app uses it to read the contract over the public JSON-RPC endpoint
 * with `gen_call`.  It never signs anything.
 */

export const TYPE_SPECIAL = 0;
export const TYPE_PINT = 1;
export const TYPE_NINT = 2;
export const TYPE_BYTES = 3;
export const TYPE_STR = 4;
export const TYPE_ARR = 5;
export const TYPE_MAP = 6;

export const SPECIAL_NULL = 0;
export const SPECIAL_FALSE = 1;
export const SPECIAL_TRUE = 2;
export const SPECIAL_ADDR = 3;

export type CalldataValue =
  | null
  | boolean
  | bigint
  | Uint8Array
  | string
  | CalldataValue[]
  | { [key: string]: CalldataValue };

function uleb128(value: number | bigint): number[] {
  let i = typeof value === "bigint" ? value : BigInt(value);
  if (i < 0n) throw new Error("cannot encode a negative uleb128");
  const out: number[] = [];
  if (i === 0n) return [0];
  while (i > 0n) {
    let cur = Number(i & 0x7fn);
    i >>= 7n;
    if (i > 0n) cur |= 0x80;
    out.push(cur);
  }
  return out;
}

export function encodeCalldata(value: CalldataValue): Uint8Array {
  const mem: number[] = [];

  const impl = (v: CalldataValue): void => {
    if (v === null) {
      mem.push(SPECIAL_NULL);
    } else if (v === true) {
      mem.push(SPECIAL_TRUE);
    } else if (v === false) {
      mem.push(SPECIAL_FALSE);
    } else if (typeof v === "bigint" || typeof v === "number") {
      let n = typeof v === "bigint" ? v : BigInt(v);
      if (n >= 0n) {
        mem.push(...uleb128(n << 3n | BigInt(TYPE_PINT)));
      } else {
        const magnitude = -n - 1n;
        mem.push(...uleb128(magnitude << 3n | BigInt(TYPE_NINT)));
      }
    } else if (v instanceof Uint8Array) {
      mem.push(...uleb128((BigInt(v.length) << 3n) | BigInt(TYPE_BYTES)));
      mem.push(...v);
    } else if (typeof v === "string") {
      const bytes = new TextEncoder().encode(v);
      mem.push(...uleb128((BigInt(bytes.length) << 3n) | BigInt(TYPE_STR)));
      mem.push(...bytes);
    } else if (Array.isArray(v)) {
      mem.push(...uleb128((BigInt(v.length) << 3n) | BigInt(TYPE_ARR)));
      for (const item of v) impl(item);
    } else if (typeof v === "object") {
      const keys = Object.keys(v).sort();
      mem.push(...uleb128((BigInt(keys.length) << 3n) | BigInt(TYPE_MAP)));
      for (const key of keys) {
        const keyBytes = new TextEncoder().encode(key);
        mem.push(...uleb128(keyBytes.length));
        mem.push(...keyBytes);
        impl(v[key]);
      }
    } else {
      throw new Error(`cannot encode ${typeof v}`);
    }
  };

  impl(value);
  return Uint8Array.from(mem);
}

class Reader {
  private offset = 0;
  constructor(private readonly buf: Uint8Array) {}

  get remaining(): number {
    return this.buf.length - this.offset;
  }

  byte(): number {
    if (this.offset >= this.buf.length) throw new Error("calldata: out of bytes");
    return this.buf[this.offset++];
  }

  take(n: number): Uint8Array {
    if (this.offset + n > this.buf.length) throw new Error("calldata: truncated");
    const out = this.buf.slice(this.offset, this.offset + n);
    this.offset += n;
    return out;
  }

  uleb128(): bigint {
    let result = 0n;
    let shift = 0n;
    for (;;) {
      const byte = this.byte();
      result |= BigInt(byte & 0x7f) << shift;
      shift += 7n;
      if ((byte & 0x80) === 0) break;
    }
    return result;
  }
}

export function decodeCalldata(bytes: Uint8Array): CalldataValue {
  const reader = new Reader(bytes);

  const impl = (): CalldataValue => {
    const code = reader.uleb128();
    const type = Number(code & 7n);
    if (type === TYPE_SPECIAL) {
      const special = Number(code);
      if (special === SPECIAL_NULL) return null;
      if (special === SPECIAL_FALSE) return false;
      if (special === SPECIAL_TRUE) return true;
      if (special === SPECIAL_ADDR) return "0x" + toHex(reader.take(20));
      throw new Error(`calldata: unknown special ${code}`);
    }
    const payload = code >> 3n;
    switch (type) {
      case TYPE_PINT:
        return payload;
      case TYPE_NINT:
        return -payload - 1n;
      case TYPE_BYTES:
        return reader.take(Number(payload));
      case TYPE_STR:
        return new TextDecoder().decode(reader.take(Number(payload)));
      case TYPE_ARR: {
        const out: CalldataValue[] = [];
        for (let i = 0n; i < payload; i += 1n) out.push(impl());
        return out;
      }
      case TYPE_MAP: {
        const out: { [key: string]: CalldataValue } = {};
        for (let i = 0n; i < payload; i += 1n) {
          const keyLength = Number(reader.uleb128());
          const key = new TextDecoder().decode(reader.take(keyLength));
          out[key] = impl();
        }
        return out;
      }
      default:
        throw new Error(`calldata: unknown type ${type}`);
    }
  };

  const value = impl();
  if (reader.remaining !== 0) {
    throw new Error(`calldata: ${reader.remaining} trailing bytes`);
  }
  return value;
}

export function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const byte of bytes) out += byte.toString(16).padStart(2, "0");
  return out;
}

export function fromHex(hex: string): Uint8Array {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  if (clean.length % 2 !== 0) throw new Error("hex must have an even length");
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}
