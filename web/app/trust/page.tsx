import Link from "next/link";

export const metadata = {
  title: "Trust — Falsifiable",
};

const PROMISED = [
  {
    title: "The money is real GEN and it is conserved",
    body: "Stakes are attached to the call itself, credited from the value the contract actually received. The pot is split by a cumulative allocation, so the shares sum to the pot exactly — there is no rounding dust for anyone to skim. Nobody can withdraw twice, and a loser withdraws nothing.",
  },
  {
    title: "The answer is decided by bytes, not by a model",
    body: "The rule is one of six fixed checks against bytes. There is no language model in the decision path, so nothing that a page says can change the answer — a page that tries to instruct the validators is simply compared against a literal string, like any other page.",
  },
  {
    title: "Every validator fetched the page itself",
    body: "The validator does not check the leader's answer. It fetches the page again and recomputes both the outcome and the SHA-256 of the exact evidence bytes. If the bytes differ from what the leader saw, the ruling does not commit and the market stays unresolved.",
  },
  {
    title: "Nothing is settled by an authority",
    body: "There is no owner, no admin key, no fee, no appeal, and no way to void a result. Closing, ruling and withdrawing are all permissionless, and a market that nobody rules on refunds everybody automatically an hour after it closes.",
  },
];

const STILL_TRUSTED = [
  {
    title: "The validator set",
    body: "A quorum of GenLayer validators decides. The contract cannot tell a colluding quorum from an honest one; it can only require that a quorum agreed on the same bytes.",
  },
  {
    title: "The moment of the reading",
    body: "The page is read when the validators fetch it, which is after the close time, not at it. A page that changes in between is judged on its later content. Narrowing that window is all the design can do.",
  },
  {
    title: "The author of the rule",
    body: "The rule decides the money. It is shown before you stake, and it cannot be changed afterwards, but a rule can still be written to be trivially true. Read the rule, not the sentence.",
  },
  {
    title: "The page's own honesty",
    body: "Falsifiable proves what the page said, not what was true. A page can lie to every validator at once and the market will still resolve honestly on the lie.",
  },
  {
    title: "The deployer key",
    body: "The demo keys in this repository are throwaway Studio keys; they are gitignored and control nothing but testnet funds. On any real network a deployer key is still one key — and this contract deliberately gives it no powers beyond opening markets and staking.",
  },
];

export default function TrustPage() {
  return (
    <section className="mt-10 max-w-[74ch]">
      <h1 className="serif text-[2.1rem] leading-tight">What you can rely on</h1>
      <p className="mt-2 text-[0.95rem] text-ink-mid">
        And, just as plainly, what you still have to trust.
      </p>

      <h2 className="label label-ink mt-9">Promised, and tested</h2>
      <div className="mt-3 space-y-5">
        {PROMISED.map((item) => (
          <div key={item.title} className="border-l-2 border-yes pl-4">
            <h3 className="serif text-[1.15rem] leading-snug">{item.title}</h3>
            <p className="mt-1 text-[0.92rem] leading-relaxed text-ink-mid">
              {item.body}
            </p>
          </div>
        ))}
      </div>

      <h2 className="label label-ink mt-11">Still trusted</h2>
      <div className="mt-3 space-y-5">
        {STILL_TRUSTED.map((item) => (
          <div key={item.title} className="border-l-2 border-undet pl-4">
            <h3 className="serif text-[1.15rem] leading-snug">{item.title}</h3>
            <p className="mt-1 text-[0.92rem] leading-relaxed text-ink-mid">
              {item.body}
            </p>
          </div>
        ))}
      </div>

      <h2 className="label label-ink mt-11">What was actually run</h2>
      <div className="mt-3 space-y-3 text-[0.92rem] leading-relaxed text-ink-mid">
        <p>
          The contract is exercised by an automated test suite that runs the
          contract in a real GenVM: the full path for YES, NO and
          UNDETERMINED, the money invariants, and twenty red-team cases — each
          refusal paired with a positive control, because a refusal that is
          not paired with a control can pass for the wrong reason.
        </p>
        <p>
          The same contract was deployed to the GenLayer Studio network, where
          the leader and the validators each fetched a live public page and
          agreed on its bytes, and where a market was staked, ruled on and
          paid out. The repository README lists the transaction ids.
        </p>
        <p>
          The front end you are reading is read-only. It talks to the public
          RPC, holds no keys, and cannot move money. Every write is a command
          you run yourself.
        </p>
      </div>

      <p className="mt-9 text-[0.92rem]">
        <Link href="/" className="text-ink underline decoration-rule-strong underline-offset-2 hover:text-seal">
          Back to the board
        </Link>
      </p>
    </section>
  );
}
