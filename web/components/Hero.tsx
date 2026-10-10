"use client";

import {
  CloudRain,
  CloudSun,
  Droplets,
  Sun,
  Thermometer,
  Wind,
} from "lucide-react";
import { useEffect, useState } from "react";
import { DemoBadge } from "@/components/DemoBadge";
import { useApp } from "@/context/AppProvider";
import { useI18n } from "@/hooks/useI18n";
import { getWeather } from "@/lib/api";
import type { WeatherSnapshot } from "@/types/domain";

function ConditionIcon({
  condition,
}: {
  condition: WeatherSnapshot["condition"];
}) {
  const cls = "size-8 shrink-0";
  if (condition === "rain") return <CloudRain className={cls} aria-hidden />;
  if (condition === "partly_cloudy")
    return <CloudSun className={cls} aria-hidden />;
  if (condition === "windy") return <Wind className={cls} aria-hidden />;
  return <Sun className={cls} aria-hidden />;
}

export function Hero() {
  const { t, lang } = useI18n();
  const { state } = useApp();
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);
  const place = state.location?.district ?? "—";

  useEffect(() => {
    if (!state.location) {
      setWeather(null);
      return;
    }
    void getWeather(state.location.district).then(setWeather);
  }, [state.location]);

  return (
    <section
      id="hero"
      className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-900 via-emerald-800 to-emerald-700 px-5 py-8 text-emerald-50 shadow-lg sm:px-8"
      aria-labelledby="hero-title"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <DemoBadge />
        <span className="text-sm font-semibold opacity-90">AICON&apos;26</span>
      </div>
      <h1
        id="hero-title"
        className={
          lang === "ur"
            ? "font-nastaliq text-4xl leading-[2.1] sm:text-5xl"
            : "font-inter text-4xl font-extrabold leading-tight sm:text-5xl"
        }
      >
        {lang === "ur" ? t.appNameUrdu : t.appName}
      </h1>
      <p className="mt-3 max-w-prose text-lg font-semibold leading-relaxed">
        {t.heroTagline}
      </p>
      <p className="mt-2 max-w-prose text-base opacity-90">{t.heroSub}</p>

      <div className="mt-6 flex flex-wrap items-end gap-6 rounded-2xl bg-white/10 p-4 backdrop-blur">
        <div>
          <p className="text-sm opacity-80">{t.myLocation}</p>
          <p className="text-2xl font-bold">{place}</p>
        </div>
        {weather && (
          <div className="flex items-center gap-3">
            <ConditionIcon condition={weather.condition} />
            <div>
              <p className="flex items-center gap-1 text-sm opacity-80">
                <Thermometer className="size-4" aria-hidden />
                {t.temperature}
              </p>
              <p className="text-2xl font-bold">{weather.temp_c}°C</p>
              <p className="flex items-center gap-1 text-sm opacity-90">
                <Droplets className="size-4" aria-hidden />
                {t.currentCondition}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
