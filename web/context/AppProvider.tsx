"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";
import { I18nProvider } from "@/hooks/useI18n";
import { STORAGE_KEYS, readStorage, writeStorage } from "@/lib/storage";
import type {
  AnalysisResult,
  ParsedFarmerRequest,
  ThemeMode,
  UserLocation,
} from "@/types/domain";

interface AppState {
  theme: ThemeMode;
  location: UserLocation | null;
  draft: ParsedFarmerRequest | null;
  transcript: string;
  result: AnalysisResult | null;
  alertDismissed: boolean;
}

type Action =
  | { type: "SET_THEME"; theme: ThemeMode }
  | { type: "SET_LOCATION"; location: UserLocation }
  | { type: "SET_DRAFT"; draft: ParsedFarmerRequest | null }
  | { type: "SET_TRANSCRIPT"; transcript: string }
  | { type: "SET_RESULT"; result: AnalysisResult | null }
  | { type: "DISMISS_ALERT" };

const initial: AppState = {
  theme: "light",
  location: null,
  draft: null,
  transcript: "",
  result: null,
  alertDismissed: false,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_THEME":
      return { ...state, theme: action.theme };
    case "SET_LOCATION":
      return { ...state, location: action.location, alertDismissed: false };
    case "SET_DRAFT":
      return { ...state, draft: action.draft };
    case "SET_TRANSCRIPT":
      return { ...state, transcript: action.transcript };
    case "SET_RESULT":
      return { ...state, result: action.result };
    case "DISMISS_ALERT":
      return { ...state, alertDismissed: true };
    default:
      return state;
  }
}

interface AppCtx {
  state: AppState;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  setLocation: (location: UserLocation) => void;
  setDraft: (draft: ParsedFarmerRequest | null) => void;
  setTranscript: (text: string) => void;
  setResult: (result: AnalysisResult | null) => void;
  dismissAlert: () => void;
}

const Ctx = createContext<AppCtx | null>(null);

function ThemeI18nShell({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);

  useEffect(() => {
    const savedTheme = readStorage(STORAGE_KEYS.theme);
    if (savedTheme === "dark" || savedTheme === "light") {
      dispatch({ type: "SET_THEME", theme: savedTheme });
    }
    const savedLoc = readStorage(STORAGE_KEYS.location);
    if (savedLoc) {
      try {
        const parsed = JSON.parse(savedLoc) as UserLocation;
        if (parsed?.district && typeof parsed.lat === "number") {
          dispatch({ type: "SET_LOCATION", location: parsed });
        }
      } catch {
        /* ignore */
      }
    } else if (process.env.NEXT_PUBLIC_SIMULATE_GEO === "1") {
      dispatch({
        type: "SET_LOCATION",
        location: {
          lat: 30.8138,
          lon: 73.4534,
          district: "Okara",
          simulated: true,
        },
      });
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", state.theme === "dark");
    writeStorage(STORAGE_KEYS.theme, state.theme);
  }, [state.theme]);

  useEffect(() => {
    if (state.location) {
      writeStorage(STORAGE_KEYS.location, JSON.stringify(state.location));
    }
  }, [state.location]);

  const setTheme = useCallback(
    (theme: ThemeMode) => dispatch({ type: "SET_THEME", theme }),
    [],
  );
  const toggleTheme = useCallback(() => {
    dispatch({
      type: "SET_THEME",
      theme: state.theme === "dark" ? "light" : "dark",
    });
  }, [state.theme]);
  const setLocation = useCallback((location: UserLocation) => {
    dispatch({ type: "SET_LOCATION", location });
  }, []);
  const setDraft = useCallback((draft: ParsedFarmerRequest | null) => {
    dispatch({ type: "SET_DRAFT", draft });
  }, []);
  const setTranscript = useCallback((transcript: string) => {
    dispatch({ type: "SET_TRANSCRIPT", transcript });
  }, []);
  const setResult = useCallback((result: AnalysisResult | null) => {
    dispatch({ type: "SET_RESULT", result });
  }, []);
  const dismissAlert = useCallback(() => {
    dispatch({ type: "DISMISS_ALERT" });
  }, []);

  const value = useMemo(
    () => ({
      state,
      setTheme,
      toggleTheme,
      setLocation,
      setDraft,
      setTranscript,
      setResult,
      dismissAlert,
    }),
    [
      state,
      setTheme,
      toggleTheme,
      setLocation,
      setDraft,
      setTranscript,
      setResult,
      dismissAlert,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function AppProvider({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <ThemeI18nShell>{children}</ThemeI18nShell>
    </I18nProvider>
  );
}

export function useApp(): AppCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
