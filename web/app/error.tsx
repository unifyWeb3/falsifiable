"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <section className="sheet mt-10 p-6">
      <h1 className="serif text-2xl">Something broke while reading the chain</h1>
      <p className="mt-2 max-w-[62ch] text-[0.95rem] text-ink-mid">
        This page reads the contract over the public Studio RPC. It does not
        cache, and it does not fall back to made-up data, so if it cannot
        reach the chain it says so instead of pretending.
      </p>
      <p className="codeblock mt-4">{error.message}</p>
      <button type="button" className="btn mt-5" onClick={() => reset()}>
        Try again
      </button>
    </section>
  );
}
