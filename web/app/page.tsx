"use client";

import { CheckPrice } from "@/components/CheckPrice";
import { FabMenu } from "@/components/FabMenu";
import { Hero } from "@/components/Hero";
import { MyLocation } from "@/components/MyLocation";
import { Navbar } from "@/components/Navbar";
import { NearMandi } from "@/components/NearMandi";
import { WeatherOutlook } from "@/components/WeatherOutlook";
import { useI18n } from "@/hooks/useI18n";

export default function HomePage() {
  const { t, lang } = useI18n();

  return (
    <div
      className={`lang-fade min-h-dvh bg-sand-50 text-emerald-950 dark:bg-[#0B1612] dark:text-emerald-50 ${
        lang === "en" ? "font-inter" : "font-naskh"
      }`}
    >
      <a href="#main" className="skip-link">
        {t.skipToContent}
      </a>
      <Navbar />
      <main
        id="main"
        className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-6 pb-28"
      >
        <Hero />
        <MyLocation />
        <CheckPrice />
        <NearMandi />
        <WeatherOutlook />
        <footer className="border-t border-emerald-800/10 pt-6 text-center text-sm text-[color:var(--muted)] dark:border-emerald-100/10">
          <p>{t.footerRights}</p>
          <p className="mt-1">{t.adviceOnly}</p>
          <p className="mt-1">{t.wholesaleCaption}</p>
        </footer>
      </main>
      <FabMenu />
    </div>
  );
}
