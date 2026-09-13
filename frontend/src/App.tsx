import { useCallback, useEffect, useRef, useState } from "react";
import {
  analizEt,
  hataMesaji,
  istatistikAl,
  saglikKontrol,
  type AnalizYaniti,
  type IstatistikYaniti,
  type SaglikYaniti,
  type Tur,
} from "./api";
import AnalysisResult from "./components/AnalysisResult";
import ChatBubble from "./components/ChatBubble";
import Composer from "./components/Composer";
import StatusPanel from "./components/StatusPanel";
import { PawIcon, SparkIcon } from "./components/Icons";

type Mesaj =
  | { id: string; rol: "kullanici"; metin: string }
  | { id: string; rol: "asistan"; sonuc: AnalizYaniti }
  | { id: string; rol: "asistan"; hata: string };

const ORNEKLER = [
  "Kedim iki gundur kusuyor ve hic mama yemiyor, cok halsiz",
  "Kopegim kulagini kasiyor ve surekli kafasini salliyor",
  "Erkek kedim kum kabinda zorluyor ama idrar yapamiyor",
  "Kopegim mama degistirdikten sonra surekli kasiniyor, derisi kizardi",
];

let sayac = 0;
const yeniId = () => `m${++sayac}`;

export default function App() {
  const [mesajlar, setMesajlar] = useState<Mesaj[]>([]);
  const [bekliyor, setBekliyor] = useState(false);
  const [saglik, setSaglik] = useState<SaglikYaniti | null>(null);
  const [istatistik, setIstatistik] = useState<IstatistikYaniti | null>(null);
  const [baglantiHatasi, setBaglantiHatasi] = useState(false);
  const sonRef = useRef<HTMLDivElement>(null);

  /** Backend durumunu ve veri istatistiklerini tazeler. */
  const durumuYenile = useCallback(async () => {
    try {
      const [s, i] = await Promise.all([saglikKontrol(), istatistikAl()]);
      setSaglik(s);
      setIstatistik(i);
      setBaglantiHatasi(false);
    } catch {
      setBaglantiHatasi(true);
    }
  }, []);

  useEffect(() => {
    void durumuYenile();
  }, [durumuYenile]);

  // Yeni mesaj geldiginde en alta kaydir
  useEffect(() => {
    sonRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mesajlar, bekliyor]);

  async function gonder(metin: string, tur: Tur) {
    setMesajlar((m) => [...m, { id: yeniId(), rol: "kullanici", metin }]);
    setBekliyor(true);
    try {
      const sonuc = await analizEt(metin, tur);
      setMesajlar((m) => [...m, { id: yeniId(), rol: "asistan", sonuc }]);
      setBaglantiHatasi(false);
      // Canli ogrenme veritabanini degistirdiyse yan paneli tazele
      if (sonuc.ogrenildi) void durumuYenile();
    } catch (err) {
      setMesajlar((m) => [...m, { id: yeniId(), rol: "asistan", hata: hataMesaji(err) }]);
      setBaglantiHatasi(true);
    } finally {
      setBekliyor(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Arka plan parlamasi */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(60rem_40rem_at_50%_-10%,rgba(16,185,129,0.10),transparent)]"
      />

      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-5 sm:px-6">
        {/* ------------------------------------------------------- Baslik */}
        <header className="mb-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-900/40">
              <PawIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold leading-none tracking-tight text-slate-50">
                VetAI
              </h1>
              <p className="mt-1 text-[12px] text-slate-500">
                Evcil hayvan semptom on-degerlendirme asistani
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                baglantiHatasi
                  ? "border-red-500/30 bg-red-500/10 text-red-400"
                  : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  baglantiHatasi ? "bg-red-500" : "animate-pulse bg-emerald-500"
                }`}
              />
              {baglantiHatasi ? "Baglanti yok" : "Cevrimici"}
            </span>
            {saglik?.gemini_aktif && (
              <span className="hidden items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-300 sm:inline-flex">
                <SparkIcon className="h-3 w-3" />
                Gemini
              </span>
            )}
          </div>
        </header>

        <div className="grid flex-1 gap-5 lg:grid-cols-[1fr_280px]">
          {/* --------------------------------------------------- Sohbet */}
          <main className="flex min-h-[60vh] flex-col">
            <div className="flex-1 space-y-4 overflow-y-auto pb-4">
              {mesajlar.length === 0 && (
                <div className="animate-fade flex h-full flex-col items-center justify-center py-12 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-line bg-surface-raised/60">
                    <PawIcon className="h-8 w-8 text-emerald-500/70" />
                  </div>
                  <h2 className="text-lg font-semibold text-slate-200">
                    Hayvaninizin sikayetini anlatin
                  </h2>
                  <p className="mt-1.5 max-w-md text-[13px] leading-relaxed text-slate-500">
                    Belirtileri kendi cumlelerinizle yazin. Sistem once metni Turkce NLP
                    ile ayikliyor, ardindan Logistic Regression modeliyle olasilik
                    hesapliyor ve sonucu sizin icin yorumluyor.
                  </p>

                  <div className="mt-6 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                    {ORNEKLER.map((ornek) => (
                      <button
                        key={ornek}
                        onClick={() => void gonder(ornek, "genel")}
                        disabled={bekliyor}
                        className="rounded-xl border border-line bg-surface-raised/50 px-3.5 py-3 text-left text-[12.5px] leading-relaxed text-slate-400 transition-colors hover:border-emerald-500/40 hover:bg-emerald-500/5 hover:text-slate-200 disabled:opacity-50"
                      >
                        {ornek}
                      </button>
                    ))}
                  </div>

                  <p className="mt-6 max-w-md text-[11px] leading-relaxed text-slate-600">
                    VetAI teshis koymaz. Urettigi sonuclar istatistiksel bir on
                    degerlendirmedir ve veteriner hekim muayenesinin yerine gecmez.
                  </p>
                </div>
              )}

              {mesajlar.map((m) =>
                m.rol === "kullanici" ? (
                  <ChatBubble key={m.id} rol="kullanici">
                    {m.metin}
                  </ChatBubble>
                ) : "hata" in m ? (
                  <ChatBubble key={m.id} rol="asistan" hata>
                    <p className="text-[13.5px] leading-relaxed">{m.hata}</p>
                  </ChatBubble>
                ) : (
                  <ChatBubble key={m.id} rol="asistan">
                    <AnalysisResult sonuc={m.sonuc} />
                  </ChatBubble>
                )
              )}

              {bekliyor && (
                <ChatBubble rol="asistan">
                  <div className="flex items-center gap-2.5 py-0.5">
                    <span className="flex gap-1">
                      {[0, 150, 300].map((gecikme) => (
                        <span
                          key={gecikme}
                          className="h-1.5 w-1.5 animate-bounce rounded-full bg-emerald-500"
                          style={{ animationDelay: `${gecikme}ms` }}
                        />
                      ))}
                    </span>
                    <span className="text-[12.5px] text-slate-500">
                      NLP temizligi, ML tahmini ve yapay zeka yorumu yapiliyor...
                    </span>
                  </div>
                </ChatBubble>
              )}

              <div ref={sonRef} />
            </div>

            {/* ------------------------------------------------ Giris alani */}
            <div className="sticky bottom-0 bg-gradient-to-t from-surface via-surface to-transparent pt-3">
              <Composer onGonder={(m, t) => void gonder(m, t)} bekliyor={bekliyor} />
            </div>
          </main>

          {/* --------------------------------------------------- Yan panel */}
          <aside className="hidden lg:block">
            <div className="sticky top-5">
              <StatusPanel
                saglik={saglik}
                istatistik={istatistik}
                baglantiHatasi={baglantiHatasi}
              />
              <p className="mt-3 px-1 text-[10.5px] leading-relaxed text-slate-600">
                Sistem her analizde yeni ifadeyi SQLite veritabanina yazar ve modeli
                arka planda yeniden egitir.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
