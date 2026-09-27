import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  hataMesaji,
  istatistikAl,
  saglikKontrol,
  sohbetEt,
  type AnalizYaniti,
  type ChatMessage,
  type IstatistikYaniti,
  type SaglikYaniti,
  type Tur,
} from "./api";
import AnalysisResult from "./components/AnalysisResult";
import ChatBubble from "./components/ChatBubble";
import Composer from "./components/Composer";
import StatusPanel from "./components/StatusPanel";
import {
  CheckIcon,
  CopyIcon,
  MoonIcon,
  PawIcon,
  RefreshIcon,
  ShieldIcon,
  SparkIcon,
  SunIcon,
  TrashIcon,
} from "./components/Icons";
import Markdown from "./lib/markdown";
import { useTema } from "./lib/tema";

/**
 * Sohbet satırı. Üç biçim vardır:
 *  - kullanıcı mesajı
 *  - asistan yanıtı (Gemini metni + o tura ait ML analizi varsa kartı)
 *  - hata balonu (yeniden denemek için gönderilen bağlam saklanır)
 */
type Mesaj =
  | { id: string; rol: "kullanici"; metin: string; tur: Tur }
  | { id: string; rol: "asistan"; metin: string; analiz: AnalizYaniti | null; model: string }
  | { id: string; rol: "asistan"; hata: string; tekrar: { gecmis: ChatMessage[]; tur: Tur } };

const ORNEKLER = [
  "Kedim iki gündür kusuyor ve hiç mama yemiyor, çok halsiz.",
  "Köpeğim kulağını kaşıyor ve sürekli kafasını sallıyor.",
  "Erkek kedim kum kabında zorluyor ama idrar yapamıyor.",
  "Köpeğim mama değiştirdikten sonra sürekli kaşınıyor, derisi kızardı.",
];

let sayac = 0;
const yeniId = (onek: string) => `${onek}-${Date.now().toString(36)}-${++sayac}`;

/** Backend'e gidecek konuşma geçmişi: yalnızca metin taşıyan mesajlar. */
function gecmiseCevir(mesajlar: Mesaj[]): ChatMessage[] {
  const sonuc: ChatMessage[] = [];
  for (const m of mesajlar) {
    if (m.rol === "kullanici") {
      sonuc.push({ id: m.id, role: "user", content: m.metin });
    } else if ("metin" in m) {
      sonuc.push({ id: m.id, role: "assistant", content: m.metin });
    }
    // hata balonları geçmişe girmez
  }
  return sonuc;
}

/** Asistan kartının altındaki küçük ikon düğmesi. */
function AracDugmesi({
  onClick,
  etiket,
  children,
}: {
  onClick: () => void;
  etiket: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={etiket}
      title={etiket}
      className="inline-flex h-7 items-center gap-1.5 rounded-lg px-2 text-[11.5px] font-medium text-ink-muted transition-colors hover:bg-canvas-soft hover:text-ink"
    >
      {children}
    </button>
  );
}

function KopyalaDugmesi({ metin }: { metin: string }) {
  const [kopyalandi, setKopyalandi] = useState(false);

  async function kopyala() {
    try {
      await navigator.clipboard.writeText(metin);
      setKopyalandi(true);
      window.setTimeout(() => setKopyalandi(false), 1600);
    } catch {
      /* pano erişimi yoksa sessizce geç */
    }
  }

  return (
    <AracDugmesi onClick={() => void kopyala()} etiket="Yanıtı kopyala">
      {kopyalandi ? (
        <CheckIcon className="h-3.5 w-3.5 text-accent-ink" />
      ) : (
        <CopyIcon className="h-3.5 w-3.5" />
      )}
      {kopyalandi ? "Kopyalandı" : "Kopyala"}
    </AracDugmesi>
  );
}

