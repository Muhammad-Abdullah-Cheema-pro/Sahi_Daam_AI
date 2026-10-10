"use client";

import { useCallback, useState } from "react";
import type { GeoPoint } from "@/types/domain";

export type GeoStatus =
  | "idle"
  | "loading"
  | "granted"
  | "denied"
  | "unavailable"
  | "timeout";

export function useGeolocation() {
  const [status, setStatus] = useState<GeoStatus>("idle");
  const [point, setPoint] = useState<GeoPoint | null>(null);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("unavailable");
      setError("Geolocation API missing");
      return;
    }
    setStatus("loading");
    setError(null);
    const timer = window.setTimeout(() => {
      setStatus("timeout");
      setError("timeout");
    }, 8000);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        window.clearTimeout(timer);
        setPoint({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
        });
        setStatus("granted");
      },
      (err) => {
        window.clearTimeout(timer);
        if (err.code === err.PERMISSION_DENIED) setStatus("denied");
        else if (err.code === err.TIMEOUT) setStatus("timeout");
        else setStatus("unavailable");
        setError(err.message);
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60_000 },
    );
  }, []);

  const simulate = useCallback((p: GeoPoint) => {
    setPoint(p);
    setStatus("granted");
    setError(null);
  }, []);

  return { status, point, error, request, simulate };
}
