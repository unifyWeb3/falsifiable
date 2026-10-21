import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionPanel } from "@/components/ActionPanel";
import { Countdown } from "@/components/Countdown";
import { PoolSplit } from "@/components/PoolSplit";
import { StatusTag } from "@/components/StatusTag";
import { ConfigError } from "@/lib/chain";
import { formatGen, formatTimestamp, shortAddress } from "@/lib/format";
import { readMarket } from "@/lib/market";
import {
  MARKET_STATUS,
  ruleDescription,
  ruleName,
  statusName,
} from "@/lib/market-state";

export const metadata = {
  title: "Market — Falsifiable",
};

const OUTCOME_TEXT: Record<number, string> = {
  0: "Not ruled on yet.",
  1: "The rule came out YES.",
  2: "The rule came out NO.",
  3: "The rule could not be decided — UNDETERMINED.",
};

export default async function MarketPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: rawId } = await params;
  const id = Number(rawId);
  if (!Number.isInteger(id) || id < 0) notFound();

  let market;
  try {
    market = await readMarket(id);
  } catch (error) {
    if (error instanceof ConfigError) throw error;
    notFound();
  }

  const now = Math.floor(Date.now() / 1000);
  const potYes = BigInt(market.potYes);
  const potNo = BigInt(market.potNo);
  const pot = potYes + potNo;
  const payoutPot = BigInt(market.payoutPot);
  const winnerIsYes = market.status === MARKET_STATUS.RESOLVED_YES;
  const winnerIsNo = market.status === MARKET_STATUS.RESOLVED_NO;
  const refunded =
    market.status === MARKET_STATUS.RESOLVED_UNDETERMINED ||
    market.status === MARKET_STATUS.RESOLVED_REFUNDED;

  return (
    <>
      <nav className="label mt-8">
        <Link href="/" className="text-ink-mid no-underline hover:text-seal">
          The board
        </Link>{" "}
        / <span className="text-ink">No. {market.id}</span>
      </nav>

      <article className="mt-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusTag status={market.status} hasStake={pot > 0n} />
          <span className="label">
            opened by{" "}
            <span className="num normal-case tracking-normal text-ink-mid">
              {shortAddress(market.creator)}
            </span>
          </span>
        </div>

        <h1 className="serif mt-4 max-w-[26ch] text-[2.4rem] leading-[1.15] tracking-[-0.01em] sm:text-[3rem]">
          {market.claim}
        </h1>

        <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0">
            <section>
              <h2 className="label label-ink">The rule</h2>
              <p className="serif mt-1.5 text-[1.15rem] leading-snug">
                {ruleDescription(
                  market.ruleKind,
                  market.ruleParam,
                  market.rulePath,
                )}
              </p>
              <dl className="mt-3 grid grid-cols-[9rem_minmax(0,1fr)] gap-x-4 gap-y-1 text-[0.82rem]">
                <dt className="label">Rule kind</dt>
                <dd className="num">{ruleName(market.ruleKind)}</dd>
                <dt className="label">Parameter</dt>
                <dd className="num break-all">{market.ruleParam}</dd>
                {market.rulePath ? (
                  <>
                    <dt className="label">Path</dt>
                    <dd className="num break-all">{market.rulePath}</dd>
                  </>
                ) : null}
                <dt className="label">Page</dt>
                <dd className="num break-all">
                  <a
                    href={market.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-ink underline decoration-rule-strong underline-offset-2 hover:text-seal"
                  >
                    {market.url}
                  </a>
                </dd>
              </dl>
              <p className="notice notice-warn mt-4 text-[0.85rem] text-ink-mid">
                The rule decides the money, not the sentence above it. A
                sentence can be written to mislead; the rule is what the
                validators apply, byte for byte.
              </p>
            </section>

            <section className="mt-9">
              <h2 className="label label-ink">The pool</h2>
              <div className="mt-2 max-w-[520px]">
                <PoolSplit potYes={market.potYes} potNo={market.potNo} />
              </div>
              <dl className="mt-4 grid grid-cols-[9rem_minmax(0,1fr)] gap-x-4 gap-y-1 text-[0.82rem]">
                <dt className="label">On YES</dt>
                <dd className="num">{formatGen(potYes)} GEN</dd>
                <dt className="label">On NO</dt>
                <dd className="num">{formatGen(potNo)} GEN</dd>
                <dt className="label">Total pot</dt>
                <dd className="num">{formatGen(pot)} GEN</dd>
                {payoutPot > 0n ? (
                  <>
                    <dt className="label">Split between</dt>
                    <dd className="num">
                      {winnerIsYes ? "the YES side" : "the NO side"} —{" "}
                      {formatGen(payoutPot)} GEN
                    </dd>
                  </>
                ) : null}
              </dl>
            </section>

            <section className="mt-9">
              <h2 className="label label-ink">The record</h2>
              <dl className="mt-2 grid grid-cols-[9rem_minmax(0,1fr)] gap-x-4 gap-y-1 text-[0.82rem]">
                <dt className="label">State</dt>
                <dd className="num">{statusName(market.status)}</dd>
                <dt className="label">Closes at</dt>
                <dd className="num">
                  {formatTimestamp(market.closeTime)}{" "}
                  <span className="text-ink-soft">
                    (<Countdown closeTime={market.closeTime} initialNow={now} />)
                  </span>
                </dd>
                <dt className="label">Ruling</dt>
                <dd>{OUTCOME_TEXT[market.ruleOutcome] ?? "—"}</dd>
                <dt className="label">Evidence digest</dt>
                <dd className="num break-all">
                  {market.evidenceDigest && market.evidenceDigest !== "00".repeat(32)
                    ? market.evidenceDigest
                    : "not recorded yet"}
                </dd>
              </dl>
              <p className="mt-3 max-w-[62ch] text-[0.85rem] text-ink-mid">
                The digest is the SHA-256 of the exact bytes the rule was
                applied to. Every validator fetched the page itself and had to
                arrive at the same digest, or the ruling does not commit.
              </p>
              {refunded ? (
                <p className="notice notice-warn mt-4 text-[0.85rem] text-ink-mid">
                  {market.status === MARKET_STATUS.RESOLVED_REFUNDED
                    ? "The rule was decided, but the pool only ever had money on one side, so everybody was refunded rather than paid out."
                    : "The rule could not be decided, so everybody was refunded."}
                </p>
              ) : null}
            </section>
          </div>

          <aside className="lg:border-l lg:border-rule lg:pl-8">
            <ActionPanel
              marketId={market.id}
              status={market.status}
              closeTime={market.closeTime}
              initialNow={now}
            />
          </aside>
        </div>
      </article>
    </>
  );
}
