import { useState } from "react";
import type { Tahmin } from "../api";
import ProbabilityBar from "./ProbabilityBar";
import { ChevronIcon } from "./Icons";
import { terimEtiketi } from "../lib/turkce";

interface Props {
  tahmin: Tahmin;
  sira: number;
}

/**
 * Tek bir hastalık tahmini.
 *
 * Başlık satırı her zaman görünür; ayrıntılar (destekleyen ifadeler ve
 * "ne yapmalı" metni) açılır kapanır. En olası tahmin açık başlar ve
 * yumuşak yeşil bir zeminle öne çıkarılır.
 */
export default function DiseaseCard({ tahmin, sira }: Props) {
  const vurgulu = sira === 0;
  const [acik, setAcik] = useState(vurgulu);

  return (
    <div
      className={`overflow-hidden rounded-xl border transition-colors ${
        vurgulu ? "border-accent-line bg-accent-soft" : "border-line bg-card"
      }`}
    >
      <button
        type="button"
        onClick={() => setAcik((a) => !a)}
        aria-expanded={acik}
        className="flex w-full flex-col gap-3 px-4 py-3.5 text-left"
      >
        <div className="flex items-center gap-3">
          <span
            className={`tnum flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold ${
              vurgulu ? "bg-accent text-white" : "bg-canvas-soft text-ink-muted"
            }`}
          >
            {sira + 1}
          </span>

          <h4 className="flex-1 text-[14.5px] font-semibold leading-snug text-ink">
            {tahmin.hastalik}
          </h4>

          <ChevronIcon
            className={`h-4 w-4 shrink-0 text-ink-muted transition-transform duration-200 ${
              acik ? "rotate-180" : ""
            }`}
          />
        </div>

        <ProbabilityBar yuzde={tahmin.yuzde} gecikmeMs={sira * 110} />
      </button>

      {acik && (
        <div className="animate-fade space-y-3.5 border-t border-line px-4 py-3.5">
          {tahmin.anlam_gerekcesi && (
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
                Anlam kontrolünün gerekçesi
              </p>
              <p className="text-[13px] leading-relaxed text-ink-soft">
                {tahmin.anlam_gerekcesi}
                {tahmin.ml_yuzde != null && (
                  <span className="text-ink-muted">
                    {" "}
                    (kelime tabanlı model tek başına: %{tahmin.ml_yuzde.toLocaleString("tr-TR")})
                  </span>
                )}
              </p>
            </div>
          )}

          {tahmin.aciklayici_kelimeler.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
                Bu tahmini destekleyen ifadeler
              </p>
              <div className="flex flex-wrap gap-1.5">
                {tahmin.aciklayici_kelimeler.map((kelime) => (
                  <span
                    key={kelime}
                    className="rounded-md border border-line bg-card px-2 py-1 text-[11.5px] text-ink-soft"
                  >
                    {terimEtiketi(kelime)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {tahmin.oneri && (
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
                Ne yapmalı
              </p>
              <p className="text-[13.5px] leading-relaxed text-ink-soft">{tahmin.oneri}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
