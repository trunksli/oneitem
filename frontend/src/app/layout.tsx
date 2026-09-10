import type { Metadata } from "next";
import { Spline_Sans } from "next/font/google";
import "./globals.css";
import SiteFooter from "@/components/site-footer";

// Balmody's web sans. Self-hosted at build time by next/font, so there is no
// render-blocking request to Google and no flash of unstyled text.
const splineSans = Spline_Sans({
  variable: "--font-spline",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const SITE_TITLE = "ONE — one good thing, four times a day";
const SITE_DESCRIPTION =
  "The internet is saturated with endless feeds. ONE surfaces exactly one exceptional " +
  "piece of content four times a day, chosen for the things you would never have found on your own.";

export const metadata: Metadata = {
  // Absolute base for the preview image and canonical URLs below.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://one-web-bwjk.onrender.com"),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: "ONE",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: "/",
    images: [{ url: "/og-default.png", width: 1200, height: 630,
               alt: "ONE — one good thing, four times a day" }],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/og-default.png"],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${splineSans.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {children}
        {/* In the layout so every page, and the static HTML crawlers read, carries
            the legal links and the AI disclosure. */}
        <SiteFooter />
      </body>
    </html>
  );
}