export default function App() {
  const [mesajlar, setMesajlar] = useState<Mesaj[]>([]);
  const [bekliyor, setBekliyor] = useState(false);
  const [saglik, setSaglik] = useState<SaglikYaniti | null>(null);
  const [istatistik, setIstatistik] = useState<IstatistikYaniti | null>(null);
  const [baglantiHatasi, setBaglantiHatasi] = useState(false);
  const sonRef = useRef<HTMLDivElement>(null);
  const { tema, temayiDegistir } = useTema();

  // Stale state'e düşmemek için geçmişin güncel kopyası ve gönderim kilidi
  const mesajlarRef = useRef<Mesaj[]>([]);
  const gonderiliyorRef = useRef(false);
  const iptalRef = useRef<AbortController | null>(null);
  const altaYakinRef = useRef(true);

  useEffect(() => {
    mesajlarRef.current = mesajlar;
  }, [mesajlar]);

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

  // Backend'e ulaşılamıyorsa (ör. sunucu hâlâ açılıyor ya da sonradan
  // başlatıldı) birkaç saniyede bir yeniden dene; bağlanınca durur.
  // Böylece "Backend kapalı" uyarısı sayfa yenilenmeden kendiliğinden kalkar.
  useEffect(() => {
    if (!baglantiHatasi) return;
    const zamanlayici = window.setInterval(() => void durumuYenile(), 3000);
    return () => window.clearInterval(zamanlayici);
  }, [baglantiHatasi, durumuYenile]);

  // Kullanıcı yukarı kaydırıp eski mesajları okuyorsa yeni yanıt geldiğinde
  // onu zorla aşağı çekmiyoruz; yalnızca zaten en alttaysa takip ediyoruz.
  useEffect(() => {
    function kaydirmaTakibi() {
      const kalan =
        document.documentElement.scrollHeight - (window.innerHeight + window.scrollY);
      altaYakinRef.current = kalan < 160;
    }
    kaydirmaTakibi();
    window.addEventListener("scroll", kaydirmaTakibi, { passive: true });
    return () => window.removeEventListener("scroll", kaydirmaTakibi);
  }, []);

  useEffect(() => {
    const son = mesajlar[mesajlar.length - 1];
    const kullaniciGonderdi = son?.rol === "kullanici";
    if (kullaniciGonderdi || altaYakinRef.current) {
      sonRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [mesajlar, bekliyor]);

  /**
   * Verilen geçmişle (son eleman kullanıcı mesajı) backend'den yanıt ister.
   * `kaldirilacakId` verilirse (tekrar dene) o hata balonu önce silinir.
   */
  const yanitIste = useCallback(
    async (gecmis: ChatMessage[], tur: Tur, kaldirilacakId?: string) => {
      if (gonderiliyorRef.current) return;
      gonderiliyorRef.current = true;
      setBekliyor(true);
      if (kaldirilacakId) {
        setMesajlar((m) => m.filter((x) => x.id !== kaldirilacakId));
      }

      const iptal = new AbortController();
      iptalRef.current = iptal;

      try {
        const sonuc = await sohbetEt(gecmis, tur, iptal.signal);
        const metin = (sonuc.message?.content ?? "").trim();
        setMesajlar((m) => [
          ...m,
          {
            id: sonuc.message?.id || yeniId("a"),
            rol: "asistan",
            metin: metin || "Yanıt boş döndü. Lütfen tekrar deneyin.",
            analiz: sonuc.analiz ?? null,
            model: sonuc.ai_model ?? "",
          },
        ]);
        setBaglantiHatasi(false);
        // Canlı öğrenme veritabanını değiştirdiyse yan paneli tazele
        if (sonuc.analiz?.ogrenildi) void durumuYenile();
      } catch (err) {
        if (axios.isCancel(err)) return; // sohbet temizlendi
        setMesajlar((m) => [
          ...m,
          { id: yeniId("e"), rol: "asistan", hata: hataMesaji(err), tekrar: { gecmis, tur } },
        ]);
        // Sunucuya hiç ulaşılamadıysa bağlantı rozetini kırmızıya çevir
        if (axios.isAxiosError(err) && !err.response) setBaglantiHatasi(true);
      } finally {
        if (iptalRef.current === iptal) iptalRef.current = null;
        gonderiliyorRef.current = false;
        setBekliyor(false);
      }
    },
    [durumuYenile]
  );

  function gonder(metin: string, tur: Tur) {
    const temiz = metin.trim();
    if (!temiz || gonderiliyorRef.current) return;
    const kullanici: Mesaj = { id: yeniId("u"), rol: "kullanici", metin: temiz, tur };
    const gecmis = [
      ...gecmiseCevir(mesajlarRef.current),
      { id: kullanici.id, role: "user" as const, content: temiz },
    ];
    setMesajlar((m) => [...m, kullanici]);
    void yanitIste(gecmis, tur);
  }

  function sohbetiTemizle() {
    iptalRef.current?.abort();
    iptalRef.current = null;
    gonderiliyorRef.current = false;
    setBekliyor(false);
    setMesajlar([]);
    window.scrollTo({ top: 0 });
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

            {/* Sohbeti temizle (yalnızca mesaj varken) */}
            {!bosEkran && (
              <button
                type="button"
                onClick={sohbetiTemizle}
                aria-label="Sohbeti temizle"
                title="Sohbeti temizle"
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-card text-ink-soft transition-colors hover:border-danger-line hover:text-danger-ink"
              >
                <TrashIcon className="h-[18px] w-[18px]" />
              </button>
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
          <main className="flex min-h-[68svh] min-w-0 flex-col">
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
                    Sonrasında takip sorularınızı da aynı sohbette sorabilirsiniz.
                  </p>

                  <div className="mt-8 grid w-full max-w-2xl gap-2.5 text-left sm:grid-cols-2">
                    {ORNEKLER.map((ornek) => (
                      <button
                        key={ornek}
                        onClick={() => gonder(ornek, "genel")}
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

              {mesajlar.map((m) => {
                if (m.rol === "kullanici") {
                  return (
                    <ChatBubble key={m.id} rol="kullanici">
                      {m.metin}
                    </ChatBubble>
                  );
                }
                if ("hata" in m) {
                  return (
                    <ChatBubble
                      key={m.id}
                      rol="asistan"
                      hata
                      araclar={
                        <AracDugmesi
                          onClick={() => void yanitIste(m.tekrar.gecmis, m.tekrar.tur, m.id)}
                          etiket="Tekrar dene"
                        >
                          <RefreshIcon className="h-3.5 w-3.5" />
                          Tekrar dene
                        </AracDugmesi>
                      }
                    >
                      <p className="text-[13.5px] leading-relaxed">{m.hata}</p>
                    </ChatBubble>
                  );
                }
                return (
                  <ChatBubble
                    key={m.id}
                    rol="asistan"
                    araclar={
                      <>
                        <KopyalaDugmesi metin={m.metin} />
                        {m.model && (
                          <span className="ml-auto text-[11px] text-ink-muted">{m.model}</span>
                        )}
                      </>
                    }
                  >
                    {m.analiz ? <AnalysisResult sonuc={m.analiz} /> : <Markdown metin={m.metin} />}
                  </ChatBubble>
                );
              })}

              {bekliyor && (
                <ChatBubble rol="asistan">
                  <div className="flex items-center gap-2.5 py-0.5" role="status" aria-live="polite">
                    <span className="flex gap-1" aria-hidden="true">
                      {[0, 240, 480].map((gecikme) => (
                        <span
                          key={gecikme}
                          className="animate-soft-pulse h-1.5 w-1.5 rounded-full bg-sage-500"
                          style={{ animationDelay: `${gecikme}ms` }}
                        />
                      ))}
                    </span>
                    <span className="text-[13px] text-ink-muted">Yanıt hazırlanıyor…</span>
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
                <Composer onGonder={gonder} bekliyor={bekliyor} />
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
