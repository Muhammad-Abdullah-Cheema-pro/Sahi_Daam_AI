import type { Metadata } from "next";
import {
  Inter,
  Noto_Naskh_Arabic,
  Noto_Nastaliq_Urdu,
} from "next/font/google";
import { AppProvider } from "@/context/AppProvider";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  variable: "--font-naskh",
  display: "swap",
});

const nastaliq = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  variable: "--font-nastaliq",
  display: "swap",
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "Sahi Daam AI | صحیح دام",
  description:
    "Fair-price and sell-or-move advisor for Punjab farmers (AICON'26).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ur"
      dir="rtl"
      suppressHydrationWarning
      className={`${inter.variable} ${naskh.variable} ${nastaliq.variable}`}
    >
      <body className="font-naskh antialiased">
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
