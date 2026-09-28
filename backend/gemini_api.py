"""Gemini entegrasyonu - LLM saglayici katmani (google-genai SDK).

Bu modul projede Gemini'ye dokunan TEK yerdir. Iki cagri turu sunar:

    yorumla(...)  -> /api/analyze: ML tahminini sahibe donuk metne cevirir
    sohbet(...)   -> /api/chat:    konusma gecmisiyle (multi-turn) yanit uretir

Gorev dagilimi: TESHISI ML MODELI KOYAR, Gemini koymaz. Gemini, tahmin
dagilimini anlasilir bir Turkce metne cevirir ve sohbet baglaminda
kullanicinin takip sorularini yanitlar.

Model adi, zaman asimi ve API anahtari yalnizca ortam degiskenlerinden okunur
(backend/.env). Anahtar yoksa modul devre disi kalir; cagiranlar
`GeminiYanit.hata_kodu` uzerinden durumu ayirt eder (graceful degradation).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("vetai.gemini")

# --------------------------------------------------------------------------
# YAPILANDIRMA  (tek nokta; koda baska yerde model adi yazilmaz)
# --------------------------------------------------------------------------

#: Varsayilan model. Gemini 2.5 serisi yeni projelere kapatildigi icin
#: (Google yalnizca eski kullanicilara sinirli erisim veriyor) guncel ve
#: kararli Flash surumu kullanilir. .env'deki GEMINI_MODEL ile degistirilebilir.
VARSAYILAN_MODEL = "gemini-3.8-flash"
MODEL_ADI = os.getenv("GEMINI_MODEL", "").strip() or VARSAYILAN_MODEL

#: Tek bir Gemini cagrisi icin ust sinir (ms). Frontend'in 45 sn'lik
#: zaman asimindan kisa tutulur ki hata mesaji istemciye ulasabilsin.
_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "30000"))

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

HataKodu = Literal[
    "anahtar_yok",       # GEMINI_API_KEY tanimli degil
    "yetkisiz",          # anahtar gecersiz / yetkisi yok (401, 403)
    "model_bulunamadi",  # GEMINI_MODEL yanlis ya da erisim yok (404)
    "gecersiz_istek",    # 400: istek semasi / parametre hatasi
    "kota",              # 429: hiz siniri ya da kota
    "zaman_asimi",       # cagri _TIMEOUT_MS icinde bitmedi
    "sunucu",            # 5xx: Google tarafinda gecici hata
    "engellendi",        # guvenlik filtresi istemi ya da yaniti engelledi
    "bos",               # model bos yanit dondurdu
    "bilinmeyen",
]


@dataclass
class GeminiYanit:
    metin: str
    model: str
    basarili: bool
    hata: Optional[str] = None
    hata_kodu: Optional[HataKodu] = None
    bitis_nedeni: Optional[str] = None


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
        # Windows'ta antivirus / kurumsal proxy TLS'i kendi kok sertifikasiyla
        # tarayabilir; Python'un certifi deposu bunu tanimaz ve her cagri
        # CERTIFICATE_VERIFY_FAILED ile duser. truststore, isletim sisteminin
        # sertifika deposunu kullanir (pip de ayni yontemi kullanir).
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass

        from google import genai
        from google.genai import types

        _client = genai.Client(
            api_key=_API_KEY,
            http_options=types.HttpOptions(timeout=_TIMEOUT_MS),
        )
        logger.info("Gemini istemcisi hazir (model=%s, timeout=%sms).", MODEL_ADI, _TIMEOUT_MS)
    except Exception as exc:  # pragma: no cover
        logger.error("Gemini istemcisi oluşturulamadı: %s", exc)
        _client = None
    return _client


def kullanilabilir_mi() -> bool:
    """Gemini katmani aktif mi? (/api/health ve arayuz rozetleri icin)"""
    return _get_client() is not None


# --------------------------------------------------------------------------
# ORTAK CAGRI + HATA SINIFLANDIRMA
# --------------------------------------------------------------------------

def _hata_siniflandir(exc: Exception) -> tuple[HataKodu, str]:
    """SDK istisnasini (kod, kullaniciya donuk mesaj) ciftine cevirir."""
    try:
        from google.genai import errors as genai_errors
    except Exception:  # pragma: no cover
        genai_errors = None

    metin = str(exc)
    ad = type(exc).__name__.lower()

    if "timeout" in ad or "timed out" in metin.lower() or "timeout" in metin.lower():
        return "zaman_asimi", f"Gemini {_TIMEOUT_MS // 1000} saniye içinde yanıt vermedi."
    if "certificate" in metin.lower() or "ssl" in ad:
        return "sunucu", "Gemini'ye güvenli bağlantı kurulamadı (TLS sertifikası doğrulanamadı)."

    kod = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if genai_errors is not None and isinstance(exc, genai_errors.APIError):
        kod = kod or exc.code

    if kod in (401, 403):
        return "yetkisiz", "Gemini API anahtarı geçersiz ya da bu model için yetkisi yok."
    if kod == 404:
        return "model_bulunamadi", f"Gemini modeli bulunamadı: '{MODEL_ADI}'. GEMINI_MODEL değerini kontrol edin."
    if kod == 429:
        return "kota", "Gemini istek sınırı aşıldı. Lütfen biraz sonra tekrar deneyin."
    if kod == 400:
        # Bilinmeyen model adlari da bazen 400 ile doner
        if "model" in metin.lower() and ("not found" in metin.lower() or "not supported" in metin.lower()):
            return "model_bulunamadi", f"Gemini modeli bulunamadı: '{MODEL_ADI}'. GEMINI_MODEL değerini kontrol edin."
        if "api key" in metin.lower():
            return "yetkisiz", "Gemini API anahtarı geçersiz."
        return "gecersiz_istek", "Gemini isteği reddetti (geçersiz istek)."
    if isinstance(kod, int) and kod >= 500:
        return "sunucu", "Gemini tarafında geçici bir sorun oluştu. Lütfen tekrar deneyin."
    if "connect" in metin.lower() or "network" in metin.lower() or "resolve" in metin.lower():
        return "sunucu", "Gemini servisine ulaşılamadı (ağ hatası)."
    return "bilinmeyen", "Gemini çağrısı beklenmeyen bir hatayla sonuçlandı."


#: `thinking_level` yerine token butcesi bekleyen 2.5 serisi icin karsiliklar.
_DUSUNME_BUTCESI = {"MINIMAL": 0, "LOW": 1024, "MEDIUM": 4096, "HIGH": 8192}


def _model_surumu(ad: str) -> tuple[int, int]:
    """Model adindan (ornegin "gemini-2.5-flash") surum ikilisini cikarir."""
    eslesme = re.search(r"gemini-(\d+)(?:\.(\d+))?", ad)
    if not eslesme:
        return (0, 0)
    return (int(eslesme.group(1)), int(eslesme.group(2) or 0))


#: Dusukten yuksege dusunme seviyeleri; geri cekilme sirasi da budur.
_SEVIYE_SIRASI = ("MINIMAL", "LOW", "MEDIUM", "HIGH")

#: "Dusunme alani hic gonderilmesin" anlamina gelen ozel etiket.
_DUSUNME_YOK = "yok"

#: Ilk basarili cagridan sonra hatirlanan secim; sonraki cagrilar bosa istek
#: harcamasin diye dogrudan bununla baslar (kota kucuk oldugu icin onemli).
_secili_dusunme: Optional[str] = None


def _dusunme_yapilandirmasi(types, etiket: str):
    """Model ailesine uygun ThinkingConfig'i uretir (uymayan modelde None).

    Gemini 3.x `thinking_level` ("MINIMAL", "LOW", ...) bekler; 2.5 serisi ise
    token cinsinden `thinking_budget`. Yanlis alan gonderildiginde istek
    400 INVALID_ARGUMENT ile geri doner ve yapay zeka katmani tamamen devre
    disi kalir. 2.5 Pro dusunmeyi tamamen kapatmaya izin vermedigi icin en
    dusuk butce 128'dir.
    """
    if etiket == _DUSUNME_YOK:
        return None
    surum = _model_surumu(MODEL_ADI)
    if surum >= (3, 0):
        return types.ThinkingConfig(thinking_level=etiket)
    if surum >= (2, 5):
        butce = _DUSUNME_BUTCESI.get(etiket, 0)
        if butce == 0 and "pro" in MODEL_ADI:
            butce = 128
        return types.ThinkingConfig(thinking_budget=butce)
    # 2.0 ve oncesi dusunme ayarini hic desteklemez; alan gonderilmez.
    return None


def _dusunme_etiketleri(thinking_level: str) -> list[str]:
    """Sirayla denenecek dusunme secimleri.

    Ayni aile icindeki modeller bile ayni seviyeleri kabul etmiyor: ornegin
    gemini-3.8-flash "MINIMAL" seviyesini reddedip "LOW" ile calisiyor. Bu
    yuzden istenen seviye tutmazsa bir ust seviye, o da tutmazsa alanin hic
    gonderilmedigi hal denenir. Ilk basarili secim hatirlanir.
    """
    if _secili_dusunme:
        return [_secili_dusunme]

    istenen = thinking_level.upper()
    etiketler = [istenen]
    if _model_surumu(MODEL_ADI) >= (3, 0) and istenen in _SEVIYE_SIRASI:
        sonraki = _SEVIYE_SIRASI.index(istenen) + 1
        if sonraki < len(_SEVIYE_SIRASI):
            etiketler.append(_SEVIYE_SIRASI[sonraki])
    etiketler.append(_DUSUNME_YOK)
    return etiketler


def _dusunme_hatasi_mi(exc: Exception) -> bool:
    """Hata, dusunme ayarinin bu modelce kabul edilmediginden mi kaynaklaniyor?"""
    metin = str(exc).lower()
    return "thinking" in metin and ("not supported" in metin or "invalid" in metin)


def _uret(contents, *, system_instruction: Optional[str], max_output_tokens: int,
          thinking_level: str = "MINIMAL") -> GeminiYanit:
    """Tek bir generate_content cagrisi; yaniti dogrular ve hatayi siniflandirir.

    Dusunme ayari model ailesine gore secilir (bkz. `_dusunme_yapilandirmasi`).
    Sicaklik (temperature) varsayilan 1.0'da birakilir: Google, 3.x serisinde
    dusurulmesinin dongu/kalite sorunlarina yol acabilecegini belirtiyor.
    """
    global _secili_dusunme

    client = _get_client()
    if client is None:
        return GeminiYanit("", MODEL_ADI, False,
                           "Gemini API anahtarı tanımlı değil.", "anahtar_yok")

    try:
        from google.genai import types
    except Exception as exc:  # pragma: no cover - SDK kurulu degilse
        logger.error("google-genai SDK yüklenemedi: %s", exc)
        return GeminiYanit("", MODEL_ADI, False,
                           "Gemini istemcisi yüklenemedi.", "bilinmeyen")

    etiketler = _dusunme_etiketleri(thinking_level)
    yanit = None
    for sira, etiket in enumerate(etiketler):
        try:
            yanit = client.models.generate_content(
                model=MODEL_ADI,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=max_output_tokens,
                    thinking_config=_dusunme_yapilandirmasi(types, etiket),
                    # Arac (tool) kullanmiyoruz; otomatik fonksiyon cagrisini kapatiyoruz.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except Exception as exc:
            if _dusunme_hatasi_mi(exc) and sira + 1 < len(etiketler):
                logger.info(
                    "Model '%s' düşünme seviyesi '%s' kabul etmedi, '%s' deneniyor.",
                    MODEL_ADI, etiket, etiketler[sira + 1],
                )
                continue
            kod, mesaj = _hata_siniflandir(exc)
            logger.error("Gemini çağrısı başarısız (%s): %s", kod, exc)
            return GeminiYanit("", MODEL_ADI, False, mesaj, kod)

        if _secili_dusunme != etiket:
            logger.info("Düşünme ayarı '%s' olarak belirlendi (model=%s).", etiket, MODEL_ADI)
            _secili_dusunme = etiket
        break

    # --- Yanit dogrulama --------------------------------------------------
    geri_bildirim = getattr(yanit, "prompt_feedback", None)
    if geri_bildirim is not None and getattr(geri_bildirim, "block_reason", None):
        neden = str(geri_bildirim.block_reason)
        logger.warning("Gemini istemi engelledi: %s", neden)
        return GeminiYanit("", MODEL_ADI, False,
                           "Bu istek güvenlik filtresi tarafından engellendi.", "engellendi", neden)

    adaylar = getattr(yanit, "candidates", None) or []
    bitis = None
    if adaylar:
        bitis_enum = getattr(adaylar[0], "finish_reason", None)
        bitis = getattr(bitis_enum, "name", None) or (str(bitis_enum) if bitis_enum else None)

    try:
        metin = (yanit.text or "").strip()
    except Exception:
        metin = ""

    if not metin:
        if bitis in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}:
            return GeminiYanit("", MODEL_ADI, False,
                               "Yanıt güvenlik filtresi tarafından engellendi.", "engellendi", bitis)
        logger.warning("Gemini boş yanıt döndürdü (finish_reason=%s).", bitis)
        return GeminiYanit("", MODEL_ADI, False, "Model boş yanıt döndürdü.", "bos", bitis)

    if bitis == "MAX_TOKENS":
        logger.info("Gemini yanıtı çıktı sınırında kesildi.")
    return GeminiYanit(metin, MODEL_ADI, True, bitis_nedeni=bitis)


# --------------------------------------------------------------------------
# /api/analyze icin: ML tahminini metne cevir
# --------------------------------------------------------------------------

def _tahmin_metni(tahminler: Sequence) -> str:
    if not tahminler:
        return "Model, veritabanındaki hiçbir hastalıkla anlamlı eşleşme bulamadı."
    satirlar = []
    for i, t in enumerate(tahminler, start=1):
        satirlar.append(f"{i}. {t.hastalik} - olasılık %{t.olasilik * 100:.0f}")
    return "\n".join(satirlar)


def analiz_baglami(
    kullanici_metni: str,
    tur: str,
    tahminler: Sequence,
    *,
    acil: bool = False,
    acil_gerekce: str = "",
    bulgular: Optional[List[str]] = None,
) -> str:
    """ML ciktisini Gemini'ye verilecek baglam metnine cevirir.

    Hem tek atimlik `yorumla` hem de sohbet akisindaki 'guncel tur baglami'
    ayni bicimi kullanir; boylece iki yol arasinda istem farki olusmaz.
    """
    tur_etiketi = {"kedi": "Kedi", "kopek": "Köpek"}.get(tur, "Belirtilmemiş (kedi/köpek)")
    acil_blok = (
        f"ACİL DURUM İŞARETİ: EVET. Gerekçe: {acil_gerekce}"
        if acil
        else "ACİL DURUM İŞARETİ: Hayır."
    )
    return f"""Hayvan türü: {tur_etiketi}
