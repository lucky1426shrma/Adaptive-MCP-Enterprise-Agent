import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "./globals.css";

// IBM Plex is designed for technical/engineering contexts, which is
// what this console actually is — a deliberate choice over a generic
// web-safe sans, not a default. Mono carries anything that's literal
// data (tool names, server IDs, latencies, citation chunk IDs); Sans
// carries everything else.
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
  title: "Investigation Console — Adaptive MCP Enterprise Agent",
  description:
    "Ask a question; watch the agent decide which tools it actually needs, across RAG, database, and GitHub, with cited evidence.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
