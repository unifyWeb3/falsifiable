import { MARKET_STATUS, statusName } from "@/lib/market-state";

const CLASS_BY_STATUS: Record<number, string> = {
  [MARKET_STATUS.OPEN]: "status-open",
  [MARKET_STATUS.CLOSED]: "status-closed",
  [MARKET_STATUS.RESOLVED_YES]: "status-yes",
  [MARKET_STATUS.RESOLVED_NO]: "status-no",
  [MARKET_STATUS.RESOLVED_UNDETERMINED]: "status-undetermined",
  [MARKET_STATUS.RESOLVED_REFUNDED]: "status-refunded",
};

const FRIENDLY: Record<number, string> = {
  [MARKET_STATUS.OPEN]: "Open",
  [MARKET_STATUS.CLOSED]: "Awaiting resolution",
  [MARKET_STATUS.RESOLVED_YES]: "Resolved YES",
  [MARKET_STATUS.RESOLVED_NO]: "Resolved NO",
  [MARKET_STATUS.RESOLVED_UNDETERMINED]: "Undetermined — refunded",
  [MARKET_STATUS.RESOLVED_REFUNDED]: "Refunded — one-sided pool",
};

export function StatusTag({
  status,
  hasStake = true,
}: {
  status: number;
  /** False when nobody ever put money in: there is nothing to settle. */
  hasStake?: boolean;
}) {
  const known = status in CLASS_BY_STATUS;
  const label =
    status === MARKET_STATUS.RESOLVED_REFUNDED && !hasStake
      ? "No stake — nothing to settle"
      : (FRIENDLY[status] ?? `Unknown (${status})`);
  return (
    <span
      className={`status ${known ? CLASS_BY_STATUS[status] : "status-unknown"}`}
      title={statusName(status)}
    >
      {label}
    </span>
  );
}