Sahibin yazdığı şikâyet: "{kullanici_metni}"
NLP ile ayıklanan bulgular: {', '.join(bulgular or []) or 'yok'}
{acil_blok}

Makine öğrenmesi modelinin (TF-IDF + Logistic Regression) tahminleri:
{_tahmin_metni(tahminler)}"""


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
    istem = (
        analiz_baglami(kullanici_metni, tur, tahminler, acil=acil,
                       acil_gerekce=acil_gerekce, bulgular=bulgular)
        + "\n\nYukarıdaki tahminlere dayanarak sahibe yönelik ön değerlendirme metnini yaz."
    )
    return _uret(istem, system_instruction=SISTEM_TALIMATI, max_output_tokens=700)


def kapsam_disi_yanit(kullanici_metni: str) -> GeminiYanit:
    """Konu disi sorular icin kisa, kibar bir yonlendirme uretir.

    Guardrail bu metni Gemini'siz de uretebilir; burasi sadece daha dogal
    bir cumle kurmak icin opsiyonel bir zenginlestirme.
    """
    return _uret(
        f'Kullanıcı şunu yazdı: "{kullanici_metni}"\n'
        "Bu bir evcil hayvan sağlığı şikâyeti değil. Tek paragrafta, en fazla "
        "35 kelimeyle, kibarca sadece kedi ve köpek sağlık şikâyetlerinde "
        "yardımcı olabildiğini söyle ve örnek bir şikâyet yazımı öner. "
        "Türkçe karakterleri eksiksiz kullan, markdown kullanma.",
        system_instruction=None,
        max_output_tokens=200,
    )


# --------------------------------------------------------------------------
# /api/chat icin: konusma gecmisiyle yanit
# --------------------------------------------------------------------------

def sohbet(
    gecmis: Sequence[tuple[str, str]],
    *,
    system_instruction: str,
    max_output_tokens: int = 1024,
) -> GeminiYanit:
    """Cok turlu sohbet cagrisi.

    `gecmis`: (rol, metin) ciftleri; rol "user" ya da "model" olmali ve son
    eleman kullaniciya ait olmalidir. Bu mapping'i chat_service.baglam_olustur
    yapar; burada yalnizca SDK tipine cevrilir.
    """
    try:
        from google.genai import types
    except Exception as exc:  # pragma: no cover
        return GeminiYanit("", MODEL_ADI, False, str(exc), "bilinmeyen")

    contents = [
        types.Content(role=rol, parts=[types.Part.from_text(text=metin)])
        for rol, metin in gecmis
    ]
    return _uret(contents, system_instruction=system_instruction,
                 max_output_tokens=max_output_tokens)


if __name__ == "__main__":  # python gemini_api.py
    import sys

    # Windows konsolu varsayilan cp1252 kullanir ve Turkce karakterde coker.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO)
    print("Model:", MODEL_ADI)
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
        print(r.metin or f"{r.hata_kodu}: {r.hata}")
