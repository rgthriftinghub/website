import type { Metadata } from "next";
import localFont from "next/font/local";

import "./globals.css";

const playfair = localFont({
  src: "../fonts/playfair-display-latin.woff2",
  display: "swap",
  variable: "--font-playfair",
  weight: "400 900",
});

const inter = localFont({
  src: "../fonts/inter-latin.woff2",
  display: "swap",
  variable: "--font-inter",
  weight: "100 900",
});

/**
 * Type pairing chosen to match the logo: a high-contrast serif echoing the
 * logo's R and G, set against a neutral grotesque for interface text.
 */
const siteName = "RG Thrifting Hub";
const siteDescription =
  "Curated thrift, export quality and new clothing for men and women. Hand-picked pieces, honest condition grading, and per-size stock you can trust.";

export const metadata: Metadata = {
  title: {
    default: `${siteName} — Curated Thrift & Export Quality Clothing`,
    template: `%s — ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  openGraph: {
    type: "website",
    siteName,
    title: `${siteName} — Curated Thrift & Export Quality Clothing`,
    description: siteDescription,
    images: [{ url: "/brand/logo.png", width: 1122, height: 1402, alt: siteName }],
  },
  twitter: { card: "summary_large_image", title: siteName, description: siteDescription },
  icons: { icon: "/brand/logo.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${playfair.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
