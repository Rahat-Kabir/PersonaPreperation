import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PersonaPreparation | Instant Meeting Briefs",
  description: "Walk into any meeting confident with AI-powered research summaries."
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
