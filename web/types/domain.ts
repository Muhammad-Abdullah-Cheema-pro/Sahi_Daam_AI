/** Types mirrored from the Python `schema.py` backend. */

export type Crop = "Wheat" | "Tomato" | "Potato" | "Onion";

export type CropStage =
  | "Growing"
  | "Nearly ready"
  | "Ready to harvest"
  | "Harvested, not sold";

export type VerdictStatus = "Fair" | "Low" | "Very low" | "Unable to assess";

export type BandBasis = "model_band" | "recent_median_band" | "none";

export type WeatherRisk = "High" | "Medium" | "Low";

export type PriceTrend = "Rising" | "Flat" | "Falling";

export type Lang = "ur" | "en";

export type ThemeMode = "light" | "dark";

export interface ParsedFarmerRequest {
  crop: Crop;
  quantity_maunds: number;
  district: string;
  quoted_price_per_maund?: number | null;
  crop_stage: CropStage;
  confidence: number;
  language_detected?: string | null;
  raw_transcript?: string | null;
}

export interface FairPriceVerdict {
  reference_market: string;
  predicted_low_maund?: number | null;
  predicted_high_maund?: number | null;
  predicted_avg_maund?: number | null;
  verdict_status: VerdictStatus;
  percentage_gap?: number | null;
  reason?: string | null;
  basis: BandBasis;
  data_as_of?: string | null;
  sample_days?: number | null;
}

export interface CityMarginResult {
  city_name: string;
  distance_km: number;
  gross_price_maund: number;
  net_price_maund: number;
  net_gain_vs_quote: number;
  break_even_price: number;
  assumptions: string;
}

export interface HarvestAdvisory {
  weather_risk: WeatherRisk;
  price_trend: PriceTrend;
  action_advice: string;
  disclaimer: string;
}

export interface AnalysisResult {
  request: ParsedFarmerRequest;
  verdict: FairPriceVerdict;
  advisory?: HarvestAdvisory | null;
  top_cities: CityMarginResult[];
  disclaimers: string[];
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface MarketCoords {
  name: string;
  lat: number;
  lon: number;
}

export interface CropPrice {
  crop: Crop;
  price_rs_maund: number | null;
  data_as_of: string | null;
}

export interface MandiCard {
  name: string;
  lat: number;
  lon: number;
  distance_km: number;
  prices: CropPrice[];
  source: "MOCK";
}

export interface DayForecast {
  date: string;
  high_c: number;
  low_c: number;
  rain_chance_pct: number;
  wind_kmh: number;
}

export interface WeatherSnapshot {
  location_name: string;
  temp_c: number;
  condition: "sunny" | "partly_cloudy" | "rain" | "windy";
  risk: WeatherRisk;
  tip: string;
  days: DayForecast[];
  source: "MOCK";
}

export interface ParseOutcome {
  status: "ok" | "needs_clarification" | "failed";
  request: ParsedFarmerRequest | null;
  missing_fields: string[];
  message: string;
  source: "MOCK";
}

export interface UserLocation {
  lat: number;
  lon: number;
  district: string;
  simulated: boolean;
}
