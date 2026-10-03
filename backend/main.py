"""VetAI REST API - FastAPI uygulamasi.

Istek akisi (/api/analyze):

    metin
      |-> 1. NLP temizligi        (nlp_engine)
      |-> 2. GUVENLIK KONTROLLERI (guardrails, bu dosya)
      |       - prompt injection
      |       - kapsam disi / insan sagligi
      |       - acil durum tespiti
      |-> 3. ML tahmini           (ml_model: TF-IDF + Logistic Regression)
      |-> 3b. Anlam katmani       (anlam_katmani: Gemini sikayeti anlamca okur,
      |                            ML siralamasini duzeltir; "sicak carpti" != "araba carpti")
      |-> 4. Gemini yorumu        (gemini_api)
      |-> 5. Canli ogrenme        (yeni semptom SQLite'a yazilir)
      -> JSON
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import anlam_katmani
import chat_service
import gemini_api
import init_db
import ml_model
from konsol import utf8_cikti_ayarla
from bilgi import acil_kaliplar, kokler
from bilgi.esanlam_sozlugu import KOD_KANONIK
from chat_service import ChatMessage
from database import (
    KAYNAK_AUTO,
    KAYNAK_PENDING,
    KAYNAK_SEED,
    Symptom,
    get_db,
    init_database,
)
from nlp_engine import (
    detect_tur,
    normalize,
    tokenize,
    token_overlap,
    turkish_lower,
)

load_dotenv()
utf8_cikti_ayarla()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vetai")

# ==========================================================================
# GUARDRAIL SABITLERI
# ==========================================================================

# --- 1) Aciliyet: bilgi/acil_kaliplar.py (15 kirmizi + 42 turuncu belirti regex'i)
#        + tahmin edilen hastaligin temel aciliyeti (ml_model.Tahmin.aciliyet).
ACILIYET_METNI = {
    "kirmizi": "Bu belirtiler acil olabilir. Lütfen beklemeden en yakın veteriner kliniğine gidin.",
    "turuncu": "Bugün içinde bir veteriner hekime görünmeniz gerekir.",
    "yesil": "Birkaç gün içinde planlı bir veteriner muayenesi önerilir; belirtiler artarsa beklemeyin.",
}

# --- 2) Prompt injection / talimat ele gecirme denemeleri
INJECTION_KALIPLARI = re.compile(
    r"onceki talimatlar|talimatlari unut|sistem promptu|system prompt|"
    r"ignore (all )?previous|disregard (all )?previous|"
    r"sen artik .* degilsin|rolunu unut|jailbreak|dan modu|"
    r"prompt(u|unu) (yaz|goster|soyle)|kurallarini (yoksay|unut)"
)

# --- 3) Insan sagligi sorulari (veteriner kapsami disinda)
INSAN_KALIPLARI = re.compile(
    r"\b(benim|kendi|kendim|esim|kizim|oglum|cocugum|annem|babam|kardesim|"
    r"bebegim|torunum)\b.*\b(agri|hasta|ates|basim|midem|karnim|bogazim)\b"
    r"|\b(basim|midem|karnim|bogazim|dislerim)\s+(agriyor|agrıyor)"
    r"|\b(insanlarda|insan icin|bende)\b"
)

# --- 4) Ilac dozu talebi (asla verilmez, uyari eklenir)
DOZ_KALIPLARI = re.compile(
    r"\bkac (mg|ml|tablet|damla|doz)\b|\bdoz(u|unu|aj)\b|"
    r"\bhangi ilaci? ver|\bantibiyotik ver|\bparasetamol|\bibuprofen|\baspirin|"
    r"\bnovalgin|\bapranax|\bmajezik"
)

# --- 5) Kapsam kontrolu: bilgi/kokler.py (153 belirti kodu, kok tabanli).
#        Asagidaki kelimeler "hayvandan bahsediyor ama belirti yok" ayrimi icin.
HAYVAN_TERIMLERI = {"kedi", "kopek", "hayvan", "yavru", "pati", "kuyruk"}

# Bu uzunlugun altindaki metinler anlamli siniflandirilamaz.
MIN_KARAKTER = 8

# Otomatik ogrenme esigi: bu olasiligin ustundeki tahminler egitim verisine
# 'auto' olarak (dusuk agirlikla) yazilir, altindakiler 'pending' kalir.
OGRENME_ESIGI = 0.45

# Yeni kayit sayilmasi icin mevcut kayitlarla azami benzerlik (Jaccard)
TEKRAR_ESIGI = 0.85


# ==========================================================================
# PYDANTIC SEMALARI  (frontend/src/api.ts bu semalarla birebir eslesir)
# ==========================================================================

class AnalizIstegi(BaseModel):
    metin: str = Field(..., min_length=1, max_length=2000, description="Sahibin şikâyeti")
    tur: Optional[Literal["kedi", "kopek", "genel"]] = Field(
        None, description="Boş bırakılırsa metinden otomatik tespit edilir"
    )


class TahminCikti(BaseModel):
    hastalik: str
    olasilik: float
    yuzde: float
    oneri: str
    aciklayici_kelimeler: List[str] = []
    ml_yuzde: Optional[float] = None   # anlam katmani siralamayi degistirdiyse ML'in kendi yuzdesi
    anlam_gerekcesi: str = ""          # anlam katmaninin (Gemini) kisa gerekcesi


class ModelBilgisi(BaseModel):
    egitildi: bool
    ornek_sayisi: int
    sinif_sayisi: int
    ozellik_sayisi: int
    dogruluk: Optional[float] = None
    egitim_zamani: Optional[str] = None


class AnalizYaniti(BaseModel):
    durum: Literal["ok", "acil", "belirsiz", "kapsam_disi", "reddedildi"]
    mesaj: str
    tur: str
    bulgular: List[str] = []
    tahminler: List[TahminCikti] = []
    ai_yorum: str = ""
    ai_aktif: bool = False
    ai_model: str = ""
    acil: bool = False
    acil_gerekce: str = ""
    aciliyet: Literal["kirmizi", "turuncu", "yesil", ""] = ""
    aciliyet_bayraklari: List[str] = []
    kararsiz: bool = False
    uyarilar: List[str] = []
    ogrenildi: bool = False
    model_bilgi: Optional[ModelBilgisi] = None
    # Anlam katmani (Gemini sikayeti anlamca okuyup ML siralamasini duzeltti mi?)
    anlam_aktif: bool = False
    anlam_model: str = ""
    anlam_ozeti: str = ""
    anlam_notu: str = ""
    ml_ilk_tahmin: str = ""            # kelime tabanli ML'in tek basina ilk sirasi


class SohbetIstegi(BaseModel):
    """/api/chat girdisi: konusma gecmisi (son eleman kullanici mesaji)."""

    messages: List[ChatMessage] = Field(..., min_length=1, max_length=200)
    tur: Optional[Literal["kedi", "kopek", "genel"]] = None


class SohbetYaniti(BaseModel):
    """/api/chat ciktisi: asistan mesaji + varsa o tura ait ML analizi."""

    message: ChatMessage
    analiz: Optional[AnalizYaniti] = None
    ai_aktif: bool = False
    ai_model: str = ""


class SaglikYaniti(BaseModel):
    durum: str
    veritabani: bool
    model: ModelBilgisi
    gemini_aktif: bool
    gemini_model: str
    anlam_katmani: bool = False
    anlam_model: str = ""


class IstatistikYaniti(BaseModel):
    toplam_kayit: int
    seed_kayit: int
    auto_kayit: int
    bekleyen_kayit: int
    hastaliklar: List[dict]
    model: ModelBilgisi


class KayitCikti(BaseModel):
    id: int
    tur: str
    semptom: str
    hastalik: str
    kaynak: str
    guven: float


# ==========================================================================
# UYGULAMA YASAM DONGUSU
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VetAI baslatiliyor...")
    init_database()
    # Bos ya da eski surumden kalan bir veritabani sunucuyu durdurmasin:
    # sema tamamlanir, v1 oncesi kayitlar temizlenir, veri yoksa yuklenir.
    try:
        init_db.seed(sessiz=True)
    except Exception:
        logger.exception(
            "Başlangıç verisi yüklenemedi. Terminalde şunu çalıştırın: "
            "python init_db.py --reset"
        )
    durum = ml_model.egit()
    if durum.egitildi:
        logger.info(
            "ML modeli hazir: %s ornek, %s sinif, %s ozellik "
            "(capraz dogrulama arka planda hesaplaniyor)",
            durum.ornek_sayisi, durum.sinif_sayisi, durum.ozellik_sayisi,
        )
    else:
        logger.warning(
            "ML modeli eğitilemedi (yeterli veri yok). "
            "Terminalde şunu çalıştırın: python init_db.py --reset"
        )
    logger.info(
        "Gemini katmani: %s", "AKTIF" if gemini_api.kullanilabilir_mi() else "DEVRE DISI (API anahtari yok)"
    )
    anlam_durumu = anlam_katmani.durum()
    logger.info(
        "Anlam katmani: %s",
        f"AKTIF (model={anlam_durumu['model']})" if anlam_durumu["etkin"]
        else "DEVRE DISI (yalnizca ML + anlam ayrimi tablosu)",
    )
    yield
    logger.info("VetAI kapatiliyor.")


app = FastAPI(
    title="VetAI API",
    description="Evcil hayvan semptom on-degerlendirme servisi "
                "(TF-IDF + Logistic Regression + Gemini, 55 hastalikli sentetik veri seti v1)",
    version="1.0.0",
    lifespan=lifespan,
)

_origins = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================================
# GUARDRAIL YARDIMCILARI
# ==========================================================================

def aciliyet_belirle(ham: str, hastalik_temel: Optional[str]) -> tuple[str, List[str]]:
    """Nihai aciliyet = max(metindeki bayraklar, tahmin edilen hastaligin temel aciliyeti).

    Doner: (seviye, [kanonik bayrak adlari]). seviye: kirmizi | turuncu | yesil.
    Regex negasyonu anlamaz; bu yuzden bayraklar kullaniciya acikca gosterilir.
    """
    seviye, bayraklar = acil_kaliplar.aciliyet_tespit(ham, hastalik_temel or None)
    return seviye or "yesil", [ad for _, ad in bayraklar]


def hayvan_var_mi(tokens: List[str], tur_secimi: Optional[str]) -> bool:
    return tur_secimi in ("kedi", "kopek") or bool(
        {t.replace("yok_", "") for t in tokens} & HAYVAN_TERIMLERI
    )


def _model_bilgisi() -> ModelBilgisi:
    d = ml_model.durum()
    return ModelBilgisi(
        egitildi=d.egitildi,
        ornek_sayisi=d.ornek_sayisi,
        sinif_sayisi=d.sinif_sayisi,
        ozellik_sayisi=d.ozellik_sayisi,
        dogruluk=d.dogruluk,
        egitim_zamani=d.egitim_zamani,
    )


def _sablon_yorum(tahminler, acil: bool, acil_gerekce: str) -> str:
    """Gemini kapaliyken kullanilan, uydurmayan sablon metin."""
    parcalar: List[str] = []
    if acil:
        parcalar.append(
            f"ACİL UYARI: Anlattıklarınız {turkish_lower(acil_gerekce)} işareti "
            "taşıyor. Lütfen vakit kaybetmeden en yakın veteriner kliniğine başvurun."
        )
    if tahminler:
        ilk = tahminler[0]
        parcalar.append(
            f"Belirttiğiniz bulgular, veritabanındaki kayıtlarla en çok "
            f"\"{ilk.hastalik}\" tablosuna benziyor (model olasılığı %{ilk.olasilik * 100:.0f}). "
            "Bu kesin bir teşhis değil, yalnızca istatistiksel bir ön değerlendirmedir."
        )
        if ilk.oneri:
            parcalar.append(ilk.oneri)
    parcalar.append(
        "Kesin tanı ve tedavi için mutlaka bir veteriner hekime muayene ettirin."
    )
    return "\n\n".join(parcalar)


def _ogren(
    db: Session,
    metin: str,
    tur: str,
    tahmin,
    tokens: List[str],
) -> bool:
    """Yeni semptom ifadesini egitim verisine ekler (canli ogrenme).

    - Olasilik OGRENME_ESIGI ustundeyse kaynak='auto' (egitime dusuk agirlikla girer)
    - Altindaysa kaynak='pending' (egitime girmez, insan onayi bekler)
    - Cok benzeri zaten varsa hic eklenmez.
    """
    try:
        mevcutlar = (
            db.query(Symptom.semptom)
            .filter(Symptom.hastalik == tahmin.hastalik)
            .limit(200)
            .all()
        )
        for (var_olan,) in mevcutlar:
            if token_overlap(tokens, tokenize(var_olan)) >= TEKRAR_ESIGI:
                return False

        kayit = Symptom(
            tur=tur,
            semptom=metin.strip(),
            hastalik=tahmin.hastalik,
            hastalik_id=tahmin.hastalik_id or None,
            aciliyet=tahmin.aciliyet or None,
            oneri=tahmin.oneri or "",
            kaynak=KAYNAK_AUTO if tahmin.olasilik >= OGRENME_ESIGI else KAYNAK_PENDING,
            guven=float(tahmin.olasilik),
        )
        db.add(kayit)
        db.commit()
        logger.info(
            "Yeni semptom ogrenildi: id=%s kaynak=%s hastalik=%s",
            kayit.id, kayit.kaynak, kayit.hastalik,
        )
        return kayit.kaynak == KAYNAK_AUTO
    except Exception as exc:  # ogrenme hatasi kullaniciyi etkilemesin
        db.rollback()
        logger.error("Ogrenme sirasinda hata: %s", exc)
        return False


# ==========================================================================
# UC NOKTALAR
# ==========================================================================

@app.get("/", tags=["genel"])
def kok():
    return {
        "servis": "VetAI API",
        "surum": "1.0.0",
        "dokumantasyon": "/docs",
        "uc_noktalar": ["/api/analyze", "/api/chat", "/api/health", "/api/stats", "/api/symptoms", "/api/retrain"],
    }


@app.get("/api/health", response_model=SaglikYaniti, tags=["genel"])
def saglik(db: Session = Depends(get_db)):
    try:
        db.query(Symptom).limit(1).all()
        vt_ok = True
    except Exception:
        vt_ok = False
    return SaglikYaniti(
        durum="calisiyor",
        veritabani=vt_ok,
        model=_model_bilgisi(),
        gemini_aktif=gemini_api.kullanilabilir_mi(),
        gemini_model=gemini_api.MODEL_ADI,
        anlam_katmani=anlam_katmani.durum()["etkin"],
        anlam_model=anlam_katmani.MODEL_ADI,
    )


def _analizi_calistir(
    ham: str,
    tur_secimi: Optional[str],
    db: Session,
    arka_plan: BackgroundTasks,
    *,
    gemini_yorumu: bool = True,
    onceki_mesajlar: Optional[List[str]] = None,
) -> AnalizYaniti:
    """Guardrail + NLP + ML + anlam katmani zinciri. /api/analyze ve /api/chat ortak kullanir.

    `gemini_yorumu=False` verilirse yorum metni icin Gemini cagrilmaz ve
    `ai_yorum` bos kalir; sohbet akisi tahminleri konusma baglamiyla birlikte
    tek bir sohbet cagrisina verir. Anlam katmani (siniflandirmayi duzelten
    kucuk JSON cagrisi) bundan bagimsizdir ve Gemini erisilebilirse her
    sikayette calisir. `onceki_mesajlar` anlam katmanina baglam olarak gider.
    """
    normalized = normalize(ham)
    uyarilar: List[str] = []

    # ---------------- GUARDRAIL 1: talimat ele gecirme -----------------
    if INJECTION_KALIPLARI.search(normalized):
        logger.warning("Prompt injection denemesi engellendi: %r", ham[:80])
        return AnalizYaniti(
            durum="reddedildi",
            mesaj="Bu isteği işleyemiyorum.",
            tur="genel",
            ai_yorum="Sistem talimatlarını değiştirmeye yönelik istekleri işleyemem. "
                     "Evcil hayvanınızın sağlık şikâyetini yazarsanız yardımcı olabilirim.",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 2: cok kisa girdi ----------------------
    if len(normalized) < MIN_KARAKTER:
        return AnalizYaniti(
            durum="belirsiz",
            mesaj="Şikâyet çok kısa.",
            tur="genel",
            ai_yorum="Değerlendirme yapabilmem için biraz daha ayrıntı gerekiyor. "
                     "Hayvanınızın türünü, şikâyetin ne zaman başladığını ve "
                     "gözlemlediğiniz belirtileri yazar mısınız? "
                     "Örnek: \"Kedim iki gündür kusuyor ve mama yemiyor.\"",
            model_bilgi=_model_bilgisi(),
        )

    tokens = tokenize(ham)
    tur = (tur_secimi if tur_secimi in ("kedi", "kopek") else None) or detect_tur(ham)
    karar, belirti_kodlari, baglam_kodlari = kokler.guardrail(ham)
    bulgular = [KOD_KANONIK.get(k, k) for k in belirti_kodlari]
    hayvan_var = hayvan_var_mi(tokens, tur_secimi)

    # ---------------- GUARDRAIL 3: insan sagligi -----------------------
    # Hayvandan hic soz edilmiyorsa ve insan kalibi eslesiyorsa, belirti bulunsa
    # bile ("basim agriyor") LLM/ML'e gitmez.
    if INSAN_KALIPLARI.search(normalized) and not hayvan_var:
        return AnalizYaniti(
            durum="kapsam_disi",
            mesaj="İnsan sağlığı kapsam dışında.",
            tur="genel",
            ai_yorum="Ben yalnızca kedi ve köpeklerin sağlık şikâyetlerinde yardımcı "
                     "olabilen bir veteriner ön değerlendirme asistanıyım. İnsan sağlığıyla "
                     "ilgili sorular için lütfen bir hekime başvurun.",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 4: kapsam disi (2+2 vb.) ---------------
    if karar == "kapsam_disi" and not hayvan_var:
        logger.info("Kapsam disi istek: %r", ham[:80])
        gemini_yanit = (
            gemini_api.kapsam_disi_yanit(ham)
            if gemini_yorumu
            else gemini_api.GeminiYanit("", gemini_api.MODEL_ADI, False)
        )
        return AnalizYaniti(
            durum="kapsam_disi",
            mesaj="Bu soru evcil hayvan sağlığı kapsamında değil.",
            tur="genel",
            ai_yorum=gemini_yanit.metin
            or ("Ben bir veteriner ön değerlendirme asistanıyım ve yalnızca kedi/köpek "
                "sağlık şikâyetlerini değerlendirebiliyorum. Örnek: "
                "\"Köpeğim dün akşamdan beri kusuyor ve halsiz.\""),
            ai_aktif=gemini_yanit.basarili,
            ai_model=gemini_api.MODEL_ADI if gemini_yanit.basarili else "",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 5: ilac/doz talebi ---------------------
    if DOZ_KALIPLARI.search(normalized):
        uyarilar.append(
            "İlaç adı ve dozu veremem. İnsan ilaçları (parasetamol, ibuprofen, aspirin) "
            "kedi ve köpeklerde öldürücüdür; veteriner reçetesi olmadan kesinlikle vermeyin."
        )

    # ---------------- GUARDRAIL 6: acil durum (metin bayraklari) -------
    # Bu asamada yalnizca metindeki kirmizi/turuncu belirtiler; hastaligin
    # temel aciliyeti ML tahmininden sonra birlestirilir.
    aciliyet, bayraklar = aciliyet_belirle(ham, None)
    acil = aciliyet == "kirmizi"
    acil_gerekce = ", ".join(bayraklar)
    if acil:
        uyarilar.insert(
            0,
            f"Acil durum şüphesi ({acil_gerekce}). Bu analiz veteriner muayenesinin "
            "yerine geçmez; vakit kaybetmeden bir kliniğe başvurun.",
        )

    # ---------------- 7: ML dagilimi + ANLAM KATMANI ------------------
    # Kelime tabanli ML dagilimi once hesaplanir (anlam katmanina ipucu olarak
    # gider), sonra Gemini sikayeti anlamca okur. Kok tabanli guardrail belirti
    # bulamadiysa da ("kah kuh yapiyor" gibi halk dili) anlam katmanina sorulur.
    if not ml_model.siniflandirici.egitildi_mi():
        ml_model.egit()
    tur_ml = tur if tur in ("kedi", "kopek") else None
    dag = ml_model.dagilim(ham, tur_ml, bos_ise_duz=True)
    ml_tahminleri = ml_model.tahminlere_cevir(dag, 3) if dag is not None and not dag.ml_bos else []

    anlam = anlam_katmani.degerlendir(
        ham, tur, onceki=onceki_mesajlar, kok_kodlari=belirti_kodlari, dag=dag
    )
    if anlam is not None and anlam.belirtiler:
        # Anlam katmani olumsuzlamayi ve deyimleri anlar; rozetleri o belirler.
        bulgular = anlam.bulgu_adlari()
    anlam_alanlari = dict(
        anlam_aktif=anlam is not None,
        anlam_model=anlam.model if anlam is not None else "",
        anlam_ozeti=anlam.ozet if anlam is not None else "",
        anlam_notu=anlam.anlam_notu if anlam is not None else "",
    )

    # Anlam katmani bunun bir saglik sikayeti olmadigini soylediyse (ör. "sıcak
    # çarpması belirtileri nelerdir?") analiz karti uretilmez; sohbet serbest yanitlar.
    if anlam is not None and not anlam.saglik_sikayeti and not anlam.adaylar and not acil:
        return AnalizYaniti(
            durum="belirsiz",
            mesaj="Şikâyet olarak değerlendirilmedi.",
            tur=tur,
            ai_yorum="Bu mesajı bir sağlık şikâyeti olarak değerlendirmedim. Hayvanınızda "
                     "gözlemlediğiniz belirtileri ve ne zamandır sürdüğünü yazarsanız ön "
                     "değerlendirme yapabilirim.",
            uyarilar=uyarilar,
            model_bilgi=_model_bilgisi(),
            **anlam_alanlari,
        )

    # ---------------- 7b: hayvan var ama belirti yok -------------------
    if karar != "devam" and not (anlam is not None and anlam.analize_uygun):
        return AnalizYaniti(
            durum="acil" if acil else "belirsiz",
            mesaj="Belirti bulunamadı.",
            tur=tur,
            bulgular=bulgular,
            acil=acil,
            acil_gerekce=acil_gerekce,
            aciliyet=aciliyet,
            aciliyet_bayraklari=bayraklar,
            uyarilar=uyarilar,
            ai_yorum="Hayvanınızdan bahsettiğinizi anlıyorum ama net bir belirti "
                     "yakalayamadım. Kusma, ishal, iştahsızlık, kaşıntı, topallama, "
                     "öksürük gibi gözlemlediğiniz durumları ve ne kadar süredir "
                     "devam ettiğini yazarsanız daha iyi değerlendirebilirim.",
            model_bilgi=_model_bilgisi(),
            **anlam_alanlari,
        )

    # ---------------- 8: TAHMIN (ML + anlam duzeltmesi) ----------------
    if anlam is not None and anlam.adaylar and dag is not None:
        tahminler = anlam_katmani.uygula(dag, anlam, top_k=3)
    else:
        tahminler = ml_tahminleri
    anlam_alanlari["ml_ilk_tahmin"] = ml_tahminleri[0].hastalik if ml_tahminleri else ""

    if not tahminler:
        return AnalizYaniti(
            durum="acil" if acil else "belirsiz",
            mesaj="Model anlamlı bir eşleşme bulamadı.",
            tur=tur,
            bulgular=bulgular,
            acil=acil,
            acil_gerekce=acil_gerekce,
            aciliyet=aciliyet,
            aciliyet_bayraklari=bayraklar,
            uyarilar=uyarilar,
            ai_yorum="Yazdıklarınızı veritabanımdaki hastalık tablolarıyla "
                     "eşleştiremedim. Belirtileri biraz daha ayrıntılı anlatabilir "
                     "misiniz? Her durumda bir veteriner hekime danışmanızı öneririm.",
            model_bilgi=_model_bilgisi(),
            **anlam_alanlari,
        )

    en_iyi = tahminler[0]
    kararsiz = ml_model.kararsiz_mi(tahminler)
    if kararsiz:
        uyarilar.append(
            f"Model bu şikâyette kararsız (en yüksek olasılık %{en_iyi.olasilik * 100:.0f}); "
            "aşağıdaki tabloların herhangi biri söz konusu olabilir. Tahminleri zayıf bir "
            "ipucu olarak değerlendirin."
        )

    # ---------------- 8b: ACILIYET (bayraklar + hastalik temel duzeyi) --
    onceki_acil = acil
    aciliyet, bayraklar = aciliyet_belirle(ham, en_iyi.aciliyet)
    acil = aciliyet == "kirmizi"
    if acil and not onceki_acil:
        # Metinde kırmızı bayrak olsaydı 6. adımda acil işaretlenirdi; buradaki kırmızı
        # düzey tahmin edilen hastalıktan gelir. Turuncu bayraklar ("Kusma") gerekçe
        # sayılmaz, yalnızca bağlam olarak eklenir.
        acil_gerekce = f"{en_iyi.hastalik} tablosu acil kabul edilir"
        if bayraklar:
            acil_gerekce += f" (bulgular: {', '.join(bayraklar)})"
        uyarilar.insert(
            0,
            f"Acil durum şüphesi ({acil_gerekce}). Bu analiz veteriner muayenesinin "
            "yerine geçmez; vakit kaybetmeden bir kliniğe başvurun.",
        )
    elif aciliyet == "turuncu":
        uyarilar.append(ACILIYET_METNI["turuncu"])

    # ---------------- 9: GEMINI YORUMU ---------------------------------
    if gemini_yorumu:
        gemini_yanit = gemini_api.yorumla(
            ham, tur, tahminler, acil=acil, acil_gerekce=acil_gerekce, bulgular=bulgular,
            anlam_ozeti=anlam_alanlari["anlam_ozeti"], anlam_notu=anlam_alanlari["anlam_notu"],
        )
        ai_yorum = gemini_yanit.metin or _sablon_yorum(tahminler, acil, acil_gerekce)
        if not gemini_yanit.basarili:
            uyarilar.append(
                "Gemini katmanı şu anda devre dışı; aşağıdaki metin veritabanındaki "
                "kayıtlardan üretilmiştir."
            )
    else:
        gemini_yanit = gemini_api.GeminiYanit("", gemini_api.MODEL_ADI, False)
        ai_yorum = ""

    # ---------------- 10: CANLI OGRENME --------------------------------
    ogrenildi = _ogren(db, ham, tur, en_iyi, tokens)
    if ogrenildi:
        # Modeli istegi bekletmeden arka planda tazele
        arka_plan.add_task(ml_model.egit)

    return AnalizYaniti(
        durum="acil" if acil else "ok",
        mesaj="Analiz tamamlandı.",
        tur=tur,
        bulgular=bulgular,
        tahminler=[
            TahminCikti(
                hastalik=t.hastalik,
                olasilik=t.olasilik,
                yuzde=round(t.olasilik * 100, 1),
                oneri=t.oneri,
                aciklayici_kelimeler=t.aciklayici_kelimeler,
                ml_yuzde=round(t.ml_olasilik * 100, 1) if t.ml_olasilik is not None else None,
                anlam_gerekcesi=t.anlam_gerekcesi,
            )
            for t in tahminler
        ],
        ai_yorum=ai_yorum,
        ai_aktif=gemini_yanit.basarili,
        ai_model=gemini_api.MODEL_ADI if gemini_yanit.basarili else "",
        acil=acil,
        acil_gerekce=acil_gerekce,
        aciliyet=aciliyet,
        aciliyet_bayraklari=bayraklar,
        kararsiz=kararsiz,
        uyarilar=uyarilar,
        ogrenildi=ogrenildi,
        model_bilgi=_model_bilgisi(),
        **anlam_alanlari,
    )


@app.post("/api/analyze", response_model=AnalizYaniti, tags=["analiz"])
def analiz_et(
    istek: AnalizIstegi,
    arka_plan: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Tek atimlik analiz: sikayet metnini gecmis olmadan degerlendirir."""
    return _analizi_calistir(istek.metin.strip(), istek.tur, db, arka_plan)


