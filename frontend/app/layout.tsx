import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const hankenGrotesk = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-hanken",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CryptoTrace AI — Blockchain Fraud Investigation Platform",
  description: "Evidence-linked cryptocurrency investigation workspace for tracing reported wallet activity and explaining deterministic findings.",
  icons: {
    icon: "/cryptotrace-icon.svg",
    apple: "/cryptotrace-icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#124343",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-forensic-theme="institutional">
      <body className={`${hankenGrotesk.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <a href="#main-content" className="ct-skip-link">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
