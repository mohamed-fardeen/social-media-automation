import type { Metadata, Viewport } from "next";
import { Inter, Inter_Tight, JetBrains_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { BootstrapRealtime } from "@/components/BootstrapRealtime";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});
const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-inter-tight",
  display: "swap",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});
const instrument = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Kelvin6k — AI Social Engine",
  description: "An AI command center for premium brands. Generate, approve, and publish social content with supervised agents.",
};

export const viewport: Viewport = {
  themeColor: "#0A0B0D",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${interTight.variable} ${jetbrains.variable} ${instrument.variable}`}
    >
      <body className="font-sans antialiased">
        <BootstrapRealtime />
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 px-8 py-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
