/**
 * VetAI backend istemcisi.
 *
 * Buradaki tipler backend/main.py icindeki Pydantic semalariyla birebir eslesir.
 * Sema degisirse iki tarafi birlikte guncelleyin.
 */
import axios from "axios";

/** Bos birakilirsa Vite proxy'si (/api -> 127.0.0.1:8000) devreye girer. */
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const http = axios.create({
  baseURL: BASE_URL,
  timeout: 45_000, // Gemini cagrisi yavas olabilir
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

/* --------------------------------------------------------------- istekler */

/** Ana analiz cagrisi: sikayet metnini backend'e gonderir. */
export async function analizEt(metin: string, tur?: Tur): Promise<AnalizYaniti> {
  const { data } = await http.post<AnalizYaniti>("/api/analyze", {
    metin,
    tur: tur && tur !== "genel" ? tur : null,
  });
  return data;
}

/** Sunucu, veritabani, model ve Gemini durumunu dondurur. */
export async function saglikKontrol(): Promise<SaglikYaniti> {
  const { data } = await http.get<SaglikYaniti>("/api/health");
  return data;
}

/** Veri seti istatistikleri (yan panel icin). */
export async function istatistikAl(): Promise<IstatistikYaniti> {
  const { data } = await http.get<IstatistikYaniti>("/api/stats");
  return data;
}

/** Axios hatasini kullaniciya gosterilebilir Turkce metne cevirir. */
export function hataMesaji(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === "ECONNABORTED") {
      return "Sunucu yanit vermedi (zaman asimi). Backend calisiyor mu?";
    }
    if (!error.response) {
      return "Backend'e ulasilamadi. 'uvicorn main:app --reload' komutunun calistigindan emin olun.";
    }
    if (error.response.status === 422) {
      return "Gonderilen metin gecersiz. Lutfen 1-2000 karakter arasinda bir sikayet yazin.";
    }
    return `Sunucu hatasi (${error.response.status}). Terminaldeki backend kaydina bakin.`;
  }
  return "Beklenmeyen bir hata olustu.";
}
