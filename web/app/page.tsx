import Link from "next/link";

import { Countdown } from "@/components/Countdown";
import { PoolSplit } from "@/components/PoolSplit";
import { StatusTag } from "@/components/StatusTag";
import { ConfigError, RpcError } from "@/lib/chain";
import { formatGen } from "@/lib/format";
import { readMarketCount, readMarketSummaries } from "@/lib/market";
import { ruleDescription } from "@/lib/market-state";

export const metadata = {
  title: "The board — Falsifiable",
};

type BoardResult =
  | { ok: true; markets: Awaited<ReturnType<typeof readMarketSummaries>> }
  | { ok: false; failure: { kind: "config" | "rpc"; message: string } };

async function loadBoard(): Promise<BoardResult> {
  try {
    return { ok: true, markets: await readMarketSummaries() };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      failure: {
        kind: error instanceof ConfigError ? "config" : "rpc",
        message,
      },
    };
  }
}

export default async function BoardPage() {
  const result = await loadBoard();
  const now = Math.floor(Date.now() / 1000);

  if (!result.ok) {
    const { kind, message } = result.failure;
    return (
      <section className="sheet mt-10 p-6">
        <h1 className="serif text-2xl">The board is unreachable</h1>
        <p className="mt-2 max-w-[62ch] text-[0.95rem] text-ink-mid">
          {kind === "config"
            ? "This deployment is not configured for a contract, so it will not pretend the chain is empty. Set NEXT_PUBLIC_STUDIONET_RPC and NEXT_PUBLIC_FALSIFIABLE_CONTRACT and reload."
            : "The Studio RPC did not answer. The board below is not a cached copy — there is no cached copy."}
        </p>
        <p className="codeblock mt-4">{message}</p>
      </section>
    );
  }

  const markets = result.markets;

  const totalStaked = markets.reduce(
    (sum, market) => sum + BigInt(market.potYes) + BigInt(market.potNo),
    0n,
  );

  return (
    <>
      <section className="mt-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="serif text-[2.1rem] leading-tight">The board</h1>
          <p className="mt-1 max-w-[58ch] text-[0.95rem] text-ink-mid">
            Every market below is one page, one claim and one rule. Read the
            rule, not the prose: the rule is what the validators apply.
          </p>
        </div>
        <div className="text-right">
          <p className="label">Markets</p>
          <p className="num text-2xl">{markets.length}</p>
        </div>
      </section>

      <section className="mt-6 flex flex-wrap gap-x-10 gap-y-2 border-y border-rule py-3">
        <div>
          <p className="label">Staked in view</p>
          <p className="num text-lg">{formatGen(totalStaked)} GEN</p>
        </div>
        <div>
          <p className="label">Open now</p>
          <p className="num text-lg">
            {markets.filter((market) => market.status === 0).length}
          </p>
        </div>
        <div>
          <p className="label">Awaiting a ruling</p>
          <p className="num text-lg">
            {markets.filter((market) => market.status === 1).length}
          </p>
        </div>
        <div>
          <p className="label">Settled</p>
          <p className="num text-lg">
            {markets.filter((market) => market.status >= 2).length}
          </p>
        </div>
      </section>

      {markets.length === 0 ? (
        <section className="sheet mt-8 p-8 text-center">
          <h2 className="serif text-xl">No markets yet</h2>
          <p className="mx-auto mt-2 max-w-[46ch] text-[0.95rem] text-ink-mid">
            Nobody has opened a claim. Be the first: pick a page, write a
            claim that could be checked, and give it a rule.
          </p>
          <Link href="/open" className="btn mt-5 inline-flex">
            Open a market
          </Link>
        </section>
      ) : (
        <section className="sheet mt-8">
          {markets.map((market) => (
            <article key={market.id} className="docket-row p-5">
              <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="label">No. {market.id}</span>
                    <StatusTag
                      status={market.status}
                      hasStake={
                        BigInt(market.potYes) + BigInt(market.potNo) > 0n
                      }
                    />
                  </div>
                  <h3 className="serif mt-2 text-[1.35rem] leading-snug">
                    <Link
                      href={`/market/${market.id}`}
                      className="text-ink no-underline hover:text-seal"
                    >
                      {market.claim}
                    </Link>
                  </h3>
                  <p className="mt-1 text-[0.85rem] text-ink-mid">
                    Rule: {ruleDescription(market.ruleKind, market.ruleParam, market.rulePath)}
                  </p>
                  <p className="mt-1 truncate text-[0.8rem] text-ink-soft">
                    {market.url}
                  </p>
                </div>
                <div className="w-full max-w-[320px]">
                  <PoolSplit
                    potYes={market.potYes}
                    potNo={market.potNo}
                  />
                  <p className="mt-2 text-[0.8rem]">
                    <Countdown closeTime={market.closeTime} initialNow={now} />
                  </p>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </>
  );
}
