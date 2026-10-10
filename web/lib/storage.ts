/** Safe localStorage helpers — never throw across SSR. */

export function readStorage(key: string): string | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string): void {
  try {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode / quota */
  }
}

export const STORAGE_KEYS = {
  lang: "sahi-daam-lang",
  theme: "sahi-daam-theme",
  location: "sahi-daam-location",
} as const;
