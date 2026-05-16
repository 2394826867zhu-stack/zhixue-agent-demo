import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

// ui-ux-pro-max recommendation: Plus Jakarta Sans — Friendly SaaS
// Best for: SaaS products, dashboards, productivity tools, EdTech
const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-geist-sans", // reuse existing CSS token
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap", // font-display: swap per UX guideline
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "知曜 · 智学Agent",
  description: "AI 驱动的学习操作系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${plusJakarta.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
