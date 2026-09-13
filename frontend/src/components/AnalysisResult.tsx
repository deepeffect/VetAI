import type { AnalizYaniti } from "../api";
import DiseaseCard from "./DiseaseCard";
import { AlertIcon, CatIcon, ChartIcon, DogIcon, InfoIcon, PawIcon, SparkIcon } from "./Icons";

interface Props {
  sonuc: AnalizYaniti;
}

function TurRozeti({ tur }: { tur: string }) {
  const Ikon = tur === "kedi" ? CatIcon : tur === "kopek" ? DogIcon : PawIcon;
  const etiket = tur === "kedi" ? "Kedi" : tur === "kopek" ? "Kopek" : "Tur belirsiz";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-slate-800/60 px-2.5 py-1 text-[11px] font-medium text-slate-300">
      <Ikon className="h-3.5 w-3.5" />
      {etiket}
    </span>
  );
}

export default function AnalysisResult({ sonuc }: Props) {
  return (
    <div className="space-y-4">
      {/* --- Acil durum banneri ------------------------------------------ */}
      {sonuc.acil && (
        <div className="animate-pulse-ring flex gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4">
          <AlertIcon className="h-5 w-5 shrink-0 text-red-400" />
          <div>
            <p className="text-sm font-bold text-red-300">ACIL DURUM SUPHESI</p>
            <p className="mt-1 text-[13px] leading-relaxed text-red-200/90">
              {sonuc.acil_gerekce}. Bu analiz veteriner muayenesinin yerine gecmez -
              lutfen vakit kaybetmeden en yakin klinige basvurun.
            </p>
          </div>
        </div>
      )}

      {/* --- Tespit edilen bulgular --------------------------------------- */}
      {sonuc.bulgular.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <TurRozeti tur={sonuc.tur} />
          <span className="mx-1 text-slate-600">|</span>
          {sonuc.bulgular.map((b) => (
            <span
              key={b}
              className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300"
            >
              {b}
            </span>
          ))}
        </div>
      )}

      {/* --- Gemini yorumu ------------------------------------------------ */}
      {sonuc.ai_yorum && (
        <div className="rounded-xl border border-line bg-surface-raised/60 p-4">
          <div className="mb-2 flex items-center gap-2">
            <SparkIcon
              className={`h-4 w-4 ${sonuc.ai_aktif ? "text-violet-400" : "text-slate-500"}`}
            />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              {sonuc.ai_aktif ? `Yapay zeka yorumu - ${sonuc.ai_model}` : "On degerlendirme"}
            </span>
          </div>
          <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-slate-200">
            {sonuc.ai_yorum}
          </p>
        </div>
      )}

      {/* --- Olasilik dagilimi -------------------------------------------- */}
      {sonuc.tahminler.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2">
            <ChartIcon className="h-4 w-4 text-slate-500" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Model olasiliklari
            </span>
            <span className="text-[11px] text-slate-600">
              TF-IDF + Logistic Regression
            </span>
          </div>
          <div className="space-y-2">
            {sonuc.tahminler.map((t, i) => (
              <DiseaseCard key={t.hastalik} tahmin={t} sira={i} />
            ))}
          </div>
        </div>
      )}

      {/* --- Uyarilar ------------------------------------------------------ */}
      {sonuc.uyarilar.length > 0 && (
        <div className="space-y-2">
          {sonuc.uyarilar.map((u, i) => (
            <div
              key={i}
              className="flex gap-2.5 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2.5"
            >
              <InfoIcon className="h-4 w-4 shrink-0 text-amber-400" />
              <p className="text-[12.5px] leading-relaxed text-amber-200/90">{u}</p>
            </div>
          ))}
        </div>
      )}

      {/* --- Canli ogrenme bildirimi --------------------------------------- */}
      {sonuc.ogrenildi && (
        <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Bu ifade egitim veritabanina eklendi, model guncellendi.
        </p>
      )}
    </div>
  );
}
