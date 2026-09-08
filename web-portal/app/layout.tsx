import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

// EBADS Admin Design System §Type: IBM Plex Sans for interface text, IBM Plex Mono for
// data/metrics (timestamps, IDs, counts) — the same dual-font pairing the dispatcher app uses —
// plus IBM Plex Sans Condensed for compact brand/avatar-initial treatments (sidebar, topbar).
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["500", "600"],
});

const plexSansCondensed = IBM_Plex_Sans_Condensed({
  variable: "--font-plex-sans-condensed",
  subsets: ["latin"],
  weight: ["600", "700"],
});

export const metadata: Metadata = {
  title: "EBADS Portal",
  description: "EBADS facility administration portal",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} ${plexSansCondensed.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
