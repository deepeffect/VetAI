import { useState } from "react";
import type { Tahmin } from "../api";
import ProbabilityBar from "./ProbabilityBar";
import { ChevronIcon } from "./Icons";

interface Props {
  tahmin: Tahmin;
  sira: number;
}

export default function DiseaseCard({ tahmin, sira }: Props) {
  // Ilk (en olasi) tahminin detayi acik baslar, digerleri kapali.
  const [acik, setAcik] = useState(sira === 0);
  const vurgulu = sira === 0;

  return (
    <div
      className={`rounded-xl border transition-colors ${
        vurgulu
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-line bg-surface-raised/60 hover:border-slate-600"
      }`}
    >
      <button
        type="button"
        onClick={() => setAcik((a) => !a)}
        aria-expanded={acik}
        className="flex w-full flex-col gap-2.5 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2.5">
          <span
            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs font-bold ${
              vurgulu ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-700/60 text-slate-400"
            }`}
          >
            {sira + 1}
          </span>
          <h4
            className={`flex-1 text-sm font-semibold leading-tight ${
              vurgulu ? "text-emerald-50" : "text-slate-300"
            }`}
          >
            {tahmin.hastalik}
          </h4>
          <ChevronIcon
            className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${
              acik ? "rotate-180" : ""
            }`}
          />
        </div>

        <ProbabilityBar yuzde={tahmin.yuzde} vurgulu={vurgulu} gecikmeMs={sira * 120} />
      </button>

      {acik && (
        <div className="animate-fade space-y-3 border-t border-line/70 px-4 py-3">
          {tahmin.aciklayici_kelimeler.length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Bu tahmini destekleyen ifadeler
              </p>
              <div className="flex flex-wrap gap-1.5">
                {tahmin.aciklayici_kelimeler.map((kelime) => (
                  <span
                    key={kelime}
                    className="rounded-md bg-slate-800/80 px-2 py-0.5 font-mono text-[11px] text-slate-300"
                  >
                    {kelime}
                  </span>
                ))}
              </div>
            </div>
          )}

          {tahmin.oneri && (
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Ne yapmali
              </p>
              <p className="text-[13px] leading-relaxed text-slate-300">{tahmin.oneri}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
