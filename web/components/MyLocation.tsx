"use client";

import { MapPin } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/context/AppProvider";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useI18n } from "@/hooks/useI18n";
import { DISTRICTS, coordsForDistrict, nearestMarket } from "@/lib/geo";

const DEMO = { lat: 30.8138, lon: 73.4534, district: "Okara" };

export function MyLocation() {
  const { t } = useI18n();
  const { state, setLocation } = useApp();
  const geo = useGeolocation();
  const [query, setQuery] = useState("");
  const [manual, setManual] = useState(state.location?.district ?? "");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return DISTRICTS;
    return DISTRICTS.filter((d) => d.toLowerCase().includes(q));
  }, [query]);

  useEffect(() => {
    if (geo.status !== "granted" || !geo.point) return;
    const nearest = nearestMarket(geo.point);
    setLocation({
      lat: geo.point.lat,
      lon: geo.point.lon,
      district: nearest.name,
      simulated: false,
    });
  }, [geo.status, geo.point, setLocation]);

  const statusText = (() => {
    switch (geo.status) {
      case "loading":
        return t.searchingLocation;
      case "granted":
        return t.locationGranted;
      case "denied":
        return t.locationDenied;
      case "unavailable":
        return t.locationUnavailable;
      case "timeout":
        return t.locationTimeout;
      default:
        return t.locationHintHttps;
    }
  })();

  function applyPoint(lat: number, lon: number, simulated: boolean) {
    const nearest = nearestMarket({ lat, lon });
    setLocation({ lat, lon, district: nearest.name, simulated });
  }

  function onUseLocation() {
    if (process.env.NEXT_PUBLIC_SIMULATE_GEO === "1") {
      geo.simulate(DEMO);
      applyPoint(DEMO.lat, DEMO.lon, true);
      return;
    }
    geo.request();
  }

  return (
    <section
      id="location"
      className="rounded-2xl border border-emerald-800/15 bg-white p-5 shadow-sm dark:border-emerald-100/10 dark:bg-emerald-950/40"
      aria-labelledby="location-title"
    >
      <h2 id="location-title" className="text-xl font-bold">
        {t.myLocation}
      </h2>
      <p className="mt-1 text-base text-[color:var(--muted)]">
        {t.locationHintHttps}
      </p>

      <button
        type="button"
        onClick={onUseLocation}
        className="mt-4 inline-flex min-h-tap w-full items-center justify-center gap-2 rounded-xl bg-emerald-800 px-4 text-base font-bold text-white sm:w-auto"
      >
        <MapPin className="size-5" aria-hidden />
        {geo.status === "loading" ? t.searchingLocation : t.useMyLocation}
      </button>

      <p className="mt-3 text-sm" role="status" aria-live="polite">
        {statusText}
      </p>

      {state.location && (
        <p className="mt-2 text-base">
          <strong>{t.matchedCity}:</strong> {state.location.district} ·{" "}
          {t.coords}: {state.location.lat.toFixed(2)},{" "}
          {state.location.lon.toFixed(2)}
          {state.location.simulated ? " (demo)" : ""}
        </p>
      )}

      <div className="mt-5 space-y-3 border-t border-emerald-800/10 pt-4 dark:border-emerald-100/10">
        <label className="block text-base font-bold" htmlFor="district-search">
          {t.chooseDistrict}
        </label>
        <input
          id="district-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.searchDistrict}
          className="min-h-tap w-full rounded-xl border border-emerald-800/20 bg-sand-50 px-3 dark:border-emerald-100/20 dark:bg-emerald-900"
        />
        <select
          id="district-select"
          className="min-h-tap w-full rounded-xl border border-emerald-800/20 bg-white px-3 dark:border-emerald-100/20 dark:bg-emerald-900"
          value={manual}
          onChange={(e) => {
            const name = e.target.value;
            setManual(name);
            const c = coordsForDistrict(name);
            if (c) applyPoint(c.lat, c.lon, false);
          }}
          aria-label={t.chooseDistrict}
        >
          <option value="">{t.selectDistrict}</option>
          {filtered.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => {
            geo.simulate(DEMO);
            applyPoint(DEMO.lat, DEMO.lon, true);
          }}
          className="inline-flex min-h-tap items-center rounded-xl border border-clay-500 px-4 font-bold text-clay-700 dark:text-clay-100"
        >
          {t.demoLocation}
        </button>
      </div>
    </section>
  );
}
