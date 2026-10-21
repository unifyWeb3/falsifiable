"use client";

import { useMemo, useState } from "react";

import { CommandBlock } from "@/components/CommandBlock";
import { RULE_NAMES } from "@/lib/market-state";

const CLI = "python3 scripts/falsifiable.py";

const RULES: { kind: number; label: string; blurb: string; needsPath: boolean }[] = [
  {
    kind: 1,
    label: "The body contains a phrase",
    blurb: "The raw response body must contain the text exactly.",
    needsPath: false,
  },
  {
    kind: 2,
    label: "The body is exactly a string",
    blurb: "The raw response body must equal the text exactly.",
    needsPath: false,
  },
  {
    kind: 3,
    label: "The title contains a phrase",
    blurb: "The text of the first <title> element must contain the text.",
    needsPath: false,
  },
  {
    kind: 4,
    label: "The title is exactly a string",
    blurb: "The text of the first <title> element must equal the text.",
    needsPath: false,
  },
  {
    kind: 5,
    label: "A JSON value contains a phrase",
    blurb: "The value at the dotted path, rendered canonically, must contain the text.",
    needsPath: true,
  },
  {
    kind: 6,
    label: "A JSON value is exactly a string",
    blurb: "The value at the dotted path, rendered canonically, must equal the text.",
    needsPath: true,
  },
];

function defaultCloseIn(): number {
  return 3600;
}

export default function OpenMarketPage() {
  const [url, setUrl] = useState("https://example.com/");
  const [claim, setClaim] = useState("");
  const [kind, setKind] = useState(1);
  const [param, setParam] = useState("");
  const [path, setPath] = useState("");
  const [closeIn, setCloseIn] = useState(defaultCloseIn());

  const rule = RULES.find((entry) => entry.kind === kind) ?? RULES[0];

  const problems = useMemo(() => {
    const found: string[] = [];
    if (!url.startsWith("https://")) found.push("the page must be an https URL");
    if (/\s/.test(url)) found.push("the URL must not contain spaces");
    if (url.length > 512) found.push("the URL is longer than 512 characters");
    if (claim.trim().length === 0) found.push("the claim must say something");
    if (claim.length > 512) found.push("the claim is longer than 512 characters");
    if (param.length === 0) found.push("the rule needs a parameter to look for");
    if (param.length > 1024) found.push("the rule parameter is longer than 1024 characters");
    if (rule.needsPath && path.length === 0) found.push("this rule needs a JSON path");
    if (path.length > 128) found.push("the JSON path is longer than 128 characters");
    if (closeIn < 60) found.push("the market must close at least a minute from now");
    if (closeIn > 30 * 24 * 3600) found.push("the market must close within 30 days");
    return found;
  }, [url, claim, param, path, closeIn, rule.needsPath]);

  const command = `${CLI} create --url ${JSON.stringify(url)} --claim ${JSON.stringify(
    claim,
  )} --rule ${RULE_NAMES[kind]} --param ${JSON.stringify(param)}${
    rule.needsPath ? ` --path ${JSON.stringify(path)}` : ""
  } --close-in ${closeIn}`;

  return (
    <section className="mt-10">
      <h1 className="serif text-[2.1rem] leading-tight">Open a market</h1>
      <p className="mt-2 max-w-[62ch] text-[0.95rem] text-ink-mid">
        A market is one page, one claim that could be checked, one rule that
        decides it, and a close time. This page builds the command; you run it
        with your own key.
      </p>

      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-7">
          <div>
            <label className="label label-ink" htmlFor="url">
              The page
            </label>
            <p className="mt-1 text-[0.82rem] text-ink-soft">
              One https URL. The validators fetch this exact address.
            </p>
            <input
              id="url"
              className="field mt-2"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              spellCheck={false}
            />
          </div>

          <div>
            <label className="label label-ink" htmlFor="claim">
              The claim
            </label>
            <p className="mt-1 text-[0.82rem] text-ink-soft">
              One sentence about what the page will show. Keep it checkable —
              but know that the rule below, not this sentence, decides the
              money.
            </p>
            <textarea
              id="claim"
              className="field mt-2 min-h-[5.5rem] leading-relaxed"
              value={claim}
              onChange={(event) => setClaim(event.target.value)}
              placeholder="The quarterly report page will show a revenue figure of 12%."
            />
          </div>

          <div>
            <span className="label label-ink">The rule</span>
            <p className="mt-1 text-[0.82rem] text-ink-soft">
              A closed set. There is no free text and no judgement call: the
              rule is applied to bytes.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {RULES.map((entry) => (
                <label
                  key={entry.kind}
                  className={`flex cursor-pointer gap-2.5 border p-3 text-[0.82rem] leading-snug ${
                    kind === entry.kind
                      ? "border-ink bg-paper-sunk"
                      : "border-rule bg-paper-raised"
                  }`}
                >
                  <input
                    type="radio"
                    name="rule"
                    className="mt-0.5"
                    checked={kind === entry.kind}
                    onChange={() => setKind(entry.kind)}
                  />
                  <span>
                    <span className="block text-ink">{entry.label}</span>
                    <span className="mt-0.5 block text-ink-soft">
                      {entry.blurb}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label className="label label-ink" htmlFor="param">
                The text to look for
              </label>
              <input
                id="param"
                className="field mt-2"
                value={param}
                onChange={(event) => setParam(event.target.value)}
                placeholder="12%"
                spellCheck={false}
              />
            </div>
            {rule.needsPath ? (
              <div>
                <label className="label label-ink" htmlFor="path">
                  JSON path
                </label>
                <input
                  id="path"
                  className="field mt-2"
                  value={path}
                  onChange={(event) => setPath(event.target.value)}
                  placeholder="data.items.0.value"
                  spellCheck={false}
                />
              </div>
            ) : null}
          </div>

          <div>
            <label className="label label-ink" htmlFor="closein">
              Closes in (seconds)
            </label>
            <p className="mt-1 text-[0.82rem] text-ink-soft">
              Between 60 seconds and 30 days. After the close time the market
              can be ruled on; an hour after that it refunds automatically.
            </p>
            <input
              id="closein"
              type="number"
              className="field mt-2"
              value={closeIn}
              min={60}
              max={2592000}
              onChange={(event) => setCloseIn(Number(event.target.value))}
            />
          </div>
        </div>

        <aside>
          <h2 className="label label-ink">The command</h2>
          {problems.length > 0 ? (
            <ul className="mt-2 space-y-1.5">
              {problems.map((problem) => (
                <li key={problem} className="notice notice-error text-[0.85rem] text-no">
                  {problem}
                </li>
              ))}
            </ul>
          ) : (
            <p className="notice notice-good mt-2 text-[0.85rem] text-ink-mid">
              This market is well formed. The command below will be accepted.
            </p>
          )}
          <div className="mt-4">
            <CommandBlock
              command={command}
              note="Needs your own key in FALSIFIABLE_KEY. The creator cannot stake on their own market."
            />
          </div>
          <p className="mt-4 text-[0.82rem] text-ink-soft">
            The command prints the market id and the transaction id. The
            transaction has to be finalised by the validators before the
            market exists on chain.
          </p>
        </aside>
      </div>
    </section>
  );
}
