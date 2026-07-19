import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";
import { Geist, Unbounded } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const unbounded = Unbounded({
  variable: "--font-unbounded",
  weight: ["400"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Tami — Plan That Trip to Japan",
  description:
    "Built at Hack the 6ix: a Telegram pet whose Physical health tracks live hotel data and whose Mental health tracks group engagement. The only way to save it is to book.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const fontVars = {
    ["--font-body" as string]: "var(--font-geist-sans), 'Geist Sans', system-ui, sans-serif",
    ["--font-display" as string]: "var(--font-unbounded), Unbounded, system-ui, sans-serif",
  } as CSSProperties;

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${unbounded.variable} h-full antialiased`}
      style={fontVars}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <Script
          src="https://code.iconify.design/iconify-icon/2.1.0/iconify-icon.min.js"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
