import type { WeatherRisk, WeatherSnapshot } from "@/types/domain";

function tipFor(risk: WeatherRisk): string {
  if (risk === "High") {
    return "Rain or heat risk is high. Decide soon; shade or cover harvested produce.";
  }
  if (risk === "Medium") {
    return "Watch the sky daily. Keep tarpaulins ready and provide shade and airflow.";
  }
  return "Weather risk is low. Time harvest by market readiness; keep basic shade.";
}

/** MOCK 72 h outlook — real app uses Open-Meteo. */
export function mockWeather(locationName: string): WeatherSnapshot {
  const risk: WeatherRisk =
    locationName === "Multan" || locationName === "Bahawalpur"
      ? "High"
      : locationName === "Lahore" || locationName === "Faisalabad"
        ? "Medium"
        : "Low";

  const baseTemp = risk === "High" ? 36 : risk === "Medium" ? 32 : 28;

  return {
    location_name: locationName,
    temp_c: baseTemp,
    condition: risk === "High" ? "rain" : risk === "Medium" ? "partly_cloudy" : "sunny",
    risk,
    tip: tipFor(risk),
    days: [
      {
        date: "2026-10-10",
        high_c: baseTemp + 2,
        low_c: baseTemp - 8,
        rain_chance_pct: risk === "High" ? 70 : risk === "Medium" ? 40 : 15,
        wind_kmh: risk === "High" ? 28 : 18,
      },
      {
        date: "2026-10-11",
        high_c: baseTemp + 1,
        low_c: baseTemp - 7,
        rain_chance_pct: risk === "High" ? 55 : risk === "Medium" ? 30 : 10,
        wind_kmh: 16,
      },
      {
        date: "2026-10-12",
        high_c: baseTemp,
        low_c: baseTemp - 9,
        rain_chance_pct: risk === "High" ? 45 : 20,
        wind_kmh: 14,
      },
    ],
    source: "MOCK",
  };
}
