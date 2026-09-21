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
import { MoonIcon, PawIcon, ShieldIcon, SparkIcon, SunIcon } from "./components/Icons";
import { useTema } from "./lib/tema";

type Mesaj =
  | { id: string; rol: "kullanici"; metin: string }
  | { id: string; rol: "asistan"; sonuc: AnalizYaniti }
  | { id: string; rol: "asistan"; hata: string };

const ORNEKLER = [
  "Kedim iki gündür kusuyor ve hiç mama yemiyor, çok halsiz.",
  "Köpeğim kulağını kaşıyor ve sürekli kafasını sallıyor.",
  "Erkek kedim kum kabında zorluyor ama idrar yapamıyor.",
  "Köpeğim mama değiştirdikten sonra sürekli kaşınıyor, derisi kızardı.",
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
  const { tema, temayiDegistir } = useTema();

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

  // Yeni mesaj geldiğinde en alta kaydır
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
      // Canlı öğrenme veritabanını değiştirdiyse yan paneli tazele
      if (sonuc.ogrenildi) void durumuYenile();
    } catch (err) {
      setMesajlar((m) => [...m, { id: yeniId(), rol: "asistan", hata: hataMesaji(err) }]);
      setBaglantiHatasi(true);
    } finally {
      setBekliyor(false);
    }
  }

  const bosEkran = mesajlar.length === 0;

  return (
    <div className="min-h-svh bg-canvas text-ink">
      {/* ==================================================== Üst çubuk */}
      <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent-line bg-accent-soft text-accent-ink">
              <PawIcon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h1 className="text-[17px] font-semibold leading-none">VetAI</h1>
              <p className="mt-1 truncate text-[12px] text-ink-muted">
                Evcil hayvan semptom ön değerlendirme asistanı
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {/* Bağlantı durumu */}
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11.5px] font-medium ${
                baglantiHatasi
                  ? "border-danger-line bg-danger-soft text-danger-ink"
                  : "border-accent-line bg-accent-soft text-accent-ink"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  baglantiHatasi ? "bg-danger" : "animate-soft-pulse bg-sage-500"
                }`}
                aria-hidden="true"
              />
              {baglantiHatasi ? "Bağlantı yok" : "Çevrim içi"}
            </span>

            {/* Gemini katmanı açıksa sessiz bir rozet */}
            {saglik?.gemini_aktif && (
              <span className="hidden items-center gap-1.5 rounded-full border border-line bg-card px-2.5 py-1 text-[11.5px] font-medium text-ink-soft sm:inline-flex">
                <SparkIcon className="h-3 w-3 text-accent-ink" />
                Gemini
              </span>
            )}

            {/* Tema değiştirici */}
            <button
              type="button"
              onClick={temayiDegistir}
              aria-label={tema === "koyu" ? "Açık temaya geç" : "Koyu temaya geç"}
              title={tema === "koyu" ? "Açık tema" : "Koyu tema"}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-card text-ink-soft transition-colors hover:text-ink"
            >
              {tema === "koyu" ? (
                <SunIcon className="h-[18px] w-[18px]" />
              ) : (
                <MoonIcon className="h-[18px] w-[18px]" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ==================================================== Gövde */}
      <div className="mx-auto max-w-[1180px] px-4 pb-6 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
          {/* ------------------------------------------------- Sohbet */}
          <main className="flex min-h-[68svh] flex-col">
            <div
              className={`flex-1 space-y-5 ${
                bosEkran ? "flex flex-col justify-center" : ""
              }`}
            >
              {bosEkran && (
                <div className="animate-fade flex flex-col items-center px-2 py-8 text-center sm:py-14">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-accent-line bg-accent-soft text-accent-ink">
                    <PawIcon className="h-8 w-8" />
                  </div>

                  <h2 className="mt-6 text-[26px] font-semibold leading-tight sm:text-[30px]">
                    Hayvanınızın şikâyetini anlatın
                  </h2>

                  <p className="mt-3 max-w-xl text-[14.5px] leading-7 text-ink-soft">
                    Belirtileri kendi cümlelerinizle yazmanız yeterli. Sistem önce metni
                    Türkçe NLP katmanıyla ayıklar, ardından Logistic Regression modeliyle
                    olasılıkları hesaplar ve sonucu sizin için sade bir dille yorumlar.
                  </p>

                  <div className="mt-8 grid w-full max-w-2xl gap-2.5 text-left sm:grid-cols-2">
                    {ORNEKLER.map((ornek) => (
                      <button
                        key={ornek}
                        onClick={() => void gonder(ornek, "genel")}
                        disabled={bekliyor}
                        className="rounded-xl border border-line bg-card px-4 py-3.5 text-left text-[13.5px] leading-relaxed text-ink-soft shadow-soft transition-colors hover:border-accent-line hover:bg-accent-soft hover:text-ink disabled:opacity-50"
                      >
                        {ornek}
                      </button>
                    ))}
                  </div>

                  <p className="mt-9 flex max-w-lg items-start gap-2 text-left text-[12px] leading-relaxed text-ink-muted">
                    <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      VetAI teşhis koymaz. Ürettiği sonuçlar istatistiksel bir ön
                      değerlendirmedir ve veteriner hekim muayenesinin yerine geçmez.
                    </span>
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
                    <span className="flex gap-1" aria-hidden="true">
                      {[0, 240, 480].map((gecikme) => (
                        <span
                          key={gecikme}
                          className="animate-soft-pulse h-1.5 w-1.5 rounded-full bg-sage-500"
                          style={{ animationDelay: `${gecikme}ms` }}
                        />
                      ))}
                    </span>
                    <span className="text-[13px] text-ink-muted">
                      Metin ayıklanıyor, model çalışıyor ve yorum hazırlanıyor…
                    </span>
                  </div>
                </ChatBubble>
              )}

              <div ref={sonRef} />
            </div>

            {/* ---------------------------------------------- Giriş alanı */}
            <div className="sticky bottom-0 -mx-1 px-1">
              {/* Altından kayan içerik sert bir kenarla kesilmesin diye kısa bir geçiş */}
              <div
                className="pointer-events-none h-6 bg-gradient-to-t from-canvas to-transparent"
                aria-hidden="true"
              />
              <div className="bg-canvas pb-4">
                <Composer onGonder={(m, t) => void gonder(m, t)} bekliyor={bekliyor} />
                {!bosEkran && (
                  <p className="mt-2.5 px-1 text-center text-[11px] text-ink-muted">
                    VetAI teşhis koymaz; sonuçlar veteriner hekim muayenesinin yerine geçmez.
                  </p>
                )}
              </div>
            </div>
          </main>

          {/* ------------------------------------------------- Yan panel */}
          <aside className="hidden lg:block">
            <div className="sticky top-[88px] max-h-[calc(100svh-6.5rem)] space-y-3 overflow-y-auto pb-2">
              <StatusPanel
                saglik={saglik}
                istatistik={istatistik}
                baglantiHatasi={baglantiHatasi}
              />
              <p className="px-1 text-[11.5px] leading-relaxed text-ink-muted">
                Sistem her analizde yeni ifadeyi SQLite veritabanına yazar ve modeli arka
                planda yeniden eğitir.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
