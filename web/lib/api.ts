/**
 * Single API surface. Swap mock implementations for real HTTP using
 * NEXT_PUBLIC_API_URL without changing call sites.
 */
import { MARKETS, roadKm } from "@/lib/geo";
import { mockAnalyze, mockParse } from "@/mock/analyze";
import { MOCK_DATA_AS_OF, MOCK_PRICES } from "@/mock/prices";
import { mockWeather } from "@/mock/weather";
import type {
  AnalysisResult,
  Crop,
  GeoPoint,
  MandiCard,
  ParseOutcome,
  ParsedFarmerRequest,
  WeatherSnapshot,
} from "@/types/domain";

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

async function maybeFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  if (!BASE) return null;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    signal: (() => {
      const c = new AbortController();
      setTimeout(() => c.abort(), 5000);
      return c.signal;
    })(),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function parseInput(text: string): Promise<ParseOutcome> {
  try {
    const remote = await maybeFetch<ParseOutcome>("/parse", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    if (remote) return remote;
  } catch {
    /* fall through to mock */
  }
  return mockParse(text);
}

export async function analyze(
  request: ParsedFarmerRequest,
): Promise<AnalysisResult> {
  try {
    const remote = await maybeFetch<AnalysisResult>("/analyze", {
      method: "POST",
      body: JSON.stringify(request),
    });
    if (remote) return remote;
  } catch {
    /* fall through */
  }
  return mockAnalyze(request);
}

export async function getWeather(locationName: string): Promise<WeatherSnapshot> {
  try {
    const remote = await maybeFetch<WeatherSnapshot>(
      `/weather?location=${encodeURIComponent(locationName)}`,
    );
    if (remote) return remote;
  } catch {
    /* fall through */
  }
  return mockWeather(locationName);
}

export async function getMandis(origin: GeoPoint): Promise<MandiCard[]> {
  try {
    const remote = await maybeFetch<MandiCard[]>(
      `/mandis?lat=${origin.lat}&lon=${origin.lon}`,
    );
    if (remote) return remote;
  } catch {
    /* fall through */
  }

  const crops: Crop[] = ["Wheat", "Tomato", "Potato", "Onion"];
  return MARKETS.map((m) => ({
    name: m.name,
    lat: m.lat,
    lon: m.lon,
    distance_km: Math.round(roadKm(origin, m) * 10) / 10,
    prices: crops.map((crop) => {
      const price = MOCK_PRICES[m.name]?.[crop] ?? null;
      return {
        crop,
        price_rs_maund: price,
        data_as_of: price != null ? MOCK_DATA_AS_OF : null,
      };
    }),
    source: "MOCK" as const,
  })).sort((a, b) => a.distance_km - b.distance_km);
}
