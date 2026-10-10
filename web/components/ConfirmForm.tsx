"use client";

import { useI18n } from "@/hooks/useI18n";
import { cropLabel, stageLabel } from "@/i18n";
import { DISTRICTS } from "@/lib/geo";
import type { Crop, CropStage, ParsedFarmerRequest } from "@/types/domain";

const CROPS: Crop[] = ["Wheat", "Tomato", "Potato", "Onion"];
const STAGES: CropStage[] = [
  "Growing",
  "Nearly ready",
  "Ready to harvest",
  "Harvested, not sold",
];

interface Props {
  draft: ParsedFarmerRequest;
  errors: Record<string, string>;
  busy: boolean;
  onChange: (patch: Partial<ParsedFarmerRequest>) => void;
  onConfirm: () => void;
}

export function ConfirmForm({
  draft,
  errors,
  busy,
  onChange,
  onConfirm,
}: Props) {
  const { t } = useI18n();

  return (
    <form
      className="grid grid-cols-1 gap-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        onConfirm();
      }}
    >
      <div>
        <label htmlFor="crop" className="font-bold">
          {t.crop}
        </label>
        <select
          id="crop"
          className="mt-1 min-h-tap w-full rounded-xl border border-emerald-800/20 px-3 dark:bg-emerald-900"
          value={draft.crop}
          onChange={(e) => onChange({ crop: e.target.value as Crop })}
        >
          {CROPS.map((c) => (
            <option key={c} value={c}>
              {cropLabel(t, c)}
            </option>
          ))}
        </select>
        {errors.crop && (
          <p className="mt-1 text-sm text-red-700" role="alert">
            {errors.crop}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="qty" className="font-bold">
          {t.quantityMaunds}
        </label>
        <input
          id="qty"
          type="number"
          min={0.01}
          step={1}
          className="mt-1 min-h-tap w-full rounded-xl border border-emerald-800/20 px-3 dark:bg-emerald-900"
          value={draft.quantity_maunds}
          onChange={(e) => onChange({ quantity_maunds: Number(e.target.value) })}
        />
        {errors.quantity && (
          <p className="mt-1 text-sm text-red-700" role="alert">
            {errors.quantity}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="district" className="font-bold">
          {t.district}
        </label>
        <select
          id="district"
          className="mt-1 min-h-tap w-full rounded-xl border border-emerald-800/20 px-3 dark:bg-emerald-900"
          value={draft.district}
          onChange={(e) => onChange({ district: e.target.value })}
        >
          {DISTRICTS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        {errors.district && (
          <p className="mt-1 text-sm text-red-700" role="alert">
            {errors.district}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="stage" className="font-bold">
          {t.cropStage}
        </label>
        <select
          id="stage"
          className="mt-1 min-h-tap w-full rounded-xl border border-emerald-800/20 px-3 dark:bg-emerald-900"
          value={draft.crop_stage}
          onChange={(e) =>
            onChange({ crop_stage: e.target.value as CropStage })
          }
        >
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {stageLabel(t, s)}
            </option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <label className="flex min-h-tap items-center gap-2 font-bold">
          <input
            type="checkbox"
            checked={draft.quoted_price_per_maund == null}
            onChange={(e) =>
              onChange({
                quoted_price_per_maund: e.target.checked ? null : 2800,
              })
            }
          />
          {t.noQuote}
        </label>
        {draft.quoted_price_per_maund != null && (
          <>
            <label htmlFor="quote" className="mt-2 block font-bold">
              {t.quotedPrice} ({t.rs} {t.perMaund}) — {t.optional}
            </label>
            <input
              id="quote"
              type="number"
              min={1}
              className="mt-1 min-h-tap w-full rounded-xl border border-emerald-800/20 px-3 dark:bg-emerald-900"
              value={draft.quoted_price_per_maund}
              onChange={(e) =>
                onChange({ quoted_price_per_maund: Number(e.target.value) })
              }
            />
          </>
        )}
      </div>
      <div className="sm:col-span-2">
        <button
          type="submit"
          disabled={busy}
          className="inline-flex min-h-tap w-full items-center justify-center rounded-xl bg-emerald-800 text-lg font-bold text-white disabled:opacity-60"
        >
          {t.confirmVerdict}
        </button>
      </div>
    </form>
  );
}
