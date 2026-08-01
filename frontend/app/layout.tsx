import type { Metadata } from "next";
import "@livekit/components-styles";
import "./globals.css";

export const metadata: Metadata = {
  title: "Midgard Kitchen",
  description: "Feast well, mortal — a RAG voice agent hosted by Thor.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
