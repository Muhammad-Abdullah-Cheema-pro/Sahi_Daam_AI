"use client";

import { AlertTriangle, CloudRain, Droplets, Wind, X } from "lucide-react";
import { useEffect, useState } from "react";
import { DemoBadge } from "@/components/DemoBadge";
import { useApp } from "@/context/AppProvider";
import { useI18n } from "@/hooks/useI18n";
import { riskLabel } from "@/i18n";
import { getWeather } from "@/lib/api";
import type { WeatherSnapshot } from "@/types/domain";

export function WeatherOutlook() {
  const { t } = useI18n();
  const { state, dismissAlert } = useApp();
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);

  useEffect(() => {
    if (!state.location) {
      setWeather(null);
      return;
    }
    void getWeather(state.location.district).then(setWeather);
  }, [state.location]);

  if (!weather) return null;

  const riskColor =
    weather.risk === "High"
      ? "bg-red-100 text-red-900 border-red-500 dark:bg-red-950 dark:text-red-100"
      : weather.risk === "Medium"
        ? "bg-amber-100 text-amber-950 border-amber-500 dark:bg-amber-950 dark:text-amber-100"
        : "bg-emerald-100 text-emerald-950 border-emerald-600 dark:bg-emerald-950 dark:text-emerald-100";

  return (
    <section
      id="weather"
      className="space-y-4"
      aria-labelledby="weather-title"
    >
      {weather.risk === "High" && !state.alertDismissed && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-2xl border-2 border-red-600 bg-red-50 p-4 text-red-950 dark:bg-red-950 dark:text-red-50"
        >
          <div className="flex gap-2">
            <AlertTriangle className="mt-0.5 size-6 shrink-0" aria-hidden />
            <div>
              <p className="font-bold">
                {t.risk}: {riskLabel(t, "High")}
              </p>
              <p className="mt-1 text-base">{weather.tip}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={dismissAlert}
            className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-lg"
            aria-label={t.dismissAlert}
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>
      )}

      <article className="rounded-2xl border border-emerald-800/15 bg-white p-5 shadow-sm dark:border-emerald-100/10 dark:bg-emerald-950/40">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="weather-title" className="text-xl font-bold">
            {t.weatherOutlook}
          </h2>
          <DemoBadge />
        </div>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          {t.next72h} · {weather.location_name}
        </p>

        <div
          className={`mt-4 inline-flex min-h-tap items-center gap-2 rounded-full border-2 px-3 py-1 font-bold ${riskColor}`}
        >
          <AlertTriangle className="size-4" aria-hidden />
          {t.risk}: {riskLabel(t, weather.risk)}
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {weather.days.map((d) => (
            <div
              key={d.date}
              className="rounded-xl border border-emerald-800/10 bg-sand-50 p-3 dark:border-emerald-100/10 dark:bg-emerald-900/50"
            >
              <p className="font-bold">{d.date}</p>
              <p className="mt-1 text-base">
                {t.high} {d.high_c}° / {t.lowTemp} {d.low_c}°
              </p>
              <p className="mt-1 flex items-center gap-1 text-sm">
                <Droplets className="size-4" aria-hidden />
                {t.rainChance}: {d.rain_chance_pct}%
              </p>
              <p className="mt-1 flex items-center gap-1 text-sm">
                <Wind className="size-4" aria-hidden />
                {t.wind}: {d.wind_kmh} {t.km}/h
              </p>
              <CloudRain className="mt-2 size-5 opacity-60" aria-hidden />
            </div>
          ))}
        </div>

        <p className="mt-4 text-base leading-relaxed">{weather.tip}</p>
        <p className="mt-3 text-sm text-[color:var(--muted)]">{t.adviceOnly}</p>
        <p className="mt-1 text-xs opacity-70">{t.weatherMockNote}</p>
      </article>
    </section>
  );
}
