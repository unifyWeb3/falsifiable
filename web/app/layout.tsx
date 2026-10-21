import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
  style: ["normal", "italic"],
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Falsifiable — a stake market on checkable claims",
  description:
    "Stake GEN on what a public web page will say at a fixed close time. Validators fetch the page and rule on it; the pot pays the winners.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${plexSans.variable} ${plexMono.variable}`}
    >
      <body>
        <main className="mx-auto w-full max-w-[1180px] px-5 pb-24 sm:px-8">
          <header className="hairline pt-8 pb-5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-3">
              <div>
                <Link
                  href="/"
                  className="serif text-[1.9rem] leading-none tracking-tight text-ink no-underline hover:text-seal"
                >
                  Falsifiable
                </Link>
                <p className="mt-2 max-w-[46ch] text-[0.95rem] leading-relaxed text-ink-mid">
                  A stake market on claims you can check. Back what a page will
                  say; validators fetch the page and rule on it.
                </p>
              </div>
              <nav className="label flex items-center gap-6">
                <Link href="/" className="text-ink-mid no-underline hover:text-seal">
                  The board
                </Link>
                <Link href="/open" className="text-ink-mid no-underline hover:text-seal">
                  Open a market
                </Link>
                <Link href="/trust" className="text-ink-mid no-underline hover:text-seal">
                  Trust
                </Link>
              </nav>
            </div>
          </header>
          {children}
          <footer className="hairline mt-16 pt-5 pb-2">
            <p className="label">
              Read-only front end · public Studio RPC · no keys held by this
              site
            </p>
          </footer>
        </main>
      </body>
    </html>
  );
}
