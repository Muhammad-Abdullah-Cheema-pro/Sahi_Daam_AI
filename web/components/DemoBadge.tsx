"use client";

import { useI18n } from "@/hooks/useI18n";

export function DemoBadge() {
  const { t } = useI18n();
  return (
    <span
      className="inline-flex min-h-tap items-center rounded-full border border-clay-500/40 bg-clay-50 px-3 text-sm font-bold text-clay-700 dark:border-clay-300/40 dark:bg-clay-700/30 dark:text-clay-100"
      title="source: MOCK"
    >
      {t.demoBadge}
    </span>
  );
}
