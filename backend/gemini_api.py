"""Gemini 2.5 Flash entegrasyonu (google-genai SDK).

Gorev dagilimi onemli: TESHISI ML MODELI KOYAR, Gemini koymaz.
Gemini'ye verilen is, Logistic Regression'in urettigi olasilik dagilimini
sahip icin anlasilir, sakin ve sorumlu bir Turkce metne cevirmektir.
Boylece halusinasyon yuzeyi daralir ve sistem Gemini olmadan da calisir.

API anahtari yoksa modul sessizce devre disi kalir; main.py bu durumda
sablon tabanli bir ozet metin uretir (graceful degradation).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("vetai.gemini")

MODEL_ADI = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# .env.example'daki yer tutucu deger gercek anahtar sanilmasin
if _API_KEY in {"buraya_kendi_anahtarini_yapistir", "your_api_key_here"}:
    _API_KEY = ""

SISTEM_TALIMATI = """Sen VetAI adli bir veteriner on-degerlendirme asistanisin.
Turkiye'deki evcil hayvan sahipleriyle Turkce konusuyorsun.

GOREVIN:
Sana verilen makine ogrenmesi tahminlerini ve kullanicinin sikayetini
kullanarak sakin, anlasilir ve sorumlu bir on-degerlendirme metni yazmak.

KURALLAR:
1. ASLA kesin teshis koyma. "olabilir", "dusundurur", "isaret edebilir" gibi
   olasilik bildiren ifadeler kullan.
2. Sana verilen tahmin listesinin disina cikip yeni hastalik adi UYDURMA.
3. Ilac adi, doz veya recete ONERME. Insan ilaclari (parasetamol, ibuprofen)
   hayvanlarda oldurucudur; konu acilirsa bunu uyar.
4. Her yanitin sonunda mutlaka veteriner hekime basvurulmasi gerektigini belirt.
5. Acil durum isareti verilmisse metne EN BASTAN, net bir sekilde "vakit
   kaybetmeden klinige gidin" uyarisi koy.
6. Sahibin evde yapabilecegi guvenli destekleyici bakim varsa kisaca soyle.
7. Tibbi terim kullanirsan parantez icinde gunluk karsiligini ver.

BICIM:
- Toplam 90-140 kelime, 2-3 kisa paragraf.
- Baslik, madde isareti, yildiz veya markdown bicimlendirmesi KULLANMA; duz metin yaz.
- Sicak ama abartisiz bir ton kullan; sahibi paniklertme, kucumseme.
"""


@dataclass
class GeminiYanit:
    metin: str
    model: str
    basarili: bool
    hata: Optional[str] = None


_client = None
_client_denendi = False


def _get_client():
    """Client'i ilk kullanimda olusturur (lazy init)."""
    global _client, _client_denendi
    if _client_denendi:
        return _client
    _client_denendi = True

    if not _API_KEY:
        logger.warning("GEMINI_API_KEY tanimli degil - Gemini katmani devre disi.")
        return None
    try:
        from google import genai

        _client = genai.Client(api_key=_API_KEY)
        logger.info("Gemini istemcisi hazir (model=%s).", MODEL_ADI)
    except Exception as exc:  # pragma: no cover
        logger.error("Gemini istemcisi olusturulamadi: %s", exc)
        _client = None
    return _client


def kullanilabilir_mi() -> bool:
    """Gemini katmani aktif mi? (/api/health ve arayuz rozetleri icin)"""
    return _get_client() is not None


def _tahmin_metni(tahminler: Sequence) -> str:
    if not tahminler:
        return "Model, veritabanindaki hicbir hastalikla anlamli eslesme bulamadi."
    satirlar = []
    for i, t in enumerate(tahminler, start=1):
        satirlar.append(f"{i}. {t.hastalik} - olasilik %{t.olasilik * 100:.0f}")
    return "\n".join(satirlar)


