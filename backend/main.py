"""VetAI REST API - FastAPI uygulamasi.

Istek akisi (/api/analyze):

    metin
      |-> 1. NLP temizligi        (nlp_engine)
      |-> 2. GUVENLIK KONTROLLERI (guardrails, bu dosya)
      |       - prompt injection
      |       - kapsam disi / insan sagligi
      |       - acil durum tespiti
      |-> 3. ML tahmini           (ml_model: TF-IDF + Logistic Regression)
      |-> 4. Gemini yorumu        (gemini_api)
      |-> 5. Canli ogrenme        (yeni semptom SQLite'a yazilir)
      -> JSON
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import gemini_api
import ml_model
from database import (
    KAYNAK_AUTO,
    KAYNAK_PENDING,
    KAYNAK_SEED,
    Symptom,
    get_db,
    init_database,
)
from nlp_engine import (
    PHRASE_SYNONYMS,
    WORD_SYNONYMS,
    detect_tur,
    extract_keywords,
    normalize,
    tokenize,
    token_overlap,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vetai")

# ==========================================================================
# GUARDRAIL SABITLERI
# ==========================================================================

# --- 1) Acil durum: bu ifadelerden biri gecerse yanit acil olarak isaretlenir.
ACIL_KALIPLAR: dict[str, str] = {
    r"nefes alam|nefes alamiyor|soluk alam": "Solunum sikintisi",
    r"nefes darligi|zor nefes|hizli nefes": "Solunum sikintisi",
    r"bilincini kaybet|bayildi|tepki vermiyor|kendine gelmiyor": "Bilinc kaybi",
    r"nobet|havale|kasilma|konvulsiyon": "Nobet gecirme",
    r"kanli ishal|kanli diski|kanli kusma|kan kusuyor": "Kanli sindirim bulgusu",
    r"durmayan kanama|kanama durmuyor|siddetli kanama": "Kontrolsuz kanama",
    r"zehir|fare zehiri|deterjan|antifiriz|cikolata yedi|ilac yedi": "Zehirlenme suphesi",
    r"idrar yapam|cis yapam|isiyemiyor": "Idrar tikanikligi (ozellikle erkek kedide oldurucu)",
    r"araba carpti|yuksekten dustu|ezildi|darbe aldi": "Travma",
    r"dogum|doguramiyor|sanci": "Dogum komplikasyonu",
    r"karni sisti ve|sert sismis karin": "Mide burulmasi suphesi",
    r"dili mor|diseti beyaz|solgun diseti": "Dolasim bozuklugu",
    r"sicakta kaldi|arabada kaldi|sicak carpmasi": "Sicak carpmasi",
    r"kemik cikti|kirik|kemigi kirildi": "Kirik suphesi",
}
_ACIL_REGEX = [(re.compile(k), v) for k, v in ACIL_KALIPLAR.items()]

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

# --- 5) Kapsam kontrolu: alan sozlugundeki tum kanonik terimler
ALAN_TERIMLERI: set[str] = (
    set(PHRASE_SYNONYMS.values())
    | set(WORD_SYNONYMS.values())
    | {"kedi", "kopek", "hayvan", "yavru", "veteriner", "asi", "mama", "pati", "kuyruk"}
)

# Alan icinde olup semptom bildirmeyen, tek basina yetersiz kelimeler
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
    metin: str = Field(..., min_length=1, max_length=2000, description="Sahibin sikayeti")
    tur: Optional[Literal["kedi", "kopek", "genel"]] = Field(
        None, description="Bos birakilirsa metinden otomatik tespit edilir"
    )


class TahminCikti(BaseModel):
    hastalik: str
    olasilik: float
    yuzde: float
    oneri: str
    aciklayici_kelimeler: List[str] = []


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
    uyarilar: List[str] = []
    ogrenildi: bool = False
    model_bilgi: Optional[ModelBilgisi] = None


class SaglikYaniti(BaseModel):
    durum: str
    veritabani: bool
    model: ModelBilgisi
    gemini_aktif: bool
    gemini_model: str


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
    durum = ml_model.egit()
    if durum.egitildi:
        logger.info(
            "ML modeli hazir: %s ornek, %s sinif, %s ozellik, capraz dogrulama=%s",
            durum.ornek_sayisi, durum.sinif_sayisi, durum.ozellik_sayisi, durum.dogruluk,
        )
    else:
        logger.warning(
            "ML modeli egitilemedi (yeterli veri yok). Once: python init_db.py"
        )
    logger.info(
        "Gemini katmani: %s", "AKTIF" if gemini_api.kullanilabilir_mi() else "DEVRE DISI (API anahtari yok)"
    )
    yield
    logger.info("VetAI kapatiliyor.")


app = FastAPI(
    title="VetAI API",
    description="Evcil hayvan semptom on-degerlendirme servisi "
                "(TF-IDF + Logistic Regression + Gemini 2.5 Flash)",
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

def acil_mi(normalized: str) -> tuple[bool, str]:
    """Metinde acil mudahale gerektiren bir ifade var mi?"""
    gerekceler = [aciklama for kalip, aciklama in _ACIL_REGEX if kalip.search(normalized)]
    return bool(gerekceler), "; ".join(dict.fromkeys(gerekceler))


def alan_ici_mi(tokens: List[str]) -> tuple[bool, bool]:
    """(alan_icinde_mi, semptom_var_mi) doner."""
    kanonik = {t.replace("yok_", "") for t in tokens}
    eslesen = kanonik & ALAN_TERIMLERI
    semptom_var = bool(eslesen - HAYVAN_TERIMLERI)
    return bool(eslesen), semptom_var


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
            f"ACIL UYARI: Anlattiklariniz {acil_gerekce.lower()} isareti tasiyor. "
            "Lutfen vakit kaybetmeden en yakin veteriner klinigine basvurun."
        )
    if tahminler:
        ilk = tahminler[0]
        parcalar.append(
            f"Belirttiginiz bulgular, veritabanindaki kayitlarla en cok "
            f"\"{ilk.hastalik}\" tablosuna benziyor (model olasiligi %{ilk.olasilik * 100:.0f}). "
            "Bu kesin bir teshis degil, yalnizca istatistiksel bir on-degerlendirmedir."
        )
        if ilk.oneri:
            parcalar.append(ilk.oneri)
    parcalar.append(
        "Kesin tani ve tedavi icin mutlaka bir veteriner hekime muayene ettirin."
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
        "uc_noktalar": ["/api/analyze", "/api/health", "/api/stats", "/api/symptoms", "/api/retrain"],
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
    )


@app.post("/api/analyze", response_model=AnalizYaniti, tags=["analiz"])
def analiz_et(
    istek: AnalizIstegi,
    arka_plan: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Ana uc nokta: sikayet metnini analiz eder."""
    ham = istek.metin.strip()
    normalized = normalize(ham)
    uyarilar: List[str] = []

    # ---------------- GUARDRAIL 1: talimat ele gecirme -----------------
    if INJECTION_KALIPLARI.search(normalized):
        logger.warning("Prompt injection denemesi engellendi: %r", ham[:80])
        return AnalizYaniti(
            durum="reddedildi",
            mesaj="Bu istegi isleyemiyorum.",
            tur="genel",
            ai_yorum="Sistem talimatlarini degistirmeye yonelik istekleri isleyemem. "
                     "Evcil hayvaninizin saglik sikayetini yazarsaniz yardimci olabilirim.",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 2: cok kisa girdi ----------------------
    if len(normalized) < MIN_KARAKTER:
        return AnalizYaniti(
            durum="belirsiz",
            mesaj="Sikayet cok kisa.",
            tur="genel",
            ai_yorum="Degerlendirme yapabilmem icin biraz daha ayrinti gerekiyor. "
                     "Hayvaninizin turunu, sikayetin ne zaman basladigini ve "
                     "gozlemlediginiz belirtileri yazar misiniz? "
                     "Ornek: \"Kedim iki gundur kusuyor ve mama yemiyor.\"",
            model_bilgi=_model_bilgisi(),
        )

    tokens = tokenize(ham)
    bulgular = extract_keywords(ham)
    tur = istek.tur or detect_tur(ham)
    alan_icinde, semptom_var = alan_ici_mi(tokens)

    # ---------------- GUARDRAIL 3: insan sagligi -----------------------
    if INSAN_KALIPLARI.search(normalized) and not alan_icinde:
        return AnalizYaniti(
            durum="kapsam_disi",
            mesaj="Insan sagligi kapsam disinda.",
            tur="genel",
            ai_yorum="Ben yalnizca kedi ve kopeklerin saglik sikayetlerinde yardimci "
                     "olabilen bir veteriner on-degerlendirme asistaniyim. Insan sagligiyla "
                     "ilgili sorular icin lutfen bir hekime basvurun.",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 4: kapsam disi (2+2 vb.) ---------------
    if not alan_icinde:
        logger.info("Kapsam disi istek: %r", ham[:80])
        gemini_yanit = gemini_api.kapsam_disi_yanit(ham)
        return AnalizYaniti(
            durum="kapsam_disi",
            mesaj="Bu soru evcil hayvan sagligi kapsaminda degil.",
            tur="genel",
            ai_yorum=gemini_yanit.metin
            or ("Ben bir veteriner on-degerlendirme asistaniyim ve yalnizca kedi/kopek "
                "saglik sikayetlerini degerlendirebiliyorum. Ornek: "
                "\"Kopegim dun aksamdan beri kusuyor ve halsiz.\""),
            ai_aktif=gemini_yanit.basarili,
            ai_model=gemini_api.MODEL_ADI if gemini_yanit.basarili else "",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- GUARDRAIL 5: ilac/doz talebi ---------------------
    if DOZ_KALIPLARI.search(normalized):
        uyarilar.append(
            "Ilac adi ve dozu veremem. Insan ilaclari (parasetamol, ibuprofen, aspirin) "
            "kedi ve kopeklerde oldurucudur; veteriner recetesi olmadan kesinlikle vermeyin."
        )

    # ---------------- GUARDRAIL 6: acil durum --------------------------
    acil, acil_gerekce = acil_mi(normalized)
    if acil:
        uyarilar.insert(
            0,
            f"ACIL DURUM SUPHESI ({acil_gerekce}). Bu analiz veteriner muayenesinin "
            "yerine gecmez; vakit kaybetmeden bir klinige basvurun.",
        )

    # ---------------- 7: hayvan var ama semptom yok --------------------
    if not semptom_var:
        return AnalizYaniti(
            durum="belirsiz",
            mesaj="Belirti bulunamadi.",
            tur=tur,
            bulgular=bulgular,
            acil=acil,
            acil_gerekce=acil_gerekce,
            uyarilar=uyarilar,
            ai_yorum="Hayvaninizdan bahsettiginizi anliyorum ama net bir belirti "
                     "yakalayamadim. Kusma, ishal, istahsizlik, kasinti, topallama, "
                     "oksuruk gibi gozlemlediginiz durumlari ve ne kadar suredir "
                     "devam ettigini yazarsaniz daha iyi degerlendirebilirim.",
            model_bilgi=_model_bilgisi(),
        )

    # ---------------- 8: ML TAHMINI ------------------------------------
    if not ml_model.siniflandirici.egitildi_mi():
        ml_model.egit()

    tahminler = ml_model.tahmin_et(ham, top_k=3)

    if not tahminler:
        return AnalizYaniti(
            durum="belirsiz",
            mesaj="Model anlamli bir eslesme bulamadi.",
            tur=tur,
            bulgular=bulgular,
            acil=acil,
            acil_gerekce=acil_gerekce,
            uyarilar=uyarilar,
            ai_yorum="Yazdiklarinizi veritabanimdaki hastalik tablolariyla "
                     "eslestiremedim. Belirtileri biraz daha ayrintili anlatabilir "
                     "misiniz? Her durumda bir veteriner hekime danismanizi oneririm.",
            model_bilgi=_model_bilgisi(),
        )

    en_iyi = tahminler[0]
    if en_iyi.olasilik < ml_model.GUVEN_ESIGI:
        uyarilar.append(
            f"Model bu sikayette kararsiz (en yuksek olasilik %{en_iyi.olasilik * 100:.0f}). "
            "Asagidaki tahminleri zayif bir ipucu olarak degerlendirin."
        )

    # ---------------- 9: GEMINI YORUMU ---------------------------------
    gemini_yanit = gemini_api.yorumla(
        ham, tur, tahminler, acil=acil, acil_gerekce=acil_gerekce, bulgular=bulgular
    )
    ai_yorum = gemini_yanit.metin or _sablon_yorum(tahminler, acil, acil_gerekce)
    if not gemini_yanit.basarili:
        uyarilar.append(
            "Gemini katmani su anda devre disi; asagidaki metin veritabanindaki "
            "kayitlardan uretilmistir."
        )

    # ---------------- 10: CANLI OGRENME --------------------------------
    ogrenildi = _ogren(db, ham, tur, en_iyi, tokens)
    if ogrenildi:
        # Modeli istegi bekletmeden arka planda tazele
        arka_plan.add_task(ml_model.egit)

    return AnalizYaniti(
        durum="acil" if acil else "ok",
        mesaj="Analiz tamamlandi.",
        tur=tur,
        bulgular=bulgular,
        tahminler=[
            TahminCikti(
                hastalik=t.hastalik,
                olasilik=t.olasilik,
                yuzde=round(t.olasilik * 100, 1),
                oneri=t.oneri,
                aciklayici_kelimeler=t.aciklayici_kelimeler,
            )
            for t in tahminler
        ],
        ai_yorum=ai_yorum,
        ai_aktif=gemini_yanit.basarili,
        ai_model=gemini_api.MODEL_ADI if gemini_yanit.basarili else "",
        acil=acil,
        acil_gerekce=acil_gerekce,
        uyarilar=uyarilar,
        ogrenildi=ogrenildi,
        model_bilgi=_model_bilgisi(),
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
