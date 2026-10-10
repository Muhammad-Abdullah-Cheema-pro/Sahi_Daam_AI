import { MARKETS, coordsForDistrict, roadKm } from "@/lib/geo";
import { MOCK_DATA_AS_OF, MOCK_PRICES } from "@/mock/prices";
import type {
  AnalysisResult,
  CityMarginResult,
  Crop,
  FairPriceVerdict,
  ParsedFarmerRequest,
  ParseOutcome,
} from "@/types/domain";

const COMMISSION = 0.04;
const TRANSPORT_RS_PER_MAUND_KM = 1.5;
const FARMGATE = 0.1;
const VERY_LOW_RATIO = 0.85;

const FORBIDDEN =
  /\b(cheat|fraud|scam|lying|gouging|thief|steal|dishonest)\b/i;

function bandFor(market: string, crop: Crop): {
  low: number;
  avg: number;
  high: number;
} | null {
  const p = MOCK_PRICES[market]?.[crop];
  if (p == null || p <= 0) return null;
  return {
    low: Math.round(p * 0.92 / 50) * 50,
    avg: p,
    high: Math.round(p * 1.08 / 50) * 50,
  };
}

function resolvePrice(crop: Crop, district: string): {
  market: string;
  band: { low: number; avg: number; high: number };
} | null {
  const origin = coordsForDistrict(district) ?? {
    lat: MARKETS[0].lat,
    lon: MARKETS[0].lon,
  };
  const ranked = [...MARKETS]
    .map((m) => ({
      m,
      band: bandFor(m.name, crop),
      d: roadKm(origin, m),
    }))
    .filter((x) => x.band != null)
    .sort((a, b) => a.d - b.d);
  if (ranked.length === 0 || !ranked[0].band) return null;
  return { market: ranked[0].m.name, band: ranked[0].band };
}

function assess(
  quote: number | null | undefined,
  market: string,
  band: { low: number; avg: number; high: number },
): FairPriceVerdict {
  if (quote == null) {
    return {
      reference_market: market,
      predicted_low_maund: band.low,
      predicted_avg_maund: band.avg,
      predicted_high_maund: band.high,
      verdict_status: "Unable to assess",
      percentage_gap: null,
      reason: "No quote provided. Wholesale band is shown for reference.",
      basis: "recent_median_band",
      data_as_of: MOCK_DATA_AS_OF,
      sample_days: 30,
    };
  }
  const adjLow = band.low * (1 - FARMGATE);
  const gap = ((quote - band.avg) / band.avg) * 100;
  let status: FairPriceVerdict["verdict_status"] = "Fair";
  if (quote < adjLow * VERY_LOW_RATIO) status = "Very low";
  else if (quote < adjLow) status = "Low";

  return {
    reference_market: market,
    predicted_low_maund: band.low,
    predicted_avg_maund: band.avg,
    predicted_high_maund: band.high,
    verdict_status: status,
    percentage_gap: Math.round(gap * 10) / 10,
    reason: null,
    basis: "recent_median_band",
    data_as_of: MOCK_DATA_AS_OF,
    sample_days: 30,
  };
}

function rankCities(req: ParsedFarmerRequest): CityMarginResult[] {
  const origin = coordsForDistrict(req.district) ?? {
    lat: MARKETS[0].lat,
    lon: MARKETS[0].lon,
  };
  const rows: CityMarginResult[] = [];
  for (const m of MARKETS) {
    const band = bandFor(m.name, req.crop);
    if (!band) continue;
    const dist = roadKm(origin, m);
    const transport = dist * TRANSPORT_RS_PER_MAUND_KM;
    const net = band.avg * (1 - COMMISSION) - transport;
    const baseline = req.quoted_price_per_maund ?? net;
    rows.push({
      city_name: m.name,
      distance_km: Math.round(dist * 10) / 10,
      gross_price_maund: band.avg,
      net_price_maund: Math.round(net),
      net_gain_vs_quote: Math.round(net - baseline),
      break_even_price: Math.round((baseline + transport) / (1 - COMMISSION)),
      assumptions: `ASSUMPTION transport=${TRANSPORT_RS_PER_MAUND_KM} Rs/maund/km; commission=${COMMISSION * 100}%`,
    });
  }
  return rows.sort((a, b) => b.net_price_maund - a.net_price_maund).slice(0, 3);
}

