import type { Metadata } from "next";
import { Spline_Sans } from "next/font/google";
import "./globals.css";

// Balmody's web sans. Self-hosted at build time by next/font, so there is no
// render-blocking request to Google and no flash of unstyled text.
const splineSans = Spline_Sans({
  variable: "--font-spline",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ONE — one good thing, four times a day",
  description:
    "The internet is saturated with endless feeds. ONE surfaces exactly one exceptional " +
    "piece of content four times a day, chosen for the things you would never have found on your own.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${splineSans.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
