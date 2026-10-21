"use client";

import { useCallback, useEffect, useState } from "react";

import { CommandBlock } from "@/components/CommandBlock";
import { formatGen } from "@/lib/format";
import { deriveActions, type ActionInput } from "@/lib/market-state";

type Position = {
  yes: string;
  no: string;
  settledYes: string;
  settledNo: string;
};

type TxState = {
  txId: string;
  status: string;
  result: string;
  present: boolean;
};

const CLI = "python3 scripts/falsifiable.py";

export function ActionPanel({
  marketId,
  status,
  closeTime,
  initialNow,
}: {
  marketId: number;
  status: number;
  closeTime: number;
  initialNow: number;
}) {
  const [address, setAddress] = useState("");
  const [position, setPosition] = useState<Position | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [looking, setLooking] = useState(false);
  // The server's time, so the server HTML and the first client render agree.
  const [now, setNow] = useState(initialNow);

  const [txId, setTxId] = useState("");
  const [tx, setTx] = useState<TxState | null>(null);
  const [txError, setTxError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(
      () => setNow(Math.floor(Date.now() / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);

  const input: ActionInput = {
    status,
    now,
    closeTime,
    payoutPreview: preview === null ? 0n : BigInt(preview),
  };
  const actions = deriveActions(input);

  const lookup = useCallback(async () => {
    if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
      setLookupError("enter a 0x-prefixed 20-byte address");
      return;
    }
    setLooking(true);
    setLookupError(null);
    try {
      const response = await fetch(
        `/api/position?id=${marketId}&address=${address}`,
        { cache: "no-store" },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ?? "the lookup failed");
      setPosition(body.position);
      setPreview(body.preview);
    } catch (error) {
      setLookupError(
        error instanceof Error ? error.message : "the lookup failed",
      );
      setPosition(null);
      setPreview(null);
    } finally {
      setLooking(false);
    }
  }, [address, marketId]);

  const track = useCallback(async () => {
    if (!/^0x[0-9a-fA-F]{64}$/.test(txId)) {
      setTxError("enter a 0x-prefixed 32-byte transaction id");
      return;
    }
    setTxError(null);
    try {
      const response = await fetch(`/api/tx?id=${txId}`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ?? "the lookup failed");
      setTx(body);
    } catch (error) {
      setTxError(error instanceof Error ? error.message : "the lookup failed");
      setTx(null);
    }
  }, [txId]);

  // Keep the transaction state live while a transaction is in flight.
  useEffect(() => {
    if (!tx) return;
    if (tx.status === "FINALIZED" || tx.status === "CANCELED") return;
    const timer = setInterval(() => {
      void track();
    }, 4000);
    return () => clearInterval(timer);
  }, [tx, track]);

  const commands: { key: string; title: string; command: string; note?: string }[] =
    [];
  if (actions.canStake) {
    commands.push({
      key: "stake-yes",
      title: "Back YES",
      command: `${CLI} stake --market ${marketId} --side yes --amount 10`,
      note: "Replace 10 with the amount of GEN you want to put on YES.",
    });
    commands.push({
      key: "stake-no",
      title: "Back NO",
      command: `${CLI} stake --market ${marketId} --side no --amount 10`,
      note: "Replace 10 with the amount of GEN you want to put on NO.",
    });
  }
  if (actions.canClose) {
    commands.push({
      key: "close",
      title: "Close the market",
      command: `${CLI} close --market ${marketId}`,
      note: "Staking is already over; this only moves the market to its next state.",
    });
  }
  if (actions.canResolve) {
    commands.push({
      key: "resolve",
      title: "Rule on the market",
      command: `${CLI} resolve --market ${marketId}`,
      note: "Validators fetch the page and rule on it. You cannot choose the answer.",
    });
  }
  if (actions.canWithdraw) {
    commands.push({
      key: "withdraw",
      title: "Withdraw",
      command: `${CLI} withdraw --market ${marketId}`,
      note: "Pays your own position to your own address. Nothing is pushed to you.",
    });
  }

  return (
    <div className="space-y-7">
      <section>
        <h2 className="label label-ink">Your position</h2>
        <div className="mt-2 flex gap-2">
          <input
            className="field"
            placeholder="0x… your address"
            value={address}
            onChange={(event) => setAddress(event.target.value.trim())}
            aria-label="Your address"
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => void lookup()}
            disabled={looking}
          >
            {looking ? "Looking" : "Look up"}
          </button>
        </div>
        {lookupError ? (
          <p className="notice notice-error mt-3 text-[0.85rem] text-no">
            {lookupError}
          </p>
        ) : null}
        {position ? (
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[0.82rem]">
            <dt className="label">On YES</dt>
            <dd className="num text-right">{formatGen(BigInt(position.yes))} GEN</dd>
            <dt className="label">On NO</dt>
            <dd className="num text-right">{formatGen(BigInt(position.no))} GEN</dd>
            <dt className="label">Withdrawable now</dt>
            <dd className="num text-right">
              {formatGen(BigInt(preview ?? "0"))} GEN
            </dd>
          </dl>
        ) : (
          <p className="mt-2 text-[0.82rem] text-ink-soft">
            Enter your address to see what you have in this market and what you
            could withdraw right now.
          </p>
        )}
      </section>

      <section>
        <h2 className="label label-ink">What you can do now</h2>
        {commands.length === 0 ? (
          <p className="mt-2 text-[0.9rem] text-ink-mid">
            Nothing to do here right now. Staking is closed, the market is
            waiting to be ruled on, or you have nothing to withdraw.
          </p>
        ) : (
          <div className="mt-2 space-y-4">
            {commands.map((command) => (
              <div key={command.key}>
                <p className="label mb-1.5">{command.title}</p>
                <CommandBlock command={command.command} note={command.note} />
              </div>
            ))}
            <p className="notice notice-warn text-[0.8rem] text-ink-mid">
              These commands need your own key in{" "}
              <code className="num">FALSIFIABLE_KEY</code>. This site never sees
              a key and cannot move your money.
            </p>
          </div>
        )}
      </section>

      <section>
        <h2 className="label label-ink">Track a transaction</h2>
        <div className="mt-2 flex gap-2">
          <input
            className="field"
            placeholder="0x… transaction id"
            value={txId}
            onChange={(event) => setTxId(event.target.value.trim())}
            aria-label="Transaction id"
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => void track()}
          >
            Track
          </button>
        </div>
        {txError ? (
          <p className="notice notice-error mt-3 text-[0.85rem] text-no">
            {txError}
          </p>
        ) : null}
        {tx ? (
          <div className="mt-3">
            <p className="text-[0.85rem]">
              <span className="label mr-2">Status</span>
              <span className="num">{tx.status}</span>
              <span className="label mx-2">Result</span>
              <span className="num">{tx.result}</span>
            </p>
            {tx.status === "FINALIZED" ? (
              <p className="notice notice-good mt-2 text-[0.82rem] text-ink-mid">
                Finalized. The state below has been updated on chain.
              </p>
            ) : (
              <p className="notice notice-warn mt-2 text-[0.82rem] text-ink-mid">
                Submitted to the network and waiting for the validators to
                agree. Nothing is committed until that happens.
              </p>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}
