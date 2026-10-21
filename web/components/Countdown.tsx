"use client";

import { useEffect, useState } from "react";

import { formatCountdown } from "@/lib/format";

/**
 * A live countdown to the close time.
 *
 * The server passes the time it rendered with, so the server HTML and the
 * first client render agree — otherwise React reports a hydration mismatch.
 * After that the browser's own clock takes over.
 *
 * The clock shown here is the browser's clock.  The contract uses the
 * *transaction timestamp* instead, so what you see is indicative; the
 * contract's own gate is the one that counts.
 */
export function Countdown({
  closeTime,
  prefix = "",
  initialNow,
}: {
  closeTime: number;
  prefix?: string;
  initialNow: number;
}) {
  const [now, setNow] = useState(initialNow);

  useEffect(() => {
    const update = () => setNow(Math.floor(Date.now() / 1000));
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  const closed = now >= closeTime;

  return (
    <span className={`num ${closed ? "text-ink-soft" : "text-ink"}`}>
      {prefix}
      {formatCountdown(closeTime, now)}
    </span>
  );
}
