import type { GeoPoint, MarketCoords } from "@/types/domain";

/** Matches Python `config.ROAD_FACTOR`. */
export const ROAD_FACTOR = 1.3;

/** AMIS markets — coordinates from product prompt / geo.py. */
export const MARKETS: MarketCoords[] = [
  { name: "Lahore", lat: 31.5497, lon: 74.3436 },
  { name: "Faisalabad", lat: 31.4504, lon: 73.135 },
  { name: "Gujranwala", lat: 32.1877, lon: 74.1945 },
  { name: "Multan", lat: 30.1575, lon: 71.5249 },
  { name: "Sargodha", lat: 32.0836, lon: 72.6711 },
  { name: "Okara", lat: 30.8138, lon: 73.4534 },
  { name: "Rawalpindi", lat: 33.5651, lon: 73.0169 },
];

/** Punjab districts used in confirmation form (subset aligned with backend lexicon). */
export const DISTRICTS: string[] = [
  "Lahore",
  "Faisalabad",
  "Gujranwala",
  "Multan",
  "Sargodha",
  "Okara",
  "Rawalpindi",
  "Kasur",
  "Sahiwal",
  "Bahawalpur",
  "Sialkot",
  "Sheikhupura",
];

export function haversineKm(a: GeoPoint, b: GeoPoint): number {
  const r = 6371;
  const p1 = (a.lat * Math.PI) / 180;
  const p2 = (b.lat * Math.PI) / 180;
  const dphi = ((b.lat - a.lat) * Math.PI) / 180;
  const dlmb = ((b.lon - a.lon) * Math.PI) / 180;
  const h =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

export function roadKm(a: GeoPoint, b: GeoPoint): number {
  return haversineKm(a, b) * ROAD_FACTOR;
}

export function nearestMarket(point: GeoPoint): MarketCoords {
  let best = MARKETS[0];
  let bestD = Infinity;
  for (const m of MARKETS) {
    const d = haversineKm(point, m);
    if (d < bestD) {
      bestD = d;
      best = m;
    }
  }
  return best;
}

export function coordsForDistrict(name: string): GeoPoint | null {
  const m = MARKETS.find((x) => x.name === name);
  if (m) return { lat: m.lat, lon: m.lon };
  return null;
}