# hata_kodu -> HTTP durumu (frontend bu kodlara gore mesaj gosterir)
_HATA_HTTP = {
    "anahtar_yok": 503,
    "yetkisiz": 503,
    "model_bulunamadi": 503,
    "gecersiz_istek": 502,
    "kota": 429,
    "zaman_asimi": 504,
    "sunucu": 502,
    "bilinmeyen": 502,
}


@app.post("/api/chat", response_model=SohbetYaniti, tags=["sohbet"])
def sohbet(
    istek: SohbetIstegi,
    arka_plan: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Konusma gecmisiyle calisan sohbet ucu.

    Akis:  son kullanici mesaji -> guardrail + ML analizi (Gemini'siz)
           -> chat_service (sistem talimati + son N mesaj + analiz baglami)
           -> Gemini -> asistan mesaji (+ varsa analiz karti verisi)
    """
    son = istek.messages[-1]
    if son.role != "user":
        raise HTTPException(status_code=422, detail="Son mesaj kullanıcıya ait olmalı.")
    ham = son.content.strip()
    if not ham:
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz.")
    if len(ham) > 2000:
        raise HTTPException(status_code=422, detail="Mesaj 2000 karakterden uzun olamaz.")

    def _mesaj(icerik: str) -> ChatMessage:
        return ChatMessage(
            id=f"a-{uuid.uuid4().hex[:12]}",
            role="assistant",
            content=icerik,
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    # 1) Guardrail + ML + anlam katmani (yorum metni icin LLM cagrisi olmadan)
    onceki = [m.content for m in istek.messages[:-1] if m.role == "user"][-2:]
    analiz = _analizi_calistir(
        ham, istek.tur, db, arka_plan, gemini_yorumu=False, onceki_mesajlar=onceki
    )

    # Sert reddetmeler (talimat ele gecirme, insan sagligi) LLM'e gitmez.
    if analiz.durum == "reddedildi" or (
        analiz.durum == "kapsam_disi" and analiz.mesaj.startswith("İnsan sağlığı")
    ):
        return SohbetYaniti(message=_mesaj(analiz.ai_yorum), analiz=None)

    # 2) Yalnizca gercek bir ML tahmini varsa analiz baglami ve karti uretilir.
    tahmin_var = analiz.durum in ("ok", "acil") and bool(analiz.tahminler)
    baglam = None
    if tahmin_var:
        baglam = gemini_api.analiz_baglami(
            ham,
            analiz.tur,
            analiz.tahminler,
            acil=analiz.acil,
            acil_gerekce=analiz.acil_gerekce,
            bulgular=analiz.bulgular,
            anlam_ozeti=analiz.anlam_ozeti,
            anlam_notu=analiz.anlam_notu,
        )

    # 3) LLM
    try:
        sonuc = chat_service.yanit_uret(istek.messages, baglam)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    yanit = sonuc.yanit

    if yanit.basarili:
        if tahmin_var:
            analiz.ai_yorum = yanit.metin
            analiz.ai_aktif = True
            analiz.ai_model = yanit.model
        return SohbetYaniti(
            message=_mesaj(yanit.metin),
            analiz=analiz if tahmin_var else None,
            ai_aktif=True,
            ai_model=yanit.model,
        )

    # 4) Gemini basarisiz: guvenlik engeli / bos yanit -> kontrollu mesaj
    if yanit.hata_kodu in ("engellendi", "bos"):
        return SohbetYaniti(
            message=_mesaj(
                "Bu isteğe yanıt üretemedim. Lütfen ifadeyi değiştirip tekrar deneyin; "
                "evcil hayvanınızın belirtilerini yazarsanız yardımcı olabilirim."
            ),
            analiz=None,
        )

    # 5) Gemini basarisiz ama ML tahmini var -> sablon metinle sur (graceful degradation)
    if tahmin_var:
        logger.warning("Sohbet: Gemini devre dışı (%s), şablon metin kullanılıyor.", yanit.hata_kodu)
        analiz.ai_yorum = _sablon_yorum(analiz.tahminler, analiz.acil, analiz.acil_gerekce)
        analiz.uyarilar.append(
            "Gemini katmanı şu anda devre dışı; aşağıdaki metin veritabanındaki "
            "kayıtlardan üretilmiştir."
        )
        return SohbetYaniti(message=_mesaj(analiz.ai_yorum), analiz=analiz)

    # 6) Ne LLM ne ML: kontrollu HTTP hatasi (UI bunu hata balonu olarak gosterir)
    raise HTTPException(
        status_code=_HATA_HTTP.get(yanit.hata_kodu or "bilinmeyen", 502),
        detail=yanit.hata or "Yanıt oluşturulurken bir hata oluştu.",
    )


@app.get("/api/stats", response_model=IstatistikYaniti, tags=["genel"])
def istatistikler(db: Session = Depends(get_db)):
    from sqlalchemy import func

    dagilim = (
        db.query(Symptom.hastalik, func.count(Symptom.id))
        .group_by(Symptom.hastalik)
        .order_by(func.count(Symptom.id).desc())
        .all()
    )
    sayac = dict(
        db.query(Symptom.kaynak, func.count(Symptom.id)).group_by(Symptom.kaynak).all()
    )
    return IstatistikYaniti(
        toplam_kayit=sum(sayac.values()),
        seed_kayit=sayac.get(KAYNAK_SEED, 0),
        auto_kayit=sayac.get(KAYNAK_AUTO, 0),
        bekleyen_kayit=sayac.get(KAYNAK_PENDING, 0),
        hastaliklar=[{"hastalik": h, "kayit": n} for h, n in dagilim],
        model=_model_bilgisi(),
    )


@app.get("/api/symptoms", response_model=List[KayitCikti], tags=["genel"])
def son_kayitlar(limit: int = 20, db: Session = Depends(get_db)):
    """En son eklenen semptom kayitlari (canli ogrenmeyi gozlemlemek icin)."""
    kayitlar = (
        db.query(Symptom).order_by(Symptom.id.desc()).limit(min(limit, 100)).all()
    )
    return [
        KayitCikti(
            id=k.id, tur=k.tur, semptom=k.semptom,
            hastalik=k.hastalik, kaynak=k.kaynak, guven=k.guven,
        )
        for k in kayitlar
    ]


@app.post("/api/retrain", response_model=ModelBilgisi, tags=["genel"])
def yeniden_egit():
    """Modeli veritabanindaki guncel veriyle bastan egitir."""
    ml_model.egit()
    return _model_bilgisi()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
