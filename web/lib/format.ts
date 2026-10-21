/** Formatting helpers.  Amounts are wei; GEN has 18 decimals. */

const WEI_PER_GEN = 10n ** 18n;

export function formatGen(wei: bigint, places = 4): string {
  const negative = wei < 0n;
  const value = negative ? -wei : wei;
  const whole = value / WEI_PER_GEN;
  const fraction = value % WEI_PER_GEN;
  const padded = fraction.toString().padStart(18, "0").slice(0, places);
  const sign = negative ? "-" : "";
  if (places === 0) return `${sign}${whole}`;
  return `${sign}${whole}.${padded}`;
}

export function formatWei(wei: bigint): string {
  return wei.toString();
}

export function formatTimestamp(seconds: number): string {
  return new Date(seconds * 1000).toISOString().replace(".000Z", "Z");
}

/** "in 2h 14m" / "closed 3m ago" */
export function formatCountdown(target: number, now: number): string {
  const delta = target - now;
  const past = delta <= 0;
  const seconds = Math.abs(delta);
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  let text: string;
  if (days > 0) text = `${days}d ${hours}h`;
  else if (hours > 0) text = `${hours}h ${minutes}m`;
  else if (minutes > 0) text = `${minutes}m ${String(secs).padStart(2, "0")}s`;
  else text = `${secs}s`;

  return past ? `closed ${text} ago` : `closes in ${text}`;
}

export function shortAddress(address: string): string {
  if (!address || address.length < 12) return address;
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

export function shortHash(hex: string): string {
  if (!hex || hex.length < 20) return hex;
  return `${hex.slice(0, 14)}…${hex.slice(-8)}`;
}
