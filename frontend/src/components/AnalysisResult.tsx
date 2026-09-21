import type { AnalizYaniti } from "../api";
import DiseaseCard from "./DiseaseCard";
import { AlertIcon, CatIcon, DogIcon, InfoIcon, PawIcon, SparkIcon } from "./Icons";
import { bulguyuCoz, turEtiketi } from "../lib/turkce";

interface Props {
  sonuc: AnalizYaniti;
}

/** Analizin hangi tür için yapıldığını gösteren küçük rozet. */
function TurRozeti({ tur }: { tur: string }) {
  const Ikon = tur === "kedi" ? CatIcon : tur === "kopek" ? DogIcon : PawIcon;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-canvas-soft px-2.5 py-1 text-[11.5px] font-medium text-ink-soft">
      <Ikon className="h-3.5 w-3.5" />
      {turEtiketi(tur)}
    </span>
  );
}

/** Bölüm başlığı: küçük, büyük harfli, sessiz. İçeriğin önüne geçmez. */
function BolumBasligi({
  children,
  ek,
}: {
  children: React.ReactNode;
  ek?: React.ReactNode;
}) {
  return (
    <div className="mb-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
        {children}
      </span>
      {ek}
    </div>
  );
}

export default function AnalysisResult({ sonuc }: Props) {
  return (
    <div className="space-y-5">
      {/* --- Acil durum uyarısı ------------------------------------------- */}
      {sonuc.acil && (
        <div className="flex gap-3 rounded-xl border border-danger-line bg-danger-soft p-4">
          <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <div>
            <p className="text-[13.5px] font-semibold text-danger-ink">
              Acil durum şüphesi
            </p>
            <p className="mt-1 text-[13.5px] leading-relaxed text-danger-ink/90">
              {sonuc.acil_gerekce}. Bu analiz veteriner muayenesinin yerine geçmez;
              lütfen vakit kaybetmeden en yakın kliniğe başvurun.
            </p>
          </div>
        </div>
      )}

      {/* --- Tespit edilen bulgular ---------------------------------------- */}
      {sonuc.bulgular.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <TurRozeti tur={sonuc.tur} />
          <span className="mx-1 h-4 w-px bg-line" aria-hidden="true" />
          {sonuc.bulgular.map((ham) => {
            const { etiket, olumsuz } = bulguyuCoz(ham);
            return (
              <span
                key={ham}
                className={`rounded-full border px-2.5 py-1 text-[11.5px] font-medium ${
                  olumsuz
                    ? "border-line bg-canvas-soft text-ink-muted"
                    : "border-accent-line bg-accent-soft text-accent-ink"
                }`}
              >
                {etiket}
              </span>
            );
          })}
        </div>
      )}

      {/* --- Değerlendirme metni (yanıtın ana gövdesi) ---------------------- */}
      {sonuc.ai_yorum && (
        <div>
          <BolumBasligi
            ek={
              sonuc.ai_aktif ? (
                <span className="text-[11px] text-ink-muted">{sonuc.ai_model}</span>
              ) : null
            }
          >
            <span className="inline-flex items-center gap-1.5">
              <SparkIcon className="h-3.5 w-3.5 text-accent-ink" />
              {sonuc.ai_aktif ? "Yapay zekâ yorumu" : "Ön değerlendirme"}
            </span>
          </BolumBasligi>
          <p className="whitespace-pre-line text-[14.5px] leading-7 text-ink">
            {sonuc.ai_yorum}
          </p>
        </div>
      )}

      {/* --- Olasılık dağılımı ---------------------------------------------- */}
      {sonuc.tahminler.length > 0 && (
        <div className="border-t border-line-soft pt-4">
          <BolumBasligi
            ek={
              <span className="text-[11px] text-ink-muted">
                TF-IDF + Logistic Regression
              </span>
            }
          >
            Model olasılıkları
          </BolumBasligi>
          <div className="space-y-2">
            {sonuc.tahminler.map((t, i) => (
              <DiseaseCard key={t.hastalik} tahmin={t} sira={i} />
            ))}
          </div>
        </div>
      )}

      {/* --- Uyarılar -------------------------------------------------------- */}
      {sonuc.uyarilar.length > 0 && (
        <div className="space-y-2">
          {sonuc.uyarilar.map((u, i) => (
            <div
              key={i}
              className="flex gap-2.5 rounded-lg border border-warn-line bg-warn-soft px-3 py-2.5"
            >
              <InfoIcon className="mt-0.5 h-4 w-4 shrink-0 text-warn-ink" />
              <p className="text-[12.5px] leading-relaxed text-warn-ink">{u}</p>
            </div>
          ))}
        </div>
      )}

      {/* --- Canlı öğrenme bildirimi ----------------------------------------- */}
      {sonuc.ogrenildi && (
        <p className="flex items-center gap-2 text-[11.5px] text-ink-muted">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-sage-500"
            aria-hidden="true"
          />
          Bu ifade eğitim veritabanına eklendi, model güncellendi.
        </p>
      )}
    </div>
  );
}
