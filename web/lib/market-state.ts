/**
 * The ONE place in the web app that decides what a user may do.
 *
 * Everything the interface offers is derived from `deriveActions`, a pure
 * function of the contract's status (plus the clock and the caller's
 * entitlement).  There is no second copy of these rules anywhere in the UI.
 *
 * `market-state.test.ts` parses `contracts/falsifiable.py` and asserts that
 * this module agrees with it, so the two cannot drift.
 */

export const MARKET_STATUS = {
  OPEN: 0,
  CLOSED: 1,
  RESOLVED_YES: 2,
  RESOLVED_NO: 3,
  RESOLVED_UNDETERMINED: 4,
  RESOLVED_REFUNDED: 5,
} as const;

export type MarketStatus = (typeof MARKET_STATUS)[keyof typeof MARKET_STATUS];

export const STATUS_NAMES: Record<number, string> = {
  0: "OPEN",
  1: "CLOSED",
  2: "RESOLVED_YES",
  3: "RESOLVED_NO",
  4: "RESOLVED_UNDETERMINED",
  5: "RESOLVED_REFUNDED",
};

export const RESOLVED_STATUSES: number[] = [
  MARKET_STATUS.RESOLVED_YES,
  MARKET_STATUS.RESOLVED_NO,
  MARKET_STATUS.RESOLVED_UNDETERMINED,
  MARKET_STATUS.RESOLVED_REFUNDED,
];

export const SIDE_YES = 0;
export const SIDE_NO = 1;

export const RULE_NAMES: Record<number, string> = {
  1: "BODY_CONTAINS",
  2: "BODY_EQUALS",
  3: "TITLE_CONTAINS",
  4: "TITLE_EQUALS",
  5: "JSON_FIELD_CONTAINS",
  6: "JSON_FIELD_EQUALS",
};

export type MarketActions = {
  canStake: boolean;
  canClose: boolean;
  canResolve: boolean;
  canWithdraw: boolean;
  canConfirm: boolean;
};

export type ActionInput = {
  /** The status the contract reports. */
  status: number;
  /** The current unix time in seconds. */
  now: number;
  /** The market's close time, in unix seconds. */
  closeTime: number;
  /** What the caller would receive if they withdrew right now, in wei. */
  payoutPreview: bigint;
  /**
   * Value the contract has already sent but the payee has not confirmed, in
   * wei.  A second withdraw is refused while this is non-zero.
   */
  pending?: bigint;
};

/**
 * Which actions the contract will accept, given its status.
 *
 * Mirrors the guards in `contracts/falsifiable.py`:
 *   stake     -> the market must be OPEN and the close time not yet passed
 *   close     -> the market must be OPEN and the close time passed
 *   resolve   -> the market must be OPEN (past its close time) or CLOSED
 *   withdraw  -> the market must be resolved, the caller must be owed
 *                something, and no earlier payout may still be pending
 *   confirm   -> the caller must have a payout that is pending acknowledgement
 */
export function deriveActions(input: ActionInput): MarketActions {
  const { status, now, closeTime, payoutPreview } = input;
  const pending = input.pending ?? 0n;
  const isOpen = status === MARKET_STATUS.OPEN;
  const isClosed = status === MARKET_STATUS.CLOSED;
  const isResolved = RESOLVED_STATUSES.includes(status);
  const pastClose = now >= closeTime;

  return {
    canStake: isOpen && !pastClose,
    canClose: isOpen && pastClose,
    canResolve: (isOpen && pastClose) || isClosed,
    canWithdraw: isResolved && payoutPreview > 0n && pending === 0n,
    canConfirm: isResolved && pending > 0n,
  };
}

export function statusName(status: number): string {
  return STATUS_NAMES[status] ?? `UNKNOWN(${status})`;
}

export function ruleName(kind: number): string {
  return RULE_NAMES[kind] ?? `UNKNOWN(${kind})`;
}

/** A short, honest description of what the rule checks. */
export function ruleDescription(
  kind: number,
  param: string,
  path: string,
): string {
  switch (kind) {
    case 1:
      return `the page body must contain the text ${JSON.stringify(param)}`;
    case 2:
      return `the page body must be exactly ${JSON.stringify(param)}`;
    case 3:
      return `the page title must contain the text ${JSON.stringify(param)}`;
    case 4:
      return `the page title must be exactly ${JSON.stringify(param)}`;
    case 5:
      return `the JSON value at ${path} must contain the text ${JSON.stringify(param)}`;
    case 6:
      return `the JSON value at ${path} must be exactly ${JSON.stringify(param)}`;
    default:
      return `unknown rule (${kind})`;
  }
}
