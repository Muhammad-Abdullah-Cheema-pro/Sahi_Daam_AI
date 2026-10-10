"use client";

import { Volume2 } from "lucide-react";
import { useI18n } from "@/hooks/useI18n";
import { verdictLabel } from "@/i18n";
import type { AnalysisResult } from "@/types/domain";

const EMOJI = {
  Fair: "✅",
  Low: "⚠️",
  "Very low": "🚨",
  "Unable to assess": "❔",
} as const;

const COLORS = {
  Fair: "border-emerald-600 bg-emerald-50 text-emerald-950 dark:bg-emerald-950 dark:text-emerald-50",
  Low: "border-amber-500 bg-amber-50 text-amber-950 dark:bg-amber-950 dark:text-amber-50",
  "Very low": "border-red-600 bg-red-50 text-red-950 dark:bg-red-950 dark:text-red-50",
  "Unable to assess":
    "border-slate-500 bg-slate-100 text-slate-900 dark:bg-slate-900 dark:text-slate-100",
} as const;

export function VerdictCard({ result }: { result: AnalysisResult }) {
  const { t } = useI18n();
  const v = result.verdict;
  const status = v.verdict_status;

  let sentence = v.reason ?? t.unable;
  if (status === "Fair") sentence = t.quoteWithin;
  else if (status === "Low") sentence = t.quoteBelow;
  else if (status === "Very low") sentence = t.quoteWellBelow;

  const hasQuote = result.request.quoted_price_per_maund != null;

  return (
    <div className="space-y-4">
      <div className={`rounded-2xl border-2 p-5 ${COLORS[status]}`}>
        <p className="text-2xl font-extrabold">
          {EMOJI[status]} {verdictLabel(t, status)}
        </p>
        <p className="mt-2 text-base leading-relaxed">
          {sentence} {t.wholesaleCaption}
        </p>
        {v.percentage_gap != null && (
          <p className="mt-2 font-semibold">
            {t.gapVsAvg}: {v.percentage_gap > 0 ? "+" : ""}
            {v.percentage_gap}%
          </p>
        )}
        {v.predicted_low_maund != null &&
          v.predicted_avg_maund != null &&
          v.predicted_high_maund != null && (
            <p className="mt-2 text-base">
              {t.bandLabel}: {v.predicted_low_maund} – {v.predicted_avg_maund} –{" "}
              {v.predicted_high_maund} {t.rs} {t.perMaund}
            </p>
          )}
        <p className="mt-2 text-sm opacity-80">
          {t.referenceMarket}: <strong>{v.reference_market}</strong>
          {v.data_as_of ? ` · ${t.dataAsOf} ${v.data_as_of}` : ""}
        </p>
      </div>

      {result.advisory && (
        <div className="rounded-2xl border border-emerald-800/15 bg-white p-4 dark:border-emerald-100/10 dark:bg-emerald-950/40">
          <h3 className="font-bold">{t.harvestAdvice}</h3>
          <p className="mt-1 text-base">
            {t.risk}: {result.advisory.weather_risk} · {t.priceTrend}:{" "}
            {result.advisory.price_trend}
          </p>
          <p className="mt-2 text-base leading-relaxed">
            {result.advisory.action_advice}
          </p>
          <p className="mt-2 text-sm opacity-80">{result.advisory.disclaimer}</p>
        </div>
      )}

      {result.top_cities.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-emerald-800/15 bg-white dark:border-emerald-100/10 dark:bg-emerald-950/40">
          <h3 className="p-4 pb-0 text-lg font-bold">{t.topCities}</h3>
          <table className="mt-2 w-full min-w-[36rem] text-start text-base">
            <thead>
              <tr className="border-b border-emerald-800/10 text-sm dark:border-emerald-100/10">
                <th className="p-3 font-bold">{t.city}</th>
                <th className="p-3 font-bold">
                  {t.distance} ({t.km})
                </th>
                <th className="p-3 font-bold">{t.gross}</th>
                <th className="p-3 font-bold">{t.net}</th>
                {hasQuote && <th className="p-3 font-bold">{t.netGain}</th>}
                <th className="p-3 font-bold">{t.breakEven}</th>
              </tr>
            </thead>
            <tbody>
              {result.top_cities.map((c) => (
                <tr
                  key={c.city_name}
                  className="border-b border-emerald-800/5 dark:border-emerald-100/5"
                >
                  <td className="p-3">{c.city_name}</td>
                  <td className="p-3">{c.distance_km}</td>
                  <td className="p-3">{c.gross_price_maund}</td>
                  <td className="p-3">{c.net_price_maund}</td>
                  {hasQuote && <td className="p-3">{c.net_gain_vs_quote}</td>}
                  <td className="p-3">{c.break_even_price}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="p-3 text-sm text-[color:var(--muted)]">
            {t.estimatesCaption}
          </p>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex min-h-tap items-center gap-2 rounded-xl bg-emerald-800 px-4 font-bold text-white"
          onClick={() => {
            const el = document.getElementById("urdu-audio") as HTMLAudioElement | null;
            void el?.play().catch(() => undefined);
          }}
        >
          <Volume2 className="size-5" aria-hidden />
          {t.listenUrdu}
        </button>
        {/* Placeholder silent-ish data URI; real app uses gTTS */}
        <audio id="urdu-audio" preload="none" className="sr-only">
          <source src="data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=" type="audio/wav" />
        </audio>
      </div>

      <details className="rounded-xl border border-emerald-800/15 p-3 dark:border-emerald-100/10">
        <summary className="min-h-tap cursor-pointer font-bold">
          {t.disclaimers}
        </summary>
        <ul className="mt-2 list-disc space-y-1 ps-5 text-sm">
          {result.disclaimers.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
