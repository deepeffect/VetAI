import type { IstatistikYaniti, SaglikYaniti } from "../api";
import { AlertIcon, ChartIcon, DatabaseIcon, SparkIcon } from "./Icons";

interface Props {
  saglik: SaglikYaniti | null;
  istatistik: IstatistikYaniti | null;
  baglantiHatasi: boolean;
}

/** Panel içindeki tek bir "etiket — değer" satırı. */
function Satir({
  etiket,
  deger,
  renk = "text-ink",
}: {
  etiket: string;
  deger: string;
  renk?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line-soft py-2 last:border-0 last:pb-0">
      <span className="text-[12.5px] text-ink-muted">{etiket}</span>
      <span className={`tnum text-[13px] font-semibold ${renk}`}>{deger}</span>
    </div>
  );
}

/** Yan paneldeki kart kabuğu: başlık + içerik. */
function Kart({
  baslik,
  ikon,
  children,
}: {
  baslik: string;
  ikon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-soft">
      <header className="mb-2 flex items-center gap-2 text-ink-muted">
        {ikon}
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em]">{baslik}</h3>
      </header>
      {children}
    </section>
  );
}

function Yukleniyor() {
  return <p className="py-2 text-[12.5px] text-ink-muted">Yükleniyor…</p>;
}

export default function StatusPanel({ saglik, istatistik, baglantiHatasi }: Props) {
  if (baglantiHatasi) {
    return (
      <section className="rounded-2xl border border-danger-line bg-danger-soft p-4">
        <header className="mb-2 flex items-center gap-2 text-danger-ink">
          <AlertIcon className="h-4 w-4" />
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em]">
            Backend kapalı
          </h3>
        </header>
        <p className="text-[12.5px] leading-relaxed text-danger-ink/90">
          FastAPI sunucusuna ulaşılamıyor. Terminalde{" "}
          <code className="rounded bg-card/60 px-1 py-0.5 font-mono text-[11.5px]">
            backend
          </code>{" "}
          klasöründe şu komutu çalıştırın:
        </p>
        <code className="mt-2.5 block rounded-lg border border-danger-line bg-card/60 px-2.5 py-2 font-mono text-[11.5px] text-ink">
          uvicorn main:app --reload
        </code>
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-danger-ink/80">
          Sunucu açılırken modeli eğitir (birkaç saniye sürer). Bağlantı her 3
          saniyede bir yeniden deneniyor; sayfayı yenilemenize gerek yok.
        </p>
      </section>
    );
  }

  const model = saglik?.model;
  const enBuyuk = istatistik?.hastaliklar[0]?.kayit || 1;

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------ Model */}
      <Kart baslik="Model" ikon={<ChartIcon className="h-4 w-4" />}>
        {model ? (
          <>
            <Satir
              etiket="Durum"
              deger={model.egitildi ? "Eğitildi" : "Eğitilmedi"}
              renk={model.egitildi ? "text-accent-ink" : "text-danger-ink"}
            />
            <Satir etiket="Eğitim örneği" deger={String(model.ornek_sayisi)} />
            <Satir etiket="Hastalık sınıfı" deger={String(model.sinif_sayisi)} />
            <Satir etiket="TF-IDF özelliği" deger={String(model.ozellik_sayisi)} />
            <Satir
              etiket="Çapraz doğrulama"
              deger={
                model.dogruluk !== null ? `%${(model.dogruluk * 100).toFixed(1)}` : "—"
              }
            />
          </>
        ) : (
          <Yukleniyor />
        )}
      </Kart>

      {/* ------------------------------------------------------- Yapay zekâ */}
      <Kart baslik="Yapay zekâ" ikon={<SparkIcon className="h-4 w-4" />}>
        <Satir
          etiket="Gemini"
          deger={saglik?.gemini_aktif ? "Aktif" : "Devre dışı"}
          renk={saglik?.gemini_aktif ? "text-accent-ink" : "text-ink-muted"}
        />
        <Satir etiket="Model" deger={saglik?.gemini_model ?? "—"} />
        {saglik && !saglik.gemini_aktif && (
          <p className="mt-2.5 text-[12px] leading-relaxed text-ink-muted">
            backend/.env dosyasına GEMINI_API_KEY ekleyip sunucuyu yeniden başlatın.
            Anahtar olmadan da çalışır; yorumlar veritabanından üretilir.
          </p>
        )}
      </Kart>

      {/* -------------------------------------------------------- Veritabanı */}
      <Kart baslik="Veritabanı" ikon={<DatabaseIcon className="h-4 w-4" />}>
        {istatistik ? (
          <>
            <Satir etiket="Toplam kayıt" deger={String(istatistik.toplam_kayit)} />
            <Satir etiket="Başlangıç verisi" deger={String(istatistik.seed_kayit)} />
            <Satir
              etiket="Otomatik öğrenilen"
              deger={String(istatistik.auto_kayit)}
              renk={istatistik.auto_kayit > 0 ? "text-accent-ink" : "text-ink"}
            />
            <Satir etiket="Onay bekleyen" deger={String(istatistik.bekleyen_kayit)} />
          </>
        ) : (
          <Yukleniyor />
        )}
      </Kart>

      {/* ------------------------------------------------------ Veri dağılımı */}
      {istatistik && istatistik.hastaliklar.length > 0 && (
        <Kart baslik="Veri dağılımı" ikon={<DatabaseIcon className="h-4 w-4" />}>
          <div className="max-h-64 space-y-2.5 overflow-y-auto pr-1 pt-1">
            {istatistik.hastaliklar.map((h) => (
              <div key={h.hastalik}>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-[12px] text-ink-soft" title={h.hastalik}>
                    {h.hastalik}
                  </span>
                  <span className="tnum text-[12px] text-ink-muted">{h.kayit}</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line-soft">
                  <div
                    className="h-full rounded-full bg-sage-300"
                    style={{ width: `${(h.kayit / enBuyuk) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Kart>
      )}
    </div>
  );
}
