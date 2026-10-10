import type { Crop } from "@/types/domain";

/** Plausible round MOCK wholesale Rs/maund — never presented as live AMIS. */
export const MOCK_PRICES: Record<
  string,
  Partial<Record<Crop, number | null>>
> = {
  Lahore: { Wheat: 3800, Tomato: 5600, Potato: 2400, Onion: 7200 },
  Faisalabad: { Wheat: 3750, Tomato: 5200, Potato: 2300, Onion: 6800 },
  Gujranwala: { Wheat: null, Tomato: 5400, Potato: null, Onion: 7000 },
  Multan: { Wheat: null, Tomato: 5000, Potato: 2200, Onion: 6600 },
  Sargodha: { Wheat: 3700, Tomato: 4800, Potato: 2100, Onion: 6400 },
  Okara: { Wheat: null, Tomato: 4700, Potato: null, Onion: 6500 },
  Rawalpindi: { Wheat: 3900, Tomato: 5800, Potato: null, Onion: 7400 },
};

export const MOCK_DATA_AS_OF = "2026-10-09";
