"use client";

import { CloudSun, Mic, Store, Wallet, X } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/hooks/useI18n";

const LINKS = [
  { id: "check-price", icon: Wallet, labelKey: "checkPrice" as const },
  { id: "mandi", icon: Store, labelKey: "nearMandi" as const },
  { id: "weather", icon: CloudSun, labelKey: "weather" as const },
  { id: "check-price", icon: Mic, labelKey: "voiceNote" as const },
];

export function FabMenu() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  function go(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setOpen(false);
  }

  return (
    <div className="fixed bottom-5 end-5 z-50 flex flex-col items-end gap-2">
      {open && (
        <ul className="flex flex-col gap-2 rounded-2xl border border-emerald-800/20 bg-white p-2 shadow-lg dark:border-emerald-100/20 dark:bg-emerald-950">
          {LINKS.map((link, i) => {
            const Icon = link.icon;
            return (
              <li key={`${link.id}-${i}`}>
                <button
                  type="button"
                  onClick={() => go(link.id)}
                  className="inline-flex min-h-tap w-full items-center gap-2 rounded-xl px-3 text-start font-bold hover:bg-emerald-50 dark:hover:bg-emerald-900"
                >
                  <Icon className="size-5 rtl:scale-x-[-1]" aria-hidden />
                  {t[link.labelKey]}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-full bg-emerald-800 text-white shadow-lg"
        aria-expanded={open}
        aria-label={t.fabMenu}
      >
        {open ? <X className="size-6" aria-hidden /> : <Wallet className="size-6" aria-hidden />}
      </button>
    </div>
  );
}