export function mockParse(text: string): ParseOutcome {
  const lower = text.toLowerCase();
  let crop: ParsedFarmerRequest["crop"] | null = null;
  if (/tomato|tamatar|ٹماٹر/.test(lower) || /ٹماٹر/.test(text)) crop = "Tomato";
  else if (/wheat|gandum|گندم/.test(lower) || /گندم/.test(text)) crop = "Wheat";
  else if (/potato|aloo|آلو/.test(lower) || /آلو/.test(text)) crop = "Potato";
  else if (/onion|pyaz|پیاز/.test(lower) || /پیاز/.test(text)) crop = "Onion";

  const qtyMatch = text.match(/(\d+(?:\.\d+)?)\s*(maund|من|man)/i);
  const qty = qtyMatch ? Number(qtyMatch[1]) : null;

  let district: string | null = null;
  for (const d of [
    "Okara",
    "Lahore",
    "Faisalabad",
    "Multan",
    "Sargodha",
    "Gujranwala",
    "Rawalpindi",
  ]) {
    if (text.toLowerCase().includes(d.toLowerCase()) || text.includes(d)) {
      district = d;
      break;
    }
  }
  if (/اوکاڑہ|اوکاڑا/.test(text)) district = "Okara";

  const priceMatch = text.match(/(\d{3,5})\s*(rupay|rupees|روپے|rs)?/i);
  const quote = priceMatch ? Number(priceMatch[1]) : null;

  const missing: string[] = [];
  if (!crop) missing.push("crop");
  if (!qty || qty <= 0) missing.push("quantity_maunds");
  if (!district) missing.push("district");

  if (missing.length) {
    return {
      status: "needs_clarification",
      request: crop
        ? {
            crop,
            quantity_maunds: qty && qty > 0 ? qty : 1,
            district: district ?? "Lahore",
            quoted_price_per_maund: quote,
            crop_stage: "Ready to harvest",
            confidence: 0.5,
            language_detected: /[؀-ۿ]/.test(text) ? "ur" : "en",
            raw_transcript: text,
          }
        : null,
      missing_fields: missing,
      message: "Please confirm the missing fields.",
      source: "MOCK",
    };
  }

  return {
    status: "ok",
    request: {
      crop: crop!,
      quantity_maunds: qty!,
      district: district!,
      quoted_price_per_maund: quote,
      crop_stage: "Ready to harvest",
      confidence: 0.85,
      language_detected: /[؀-ۿ]/.test(text) ? "ur" : "roman-ur",
      raw_transcript: text,
    },
    missing_fields: [],
    message: "Parsed successfully — please confirm.",
    source: "MOCK",
  };
}

export function mockAnalyze(request: ParsedFarmerRequest): AnalysisResult {
  const resolved = resolvePrice(request.crop, request.district);
  if (!resolved) {
    const verdict: FairPriceVerdict = {
      reference_market: request.district,
      verdict_status: "Unable to assess",
      basis: "none",
      reason: `No market has usable WHOLESALE data for ${request.crop}. Comparison is against WHOLESALE prices.`,
      data_as_of: MOCK_DATA_AS_OF,
      sample_days: 0,
    };
    return {
      request,
      verdict,
      advisory: null,
      top_cities: [],
      disclaimers: [
        "WHOLESALE mandi prices are not farm-gate prices.",
        "MOCK demo data — not a live AMIS scrape.",
      ],
    };
  }

  const verdict = assess(
    request.quoted_price_per_maund,
    resolved.market,
    resolved.band,
  );
  const top = rankCities(request);
  const risk =
    request.district === "Multan" ? "High" : request.district === "Lahore" ? "Medium" : "Low";
  const trend =
    verdict.percentage_gap != null && verdict.percentage_gap < -10
      ? "Falling"
      : "Flat";

  let advice =
    risk === "High"
      ? "Weather risk is High. Prefer the next dry window; cover produce with tarpaulins; improve ventilation."
      : risk === "Medium"
        ? "Weather risk is Medium. Check the sky daily; keep tarpaulins ready; provide shade and airflow."
        : "Weather risk is Low. Choose harvest timing based on market readiness; keep shade and ventilation.";

  if (FORBIDDEN.test(advice)) {
    advice = "Keep produce shaded and ventilated. Advice only.";
  }

  return {
    request,
    verdict,
    advisory:
      request.crop_stage === "Growing"
        ? null
        : {
            weather_risk: risk,
            price_trend: trend,
            action_advice: advice,
            disclaimer:
              "Advice only. Consult local agricultural extension standard practices.",
          },
    top_cities: top,
    disclaimers: [
      "WHOLESALE mandi prices are not farm-gate prices.",
      "Transport, commission and farm-gate rates are ASSUMPTIONS.",
      "MOCK demo data — not a live AMIS scrape.",
      `Band basis=${verdict.basis}, data_as_of=${verdict.data_as_of}.`,
    ],
  };
}

export const SAMPLE_TRANSCRIPT =
  "40 maund tamatar hain Okara mein, broker 2800 de raha hai";
