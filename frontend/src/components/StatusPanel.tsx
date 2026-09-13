import type { IstatistikYaniti, SaglikYaniti } from "../api";
import { ChartIcon, DatabaseIcon, SparkIcon } from "./Icons";

interface Props {
  saglik: SaglikYaniti | null;
  istatistik: IstatistikYaniti | null;
  baglantiHatasi: boolean;
}

function Satir({ etiket, deger, renk = "text-slate-200" }: {
  etiket: string;
  deger: string;
  renk?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-1">
      <span className="text-[11.5px] text-slate-500">{etiket}</span>
      <span className={`font-mono text-[12px] font-medium tabular-nums ${renk}`}>{deger}</span>
    </div>
  );
}

function Bolum({ baslik, ikon, children }: {
  baslik: string;
  ikon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised/50 p-3.5">
      <div className="mb-2 flex items-center gap-2">
        {ikon}
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {baslik}
        </h3>
      </div>
      {children}
    </div>
  );
}

export default function StatusPanel({ saglik, istatistik, baglantiHatasi }: Props) {
  if (baglantiHatasi) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-3.5">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-red-400">
          Backend kapali
        </h3>
        <p className="mt-2 text-[12px] leading-relaxed text-red-200/80">
          FastAPI sunucusuna ulasilamiyor. Terminalde{" "}
          <code className="rounded bg-slate-800 px-1 py-0.5 text-[11px]">backend</code> klasorunde
          sunu calistirin:
        </p>
        <code className="mt-2 block rounded-lg bg-slate-900/80 px-2.5 py-2 font-mono text-[11px] text-emerald-300">
          uvicorn main:app --reload
        </code>
      </div>
    );
  }

  const model = saglik?.model;

  return (
    <div className="space-y-3">
      <Bolum baslik="Model" ikon={<ChartIcon className="h-4 w-4 text-emerald-500" />}>
        {model ? (
          <>
            <Satir
              etiket="Durum"
              deger={model.egitildi ? "Egitildi" : "Egitilmedi"}
              renk={model.egitildi ? "text-emerald-400" : "text-red-400"}
            />
            <Satir etiket="Egitim ornegi" deger={String(model.ornek_sayisi)} />
            <Satir etiket="Hastalik sinifi" deger={String(model.sinif_sayisi)} />
            <Satir etiket="TF-IDF ozelligi" deger={String(model.ozellik_sayisi)} />
            <Satir
              etiket="Capraz dogrulama"
              deger={model.dogruluk !== null ? `%${(model.dogruluk * 100).toFixed(1)}` : "-"}
              renk="text-amber-300"
            />
          </>
        ) : (
          <p className="text-[12px] text-slate-500">Yukleniyor...</p>
        )}
      </Bolum>

      <Bolum baslik="Yapay zeka" ikon={<SparkIcon className="h-4 w-4 text-violet-400" />}>
        <Satir
          etiket="Gemini"
          deger={saglik?.gemini_aktif ? "Aktif" : "Devre disi"}
          renk={saglik?.gemini_aktif ? "text-emerald-400" : "text-slate-500"}
        />
        <Satir etiket="Model" deger={saglik?.gemini_model ?? "-"} />
        {saglik && !saglik.gemini_aktif && (
          <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
            backend/.env dosyasina GEMINI_API_KEY ekleyip sunucuyu yeniden baslatin.
            Anahtarsiz da calisir; yorumlar veritabanindan uretilir.
          </p>
        )}
      </Bolum>

      <Bolum baslik="Veritabani" ikon={<DatabaseIcon className="h-4 w-4 text-sky-400" />}>
        {istatistik ? (
          <>
            <Satir etiket="Toplam kayit" deger={String(istatistik.toplam_kayit)} />
            <Satir etiket="Baslangic verisi" deger={String(istatistik.seed_kayit)} />
            <Satir
              etiket="Otomatik ogrenilen"
              deger={String(istatistik.auto_kayit)}
              renk="text-emerald-400"
            />
            <Satir etiket="Onay bekleyen" deger={String(istatistik.bekleyen_kayit)} />
          </>
        ) : (
          <p className="text-[12px] text-slate-500">Yukleniyor...</p>
        )}
      </Bolum>

      {istatistik && istatistik.hastaliklar.length > 0 && (
        <Bolum baslik="Veri dagilimi" ikon={<DatabaseIcon className="h-4 w-4 text-slate-500" />}>
          <div className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
            {istatistik.hastaliklar.map((h) => {
              const enBuyuk = istatistik.hastaliklar[0]?.kayit || 1;
              return (
                <div key={h.hastalik}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[11px] text-slate-400" title={h.hastalik}>
                      {h.hastalik}
                    </span>
                    <span className="font-mono text-[11px] text-slate-500">{h.kayit}</span>
                  </div>
                  <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-slate-600"
                      style={{ width: `${(h.kayit / enBuyuk) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Bolum>
      )}
    </div>
  );
}
