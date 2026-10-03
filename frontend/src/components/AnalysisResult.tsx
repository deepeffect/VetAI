import type { AnalizYaniti } from "../api";
import DiseaseCard from "./DiseaseCard";
import { AlertIcon, CatIcon, DogIcon, InfoIcon, PawIcon, SparkIcon } from "./Icons";
import Markdown from "../lib/markdown";
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

/**
 * Anlam kontrolü kutusu: Gemini şikâyeti anlamca okuduysa ne anladığını,
 * yanıltıcı bir kelime varsa açıklamasını ve kelime tabanlı modelin tek
 * başına başka bir tabloyu öne çıkardığını gösterir.
 */
function AnlamKontrolu({ sonuc }: { sonuc: AnalizYaniti }) {
  if (!sonuc.anlam_aktif || (!sonuc.anlam_ozeti && !sonuc.anlam_notu)) return null;
  const ilk = sonuc.tahminler[0]?.hastalik;
  const siralamaDegisti = Boolean(sonuc.ml_ilk_tahmin && ilk && sonuc.ml_ilk_tahmin !== ilk);
  return (
    <div className="rounded-xl border border-accent-line bg-accent-soft px-4 py-3">
      <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-accent-ink">
        <SparkIcon className="h-3.5 w-3.5" />
        Anlam kontrolü
      </p>
      {sonuc.anlam_ozeti && (
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{sonuc.anlam_ozeti}</p>
      )}
      {sonuc.anlam_notu && (
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-soft">{sonuc.anlam_notu}</p>
      )}
      {siralamaDegisti && (
        <p className="mt-1.5 text-[12px] leading-relaxed text-ink-muted">
          Kelime tabanlı model tek başına “{sonuc.ml_ilk_tahmin}” tablosunu öne çıkarıyordu;
          sıralama ifadenin anlamına göre düzeltildi.
        </p>
      )}
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

      {/* --- 24 saat içinde görülmeli (turuncu) --------------------------- */}
      {!sonuc.acil && sonuc.aciliyet === "turuncu" && (
        <div className="flex gap-3 rounded-xl border border-warn-line bg-warn-soft p-4">
          <InfoIcon className="mt-0.5 h-5 w-5 shrink-0 text-warn-ink" />
          <div>
            <p className="text-[13.5px] font-semibold text-warn-ink">Bugün içinde veterinere görünün</p>
            <p className="mt-1 text-[13.5px] leading-relaxed text-warn-ink/90">
              {sonuc.aciliyet_bayraklari.length > 0
                ? `${sonuc.aciliyet_bayraklari.join(", ")} bulguları 24 saat içinde muayene gerektirir.`
                : "Bu tablo genellikle 24 saat içinde muayene gerektirir."}
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

      {/* --- Anlam kontrolü (Gemini'nin şikâyeti nasıl okuduğu) ------------- */}
      <AnlamKontrolu sonuc={sonuc} />

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
          <Markdown metin={sonuc.ai_yorum} />
        </div>
      )}

      {/* --- Olasılık dağılımı ---------------------------------------------- */}
      {sonuc.tahminler.length > 0 && (
        <div className="border-t border-line-soft pt-4">
          <BolumBasligi
            ek={
              <span className="text-[11px] text-ink-muted">
                {sonuc.anlam_aktif
                  ? "TF-IDF + Logistic Regression + anlam kontrolü"
                  : "TF-IDF + Logistic Regression"}
              </span>
            }
          >
            {sonuc.kararsiz ? "Olası tablolar (model kararsız)" : "Model olasılıkları"}
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
