/**
 * VetAI backend istemcisi.
 *
 * Buradaki tipler backend/main.py içindeki Pydantic şemalarıyla birebir eşleşir.
 * Şema değişirse iki tarafı birlikte güncelleyin.
 */
import axios from "axios";

/** Boş bırakılırsa Vite proxy'si (/api -> 127.0.0.1:8000) devreye girer. */
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const http = axios.create({
  baseURL: BASE_URL,
  timeout: 45_000, // Gemini çağrısı yavaş olabilir
  headers: { "Content-Type": "application/json" },
});

/* ------------------------------------------------------------------ tipler */

export type Durum = "ok" | "acil" | "belirsiz" | "kapsam_disi" | "reddedildi";
export type Tur = "kedi" | "kopek" | "genel";

export interface Tahmin {
  hastalik: string;
  olasilik: number;
  yuzde: number;
  oneri: string;
  aciklayici_kelimeler: string[];
}

export interface ModelBilgisi {
  egitildi: boolean;
  ornek_sayisi: number;
  sinif_sayisi: number;
  ozellik_sayisi: number;
  dogruluk: number | null;
  egitim_zamani: string | null;
}

export interface AnalizYaniti {
  durum: Durum;
  mesaj: string;
  tur: string;
  bulgular: string[];
  tahminler: Tahmin[];
  ai_yorum: string;
  ai_aktif: boolean;
  ai_model: string;
  acil: boolean;
  acil_gerekce: string;
  /** kirmizi (hemen) | turuncu (24 saat içinde) | yesil (planlı) | "" (belirlenemedi) */
  aciliyet: "kirmizi" | "turuncu" | "yesil" | "";
  /** Aciliyeti yükselten belirtilerin Türkçe adları (şeffaflık için gösterilir). */
  aciliyet_bayraklari: string[];
  /** Model ilk iki tahmin arasında kararsızsa true; arayüz "şu tablolardan biri" dili kullanır. */
  kararsiz: boolean;
  uyarilar: string[];
  ogrenildi: boolean;
  model_bilgi: ModelBilgisi | null;
}

export interface SaglikYaniti {
  durum: string;
  veritabani: boolean;
  model: ModelBilgisi;
  gemini_aktif: boolean;
  gemini_model: string;
}

export interface HastalikDagilimi {
  hastalik: string;
  kayit: number;
}

export interface IstatistikYaniti {
  toplam_kayit: number;
  seed_kayit: number;
  auto_kayit: number;
  bekleyen_kayit: number;
  hastaliklar: HastalikDagilimi[];
  model: ModelBilgisi;
}

/* ------------------------------------------------------------ sohbet tipleri */

/** Frontend ile backend (chat_service.ChatMessage) arasında ortak mesaj biçimi. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt?: string;
}

export interface SohbetYaniti {
  message: ChatMessage;
  /** Son mesaj bir şikâyetse o tura ait ML analizi; değilse null. */
  analiz: AnalizYaniti | null;
  ai_aktif: boolean;
  ai_model: string;
}

/* --------------------------------------------------------------- istekler */

/** Ana analiz çağrısı: şikâyet metnini backend'e gönderir. */
export async function analizEt(metin: string, tur?: Tur): Promise<AnalizYaniti> {
  const { data } = await http.post<AnalizYaniti>("/api/analyze", {
    metin,
    tur: tur && tur !== "genel" ? tur : null,
  });
  return data;
}

/**
 * Sohbet çağrısı: konuşma geçmişini (son eleman kullanıcı mesajı) gönderir.
 * Backend geçmişi kendi sınırına göre kırpar; burada yalnızca taşınır.
 */
export async function sohbetEt(
  messages: ChatMessage[],
  tur?: Tur,
  signal?: AbortSignal
): Promise<SohbetYaniti> {
  const { data } = await http.post<SohbetYaniti>(
    "/api/chat",
    { messages, tur: tur && tur !== "genel" ? tur : null },
    { signal }
  );
  return data;
}

/** Sunucu, veritabanı, model ve Gemini durumunu döndürür. */
export async function saglikKontrol(): Promise<SaglikYaniti> {
  const { data } = await http.get<SaglikYaniti>("/api/health");
  return data;
}

/** Veri seti istatistikleri (yan panel için). */
export async function istatistikAl(): Promise<IstatistikYaniti> {
  const { data } = await http.get<IstatistikYaniti>("/api/stats");
  return data;
}

const GENEL_HATA = "Yanıt oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.";

/** FastAPI'nin `{"detail": "..."}` gövdesinden okunabilir metni çıkarır. */
function sunucuDetayi(data: unknown): string | null {
  if (data && typeof data === "object" && "detail" in data) {
    const detay = (data as { detail: unknown }).detail;
    if (typeof detay === "string" && detay.trim()) return detay;
  }
  return null;
}

/** Axios hatasını kullanıcıya gösterilebilir Türkçe metne çevirir. */
export function hataMesaji(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === "ERR_CANCELED") {
      return "İstek iptal edildi.";
    }
    if (error.code === "ECONNABORTED") {
      return "Sunucu yanıt vermedi (zaman aşımı). Backend'in çalıştığından emin misiniz?";
    }
    if (!error.response) {
      return "Backend'e ulaşılamadı. Terminalde 'uvicorn main:app --reload' komutunun çalıştığından emin olun.";
    }
    const { status, data } = error.response;
    if (status === 422) {
      return (
        sunucuDetayi(data) ??
        "Gönderilen metin geçersiz. Lütfen 1-2000 karakter arasında bir mesaj yazın."
      );
    }
    // Backend Gemini hatalarını (anahtar yok, model yanlış, kota, zaman aşımı)
    // 429 / 502 / 503 / 504 ile ve açıklayıcı bir detail alanıyla döndürür.
    if ([429, 502, 503, 504].includes(status)) {
      return sunucuDetayi(data) ?? GENEL_HATA;
    }
    return `Sunucu hatası (${status}). Terminaldeki backend kaydına bakın.`;
  }
  return GENEL_HATA;
}
