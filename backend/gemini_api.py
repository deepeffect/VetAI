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

SISTEM_TALIMATI = """Sen VetAI adlı bir veteriner ön değerlendirme asistanısın.
Türkiye'deki evcil hayvan sahipleriyle Türkçe konuşuyorsun.

GÖREVİN:
Sana verilen makine öğrenmesi tahminlerini ve kullanıcının şikâyetini
kullanarak sakin, anlaşılır ve sorumlu bir ön değerlendirme metni yazmak.

KURALLAR:
1. ASLA kesin teşhis koyma. "olabilir", "düşündürür", "işaret edebilir" gibi
   olasılık bildiren ifadeler kullan.
2. Sana verilen tahmin listesinin dışına çıkıp yeni hastalık adı UYDURMA.
3. İlaç adı, doz veya reçete ÖNERME. İnsan ilaçları (parasetamol, ibuprofen)
   hayvanlarda öldürücüdür; konu açılırsa bunu uyar.
4. Her yanıtın sonunda mutlaka veteriner hekime başvurulması gerektiğini belirt.
5. Acil durum işareti verilmişse metne EN BAŞTAN, net bir şekilde "vakit
   kaybetmeden kliniğe gidin" uyarısı koy.
6. Sahibin evde yapabileceği güvenli destekleyici bakım varsa kısaca söyle.
7. Tıbbi terim kullanırsan parantez içinde günlük karşılığını ver.

BİÇİM:
- Toplam 90-140 kelime, 2-3 kısa paragraf.
- Başlık, madde işareti, yıldız veya markdown biçimlendirmesi KULLANMA; düz metin yaz.
- Sıcak ama abartısız bir ton kullan; sahibi panikletme, küçümseme.
- Türkçe karakterleri (ç, ğ, ı, İ, ö, ş, ü, â) eksiksiz ve doğru kullan;
  ASCII karşılıklarıyla ("sikayet", "ates" gibi) yazma.
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
        logger.warning("GEMINI_API_KEY tanımlı değil - Gemini katmanı devre dışı.")
        return None
    try:
        from google import genai

        _client = genai.Client(api_key=_API_KEY)
        logger.info("Gemini istemcisi hazir (model=%s).", MODEL_ADI)
    except Exception as exc:  # pragma: no cover
        logger.error("Gemini istemcisi oluşturulamadı: %s", exc)
        _client = None
    return _client


def kullanilabilir_mi() -> bool:
    """Gemini katmani aktif mi? (/api/health ve arayuz rozetleri icin)"""
    return _get_client() is not None


def _tahmin_metni(tahminler: Sequence) -> str:
    if not tahminler:
        return "Model, veritabanındaki hiçbir hastalıkla anlamlı eşleşme bulamadı."
    satirlar = []
    for i, t in enumerate(tahminler, start=1):
        satirlar.append(f"{i}. {t.hastalik} - olasılık %{t.olasilik * 100:.0f}")
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
            hata="Gemini API anahtarı tanımlı değil.",
        )

    tur_etiketi = {"kedi": "Kedi", "kopek": "Köpek"}.get(tur, "Belirtilmemiş (kedi/köpek)")
    acil_blok = (
        f"ACİL DURUM İŞARETİ: EVET. Gerekçe: {acil_gerekce}"
        if acil
        else "ACİL DURUM İŞARETİ: Hayır."
    )

    istem = f"""Hayvan türü: {tur_etiketi}
Sahibin yazdığı şikâyet: "{kullanici_metni}"
NLP ile ayıklanan bulgular: {', '.join(bulgular or []) or 'yok'}
{acil_blok}

Makine öğrenmesi modelinin (TF-IDF + Logistic Regression) tahminleri:
{_tahmin_metni(tahminler)}

Yukarıdaki tahminlere dayanarak sahibe yönelik ön değerlendirme metnini yaz."""

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
            return GeminiYanit("", MODEL_ADI, False, "Model boş yanıt döndürdü.")
        return GeminiYanit(metin, MODEL_ADI, True)

    except Exception as exc:
        logger.error("Gemini çağrısı başarısız: %s", exc)
        return GeminiYanit("", MODEL_ADI, False, str(exc))


def kapsam_disi_yanit(kullanici_metni: str) -> GeminiYanit:
    """Konu disi sorular icin kisa, kibar bir yonlendirme uretir.

    Guardrail bu metni Gemini'siz de uretebilir; burasi sadece daha dogal
    bir cumle kurmak icin opsiyonel bir zenginlestirme.
    """
    client = _get_client()
    if client is None:
        return GeminiYanit("", MODEL_ADI, False, "Gemini devre dışı.")
    try:
        from google.genai import types

        yanit = client.models.generate_content(
            model=MODEL_ADI,
            contents=(
                f'Kullanıcı şunu yazdı: "{kullanici_metni}"\n'
                "Bu bir evcil hayvan sağlığı şikâyeti değil. Tek paragrafta, en fazla "
                "35 kelimeyle, kibarca sadece kedi ve köpek sağlık şikâyetlerinde "
                "yardımcı olabildiğini söyle ve örnek bir şikâyet yazımı öner. "
                "Türkçe karakterleri eksiksiz kullan, markdown kullanma."
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
        logger.error("Gemini kapsam dışı yanıt hatası: %s", exc)
        return GeminiYanit("", MODEL_ADI, False, str(exc))


if __name__ == "__main__":  # python gemini_api.py
    import sys

    # Windows konsolu varsayilan cp1252 kullanir ve Turkce karakterde coker.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO)
    print("Gemini kullanılabilir:", kullanilabilir_mi())
    if kullanilabilir_mi():
        class _T:
            def __init__(self, h, o):
                self.hastalik, self.olasilik = h, o

        r = yorumla(
            "Kedim iki gündür kusuyor ve mama yemiyor",
            "kedi",
            [_T("Gastroenterit", 0.35), _T("Kronik Böbrek Yetmezliği", 0.08)],
            bulgular=["kusma", "istahsizlik"],
        )
        print("\nBaşarılı:", r.basarili, "\n")
        print(r.metin or r.hata)
