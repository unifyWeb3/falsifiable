"use client";

import { useState } from "react";

/** A command you can copy and run yourself.  This site holds no keys. */
export function CommandBlock({
  command,
  note,
}: {
  command: string;
  note?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div>
      <div className="codeblock flex items-start gap-3">
        <code className="flex-1">{command}</code>
        <button
          type="button"
          onClick={copy}
          className="btn btn-quiet shrink-0 !px-2 !py-1 !text-[0.65rem]"
          aria-label="Copy the command to the clipboard"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {note ? <p className="label mt-1.5 normal-case tracking-normal">{note}</p> : null}
    </div>
  );
}
