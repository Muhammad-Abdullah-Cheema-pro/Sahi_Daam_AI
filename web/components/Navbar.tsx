"use client";

import { MapPin, Moon, Sun, Wheat } from "lucide-react";
import { DemoBadge } from "@/components/DemoBadge";
import { useApp } from "@/context/AppProvider";
import { useI18n } from "@/hooks/useI18n";

export function Navbar() {
  const { t, lang, toggleLang } = useI18n();
  const { state, toggleTheme } = useApp();

  return (
    <header className="sticky top-0 z-40 border-b border-emerald-800/15 bg-sand-50/95 backdrop-blur dark:border-emerald-100/10 dark:bg-emerald-950/95">
      <nav
        className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3"
        aria-label="Primary"
      >
        <a
          href="#main"
          className="flex min-h-tap items-center gap-2 font-bold text-emerald-800 dark:text-emerald-50"
        >
          <Wheat className="size-7 shrink-0" aria-hidden />
          <span className="leading-tight">
            <span className="block text-base">{t.appName}</span>
            <span className="block font-naskh text-sm opacity-90">
              {t.appNameUrdu}
            </span>
          </span>
        </a>

        <div className="flex flex-wrap items-center gap-2">
          <DemoBadge />
          {state.location && (
            <span className="inline-flex min-h-tap items-center gap-1 rounded-full bg-emerald-100 px-3 text-sm font-semibold text-emerald-900 dark:bg-emerald-900 dark:text-emerald-50">
              <MapPin className="size-4" aria-hidden />
              {state.location.district}
            </span>
          )}
          <button
            type="button"
            onClick={toggleLang}
            className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl border border-emerald-800/20 bg-white px-3 text-sm font-bold text-emerald-900 transition-lang dark:border-emerald-100/20 dark:bg-emerald-900 dark:text-emerald-50"
            aria-label={t.languageToggle}
          >
            {lang === "ur" ? "English" : "اردو"}
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl border border-emerald-800/20 bg-white dark:border-emerald-100/20 dark:bg-emerald-900"
            aria-label={state.theme === "dark" ? t.themeLight : t.themeDark}
          >
            {state.theme === "dark" ? (
              <Sun className="size-5" aria-hidden />
            ) : (
              <Moon className="size-5" aria-hidden />
            )}
          </button>
        </div>
      </nav>
    </header>
  );
}
