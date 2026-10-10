"use client";

import { Mic, Upload } from "lucide-react";
import { useState } from "react";
import { ConfirmForm } from "@/components/ConfirmForm";
import { VerdictCard } from "@/components/VerdictCard";
import { useApp } from "@/context/AppProvider";
import { useI18n } from "@/hooks/useI18n";
import { analyze, parseInput } from "@/lib/api";
import { SAMPLE_TRANSCRIPT } from "@/mock/analyze";
import type { ParsedFarmerRequest } from "@/types/domain";

type VoiceState = "idle" | "recording" | "processing";
type Tab = "voice" | "typed";

export function CheckPrice() {
  const { t } = useI18n();
  const { state, setDraft, setTranscript, setResult } = useApp();
  const [tab, setTab] = useState<Tab>("typed");
  const [voice, setVoice] = useState<VoiceState>("idle");
  const [text, setText] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const draft = state.draft;

  async function runParse(input: string) {
    const outcome = await parseInput(input);
    setTranscript(outcome.request?.raw_transcript ?? input);
    if (outcome.request) setDraft(outcome.request);
    setResult(null);
  }

  function onRecord() {
    if (voice !== "idle") return;
    setVoice("recording");
    window.setTimeout(() => {
      setVoice("processing");
      window.setTimeout(() => {
        setText(SAMPLE_TRANSCRIPT);
        void runParse(SAMPLE_TRANSCRIPT).finally(() => setVoice("idle"));
      }, 1000);
    }, 1000);
  }

  function updateDraft(patch: Partial<ParsedFarmerRequest>) {
    if (!draft) {
      setDraft({
        crop: "Tomato",
        quantity_maunds: 1,
        district: state.location?.district ?? "Lahore",
        crop_stage: "Ready to harvest",
        confidence: 0.8,
        ...patch,
      });
      return;
    }
    setDraft({ ...draft, ...patch });
  }

  async function onConfirm() {
    if (!draft) return;
    const next: Record<string, string> = {};
    if (!draft.crop) next.crop = t.required;
    if (!(draft.quantity_maunds > 0)) next.quantity = t.mustBePositive;
    if (!draft.district) next.district = t.selectDistrict;
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      setResult(await analyze(draft));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      id="check-price"
      className="space-y-4 rounded-2xl border border-emerald-800/15 bg-white p-5 shadow-sm dark:border-emerald-100/10 dark:bg-emerald-950/40"
      aria-labelledby="check-title"
    >
      <h2 id="check-title" className="text-xl font-bold">
        {t.checkPrice}
      </h2>

      <div role="tablist" className="flex gap-2">
        {(["voice", "typed"] as const).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`min-h-tap flex-1 rounded-xl px-3 font-bold ${
              tab === id
                ? "bg-emerald-800 text-white"
                : "bg-emerald-50 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-50"
            }`}
            onClick={() => setTab(id)}
          >
            {id === "voice" ? t.voiceTab : t.typedTab}
          </button>
        ))}
      </div>

      {tab === "voice" ? (
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRecord}
            className="inline-flex min-h-tap min-w-[12rem] flex-1 items-center justify-center gap-2 rounded-2xl bg-emerald-800 text-lg font-bold text-white"
            aria-label={t.record}
          >
            <Mic className="size-6" aria-hidden />
            {voice === "idle"
              ? t.record
              : voice === "recording"
                ? t.recording
                : t.processing}
          </button>
          <label className="inline-flex min-h-tap cursor-pointer items-center gap-2 rounded-xl border border-emerald-800/20 px-4 font-bold">
            <Upload className="size-5" aria-hidden />
            {t.uploadAudio}
            <input
              type="file"
              accept="audio/*"
              className="sr-only"
              onChange={() => {
                setText(SAMPLE_TRANSCRIPT);
                void runParse(SAMPLE_TRANSCRIPT);
              }}
            />
          </label>
        </div>
      ) : (
        <div>
          <label htmlFor="typed-input" className="block font-bold">
            {t.typedTab}
          </label>
          <textarea
            id="typed-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.typedPlaceholder}
            rows={4}
            className="mt-2 w-full rounded-xl border border-emerald-800/20 bg-sand-50 p-3 text-base dark:border-emerald-100/20 dark:bg-emerald-900"
          />
          <button
            type="button"
            className="mt-3 inline-flex min-h-tap items-center rounded-xl bg-emerald-700 px-4 font-bold text-white"
            onClick={() => void runParse(text)}
          >
            {t.checkPrice}
          </button>
        </div>
      )}

      {state.transcript && (
        <div className="rounded-xl bg-sand-50 p-3 dark:bg-emerald-900/60">
          <h3 className="font-bold">{t.whatIHeard}</h3>
          <p className="mt-1 text-base leading-relaxed">{state.transcript}</p>
        </div>
      )}

      {draft && (
        <ConfirmForm
          draft={draft}
          errors={errors}
          busy={busy}
          onChange={updateDraft}
          onConfirm={() => void onConfirm()}
        />
      )}

      {state.result && <VerdictCard result={state.result} />}
    </section>
  );
}
