import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PersonaPrep — Meeting Intelligence",
  description: "Editorial-grade research briefs on the people you meet."
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
