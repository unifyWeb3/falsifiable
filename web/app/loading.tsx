export default function Loading() {
  return (
    <section className="mt-10" aria-busy="true" aria-live="polite">
      <span className="label">Reading the chain…</span>
      <div className="mt-4 space-y-3" aria-hidden="true">
        <div className="h-4 w-1/3 bg-paper-sunk" />
        <div className="h-3 w-3/4 bg-paper-sunk" />
        <div className="h-3 w-1/2 bg-paper-sunk" />
        <div className="mt-6 h-16 w-full bg-paper-sunk" />
      </div>
    </section>
  );
}