def yorumla(
    kullanici_metni: str,
    tur: str,
    tahminler: Sequence,
    *,
    acil: bool = False,
    acil_gerekce: str = "",
    bulgular: Optional[List[str]] = None,
) -> GeminiYanit:
    """ML ciktisini kullaniciya donuk bir on-degerlendirme metnine cevirir."""
    client = _get_client()
    if client is None:
        return GeminiYanit(
            metin="",
            model=MODEL_ADI,
            basarili=False,
            hata="Gemini API anahtari tanimli degil.",
        )

    tur_etiketi = {"kedi": "Kedi", "kopek": "Kopek"}.get(tur, "Belirtilmemis (kedi/kopek)")
    acil_blok = (
        f"ACIL DURUM ISARETI: EVET. Gerekce: {acil_gerekce}"
        if acil
        else "ACIL DURUM ISARETI: Hayir."
    )

    istem = f"""Hayvan turu: {tur_etiketi}
Sahibin yazdigi sikayet: "{kullanici_metni}"
NLP ile ayiklanan bulgular: {', '.join(bulgular or []) or 'yok'}
{acil_blok}

Makine ogrenmesi modelinin (TF-IDF + Logistic Regression) tahminleri:
{_tahmin_metni(tahminler)}

Yukaridaki tahminlere dayanarak sahibe yonelik on-degerlendirme metnini yaz."""

    try:
        from google.genai import types

        yanit = client.models.generate_content(
            model=MODEL_ADI,
            contents=istem,
            config=types.GenerateContentConfig(
                system_instruction=SISTEM_TALIMATI,
                temperature=0.4,          # tibbi baglamda dusuk yaraticilik
                max_output_tokens=700,
                # Gemini 2.5 Flash'ta dusunme adimini kapatarak gecikmeyi dusuruyoruz;
                # akil yurutmeyi zaten ML modeli yapti, Gemini sadece metne ceviriyor.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                # Arac (tool) kullanmiyoruz; otomatik fonksiyon cagrisini kapatiyoruz.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        metin = (yanit.text or "").strip()
        if not metin:
            return GeminiYanit("", MODEL_ADI, False, "Model bos yanit dondurdu.")
        return GeminiYanit(metin, MODEL_ADI, True)

    except Exception as exc:
        logger.error("Gemini cagrisi basarisiz: %s", exc)
        return GeminiYanit("", MODEL_ADI, False, str(exc))


def kapsam_disi_yanit(kullanici_metni: str) -> GeminiYanit:
    """Konu disi sorular icin kisa, kibar bir yonlendirme uretir.

    Guardrail bu metni Gemini'siz de uretebilir; burasi sadece daha dogal
    bir cumle kurmak icin opsiyonel bir zenginlestirme.
    """
    client = _get_client()
    if client is None:
        return GeminiYanit("", MODEL_ADI, False, "Gemini devre disi.")
    try:
        from google.genai import types

        yanit = client.models.generate_content(
            model=MODEL_ADI,
            contents=(
                f'Kullanici sunu yazdi: "{kullanici_metni}"\n'
                "Bu bir evcil hayvan sagligi sikayeti degil. Tek paragrafta, en fazla "
                "35 kelimeyle, kibarca sadece kedi ve kopek saglik sikayetlerinde "
                "yardimci olabildigini soyle ve ornek bir sikayet yazimi oner. "
                "Markdown kullanma."
            ),
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=200,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return GeminiYanit((yanit.text or "").strip(), MODEL_ADI, True)
    except Exception as exc:
        logger.error("Gemini kapsam disi yanit hatasi: %s", exc)
        return GeminiYanit("", MODEL_ADI, False, str(exc))


if __name__ == "__main__":  # python gemini_api.py
    import sys

    # Windows konsolu varsayilan cp1252 kullanir ve Turkce karakterde coker.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO)
    print("Gemini kullanilabilir:", kullanilabilir_mi())
    if kullanilabilir_mi():
        class _T:
            def __init__(self, h, o):
                self.hastalik, self.olasilik = h, o

        r = yorumla(
            "Kedim iki gundur kusuyor ve mama yemiyor",
            "kedi",
            [_T("Gastroenterit", 0.35), _T("Kronik Bobrek Yetmezligi", 0.08)],
            bulgular=["kusma", "istahsizlik"],
        )
        print("\nBasarili:", r.basarili, "\n")
        print(r.metin or r.hata)
