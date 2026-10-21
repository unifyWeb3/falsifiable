import { formatGen } from "@/lib/format";

/**
 * The pool split: one ruled bar, not a donut and not a card.
 *
 * When one side is empty the bar shows the stake in neutral grey — the
 * market is still live, there is just nobody on the other side.
 */
export function PoolSplit({
  potYes,
  potNo,
  compact = false,
}: {
  potYes: string;
  potNo: string;
  compact?: boolean;
}) {
  const yes = BigInt(potYes);
  const no = BigInt(potNo);
  const total = yes + no;
  const yesPct = total === 0n ? 0 : Number((yes * 10000n) / total) / 100;
  const noPct = total === 0n ? 0 : 100 - yesPct;

  return (
    <div>
      <div
        className="split"
        role="img"
        aria-label={
          total === 0n
            ? "No stakes yet"
            : `Pool: ${yesPct.toFixed(1)}% yes, ${noPct.toFixed(1)}% no`
        }
      >
        {total === 0n ? (
          <div className="split-none" style={{ width: "100%" }} />
        ) : (
          <>
            <div className="split-yes" style={{ width: `${yesPct}%` }} />
            <div className="split-no" style={{ width: `${noPct}%` }} />
          </>
        )}
      </div>
      {!compact && (
        <div className="mt-1.5 flex justify-between text-[0.72rem]">
          <span className="num text-yes">
            YES {formatGen(yes)}{" "}
            <span className="text-ink-soft">
              {total === 0n ? "" : `${yesPct.toFixed(1)}%`}
            </span>
          </span>
          <span className="num text-no">
            {total === 0n ? "" : `${noPct.toFixed(1)}%`} NO {formatGen(no)}
          </span>
        </div>
      )}
    </div>
  );
}
