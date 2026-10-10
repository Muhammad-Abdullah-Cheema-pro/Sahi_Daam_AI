import { en, type Dict } from "@/i18n/en";
import { ur } from "@/i18n/ur";
import type { Crop, CropStage, Lang, VerdictStatus, WeatherRisk } from "@/types/domain";

export type { Dict };

export const dictionaries: Record<Lang, Dict> = { ur, en };

export function cropLabel(t: Dict, crop: Crop): string {
  const map: Record<Crop, string> = {
    Wheat: t.wheat,
    Tomato: t.tomato,
    Potato: t.potato,
    Onion: t.onion,
  };
  return map[crop];
}

export function stageLabel(t: Dict, stage: CropStage): string {
  const map: Record<CropStage, string> = {
    Growing: t.stageGrowing,
    "Nearly ready": t.stageNearly,
    "Ready to harvest": t.stageReady,
    "Harvested, not sold": t.stageHarvested,
  };
  return map[stage];
}

export function verdictLabel(t: Dict, status: VerdictStatus): string {
  const map: Record<VerdictStatus, string> = {
    Fair: t.fair,
    Low: t.low,
    "Very low": t.veryLow,
    "Unable to assess": t.unable,
  };
  return map[status];
}

export function riskLabel(t: Dict, risk: WeatherRisk): string {
  const map: Record<WeatherRisk, string> = {
    High: t.riskHigh,
    Medium: t.riskMedium,
    Low: t.riskLow,
  };
  return map[risk];
}
