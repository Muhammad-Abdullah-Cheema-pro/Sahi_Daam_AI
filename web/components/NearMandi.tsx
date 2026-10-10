"use client";

import { ChevronDown, Store } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { DemoBadge } from "@/components/DemoBadge";
import { useApp } from "@/context/AppProvider";
import { useI18n } from "@/hooks/useI18n";
import { cropLabel } from "@/i18n";
import { getMandis } from "@/lib/api";
import type { Crop, MandiCard } from "@/types/domain";

const CROPS: Crop[] = ["Wheat", "Tomato", "Potato", "Onion"];

export function NearMandi() {
  const { t } = useI18n();
  const { state } = useApp();
  const [cards, setCards] = useState<MandiCard[]>([]);
  const [filter, setFilter] = useState<Crop | "all">("all");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!state.location) {
      setCards([]);
      return;
    }
    void getMandis({ lat: state.location.lat, lon: state.location.lon }).then(
      setCards,
    );
  }, [state.location]);

  const shown = useMemo(() => {
    if (filter === "all") return cards;
    return [...cards].sort((a, b) => {
      const pa = a.prices.find((p) => p.crop === filter)?.price_rs_maund;
      const pb = b.prices.find((p) => p.crop === filter)?.price_rs_maund;
      if (pa == null && pb == null) return a.distance_km - b.distance_km;
      if (pa == null) return 1;
      if (pb == null) return -1;
      return pb - pa;
    });
  }, [cards, filter]);

  return (
    <section
      id="mandi"
      className="space-y-4"
      aria-labelledby="mandi-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="mandi-title" className="text-xl font-bold">
          {t.nearMandi}
        </h2>
        <DemoBadge />
      </div>

      <div className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="crop-filter">
          {t.filterByCrop}
        </label>
        <select
          id="crop-filter"
          className="min-h-tap rounded-xl border border-emerald-800/20 bg-white px-3 dark:border-emerald-100/20 dark:bg-emerald-900"
          value={filter}
          onChange={(e) =>
            setFilter(e.target.value === "all" ? "all" : (e.target.value as Crop))
          }
        >
          <option value="all">{t.allCrops}</option>
          {CROPS.map((c) => (
            <option key={c} value={c}>
              {cropLabel(t, c)}
            </option>
          ))}
        </select>
      </div>

      {!state.location && (
        <p className="text-base text-[color:var(--muted)]">{t.chooseDistrict}</p>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((card) => (
          <article
            key={card.name}
            className="rounded-2xl border border-emerald-800/15 bg-white p-4 shadow-sm dark:border-emerald-100/10 dark:bg-emerald-950/40"
          >
            <header className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <Store className="size-5 shrink-0" aria-hidden />
                <h3 className="text-lg font-bold">{card.name}</h3>
              </div>
              <p className="text-sm font-semibold">
                {card.distance_km} {t.km}
                <span className="block text-xs font-normal opacity-70">
                  {t.approxRoad}
                </span>
              </p>
            </header>

            <ul className="mt-3 space-y-2">
              {card.prices.map((p) => (
                <li
                  key={p.crop}
                  className="flex items-baseline justify-between gap-2 text-base"
                >
                  <span>{cropLabel(t, p.crop)}</span>
                  <span className="text-end font-semibold">
                    {p.price_rs_maund == null ? (
                      t.noDataToday
                    ) : (
                      <>
                        {t.rs} {p.price_rs_maund} {t.perMaund}
                        <span className="block text-xs font-normal opacity-70">
                          {t.dataAsOf} {p.data_as_of}
                        </span>
                      </>
                    )}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-[color:var(--muted)]">
              {t.wholesaleCaption}
            </p>

            <button
              type="button"
              className="mt-3 inline-flex min-h-tap items-center gap-1 text-base font-bold text-emerald-800 dark:text-emerald-100"
              aria-expanded={open === card.name}
              onClick={() =>
                setOpen((prev) => (prev === card.name ? null : card.name))
              }
            >
              {t.details}
              <ChevronDown
                className={`size-4 transition-transform rtl:scale-x-[-1] ${open === card.name ? "rotate-180" : ""}`}
                aria-hidden
              />
            </button>
            {open === card.name && (
              <p className="mt-2 text-sm opacity-80">
                {card.lat.toFixed(2)}, {card.lon.toFixed(2)} · source:{" "}
                {card.source}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
