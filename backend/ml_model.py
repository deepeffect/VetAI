"""Klasik ML katmani: TF-IDF + Logistic Regression ile semptom siniflandirma.

Akis:
    SQLite (symptoms) -> nlp_engine.tokenize -> TF-IDF -> LogisticRegression
                      -> predict_proba -> ilk N hastalik + olasilik

Neden Logistic Regression?
    - Kucuk/orta veri setinde calisir, olasilik (predict_proba) uretir.
    - Katsayilari dogrudan okunabilir; hangi kelimenin hangi hastaliga ittigini
      `aciklayici_kelimeler()` ile arayuzde gosterebiliyoruz (yorumlanabilirlik).

Canli ogrenme guvenligi:
    Kullanici sorgularindan otomatik turetilen kayitlar (kaynak='auto') egitime
    dusuk ornek agirligiyla girer; boylece pseudo-labeling modeli zamanla
    bozamaz. 'pending' kayitlar egitime hic alinmaz.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from database import KAYNAK_AGIRLIK, KAYNAK_PENDING, Symptom, get_session
from nlp_engine import tokenize

# Kararsizlik olcutu (55 sinif icin). Eski mutlak esik (0.28) 55 sinifta dogru
# tahminlerin yarisini bile "kararsiz" isaretliyordu; marj tabanli olcut
# (1. ve 2. tahmin arasindaki fark) daha ayirt edici (bkz. data/UYARI_OKUYUN.txt).
MARJ_ESIGI = 0.05      # top1 - top2 bu degerin altindaysa kararsiz
GUVEN_ESIGI = 0.15     # top1 bu mutlak degerin altindaysa kararsiz

# Tur bilgisi modele girdi olarak verilir: metnin basina tokenizer'dan
# govdelenmeden gecen bir tur token'i eklenir ("kedix"/"kopekx").
TUR_TOKEN = {"kedi": "kedix", "kopek": "kopekx"}


def metin_hazirla(metin: str, tur: Optional[str]) -> str:
    """Egitim ve tahminde AYNI bicimde uygulanir: tur token'i + ham metin."""
    token = TUR_TOKEN.get(tur or "")
    return f"{token} {metin}" if token else metin


@dataclass
class Tahmin:
    hastalik: str
    olasilik: float
    oneri: str = ""
    aciklayici_kelimeler: List[str] = field(default_factory=list)
    hastalik_id: str = ""            # bilgi tabani anahtari (aciliyet/tur filtresi icin)
    aciliyet: str = ""               # hastaligin temel aciliyeti: kirmizi/turuncu/yesil


@dataclass
class ModelDurumu:
    egitildi: bool = False
    ornek_sayisi: int = 0
    sinif_sayisi: int = 0
    ozellik_sayisi: int = 0
    dogruluk: Optional[float] = None       # capraz dogrulama ortalamasi
    egitim_zamani: Optional[str] = None
    siniflar: List[str] = field(default_factory=list)


class SemptomSiniflandirici:
    """TF-IDF + Logistic Regression sarmalayicisi (surec icinde tekil nesne)."""

    def __init__(self) -> None:
        self._pipeline: Optional[Pipeline] = None
        self._oneri_haritasi: dict[str, str] = {}
        self._id_haritasi: dict[str, str] = {}        # hastalik adi -> hastalik_id
        self._tur_haritasi: dict[str, str] = {}       # hastalik adi -> kedi/kopek/genel
        self._aciliyet_haritasi: dict[str, str] = {}  # hastalik adi -> temel aciliyet
        self._lock = threading.Lock()
        self.durum = ModelDurumu()

    # ---------------------------------------------------------------- egitim
    def _veriyi_yukle(self) -> tuple[list[str], list[str], list[float], dict[str, str]]:
        session = get_session()
        try:
            kayitlar = (
                session.query(Symptom)
                .filter(Symptom.kaynak != KAYNAK_PENDING)
                .all()
            )
            metinler = [metin_hazirla(k.semptom, k.tur) for k in kayitlar]
            etiketler = [k.hastalik for k in kayitlar]
            agirliklar = [KAYNAK_AGIRLIK.get(k.kaynak, 0.5) for k in kayitlar]

            # Her hastalik icin tavsiye metni (ilk dolu olan gecerli sayilir)
            oneriler: dict[str, str] = {}
            idler: dict[str, str] = {}
            turler: dict[str, set] = {}
            aciliyetler: dict[str, str] = {}
            for k in kayitlar:
                if k.oneri and k.hastalik not in oneriler:
                    oneriler[k.hastalik] = k.oneri
                if k.hastalik_id and k.hastalik not in idler:
                    idler[k.hastalik] = k.hastalik_id
                if k.tur in ("kedi", "kopek"):
                    turler.setdefault(k.hastalik, set()).add(k.tur)
                if k.aciliyet and k.hastalik not in aciliyetler:
                    aciliyetler[k.hastalik] = k.aciliyet
            self._id_haritasi = idler
            # Egitim verisinde yalnizca tek turde gorulen hastalik o ture ozgudur.
            self._tur_haritasi = {
                h: next(iter(t)) if len(t) == 1 else "genel" for h, t in turler.items()
            }
            self._aciliyet_haritasi = _temel_aciliyetler(idler) or aciliyetler
            return metinler, etiketler, agirliklar, oneriler
        finally:
            session.close()

    def egit(self, cv_arka_planda: bool = True) -> ModelDurumu:
        """Veritabanindaki guncel veriyle modeli bastan egitir.

        Capraz dogrulama 55 sinif / ~2.500 ornekte egitimin kendisinden iki kat
        uzun surer (~11 sn). Sunucu acilisini ve canli ogrenme sonrasi yeniden
        egitimi bekletmemek icin varsayilan olarak arka planda hesaplanir;
        sonuc gelene kadar `durum.dogruluk` None kalir. Olcum betigi gibi
        sonucu hemen isteyen cagiranlar `cv_arka_planda=False` verir.
        """
        metinler, etiketler, agirliklar, oneriler = self._veriyi_yukle()

        if len(set(etiketler)) < 2:
            # Tek sinifli veriyle LogisticRegression egitilemez.
            with self._lock:
                self._pipeline = None
                self._oneri_haritasi = oneriler
                self.durum = ModelDurumu(
                    egitildi=False,
                    ornek_sayisi=len(metinler),
                    sinif_sayisi=len(set(etiketler)),
                )
            return self.durum

        pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        tokenizer=tokenize,      # kendi Turkce tokenizer'imiz
                        preprocessor=None,
                        lowercase=False,         # normalizasyonu tokenizer yapiyor
                        token_pattern=None,      # tokenizer verildiginde kapatilmali
                        ngram_range=(1, 2),      # tekil token + ikili kombinasyon
                        min_df=1,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1000,
                        C=4.0,                   # kucuk veri -> daha az duzenlilestirme
                        class_weight="balanced", # nadir hastaliklar ezilmesin
                        solver="lbfgs",
                    ),
                ),
            ]
        )

        pipeline.fit(metinler, etiketler, clf__sample_weight=np.asarray(agirliklar))

        dogruluk = None if cv_arka_planda else self._capraz_dogrula(pipeline, metinler, etiketler)
        vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]

        with self._lock:
            self._pipeline = pipeline
            self._oneri_haritasi = oneriler
            self.durum = ModelDurumu(
                egitildi=True,
                ornek_sayisi=len(metinler),
                sinif_sayisi=len(pipeline.named_steps["clf"].classes_),
                ozellik_sayisi=len(vectorizer.vocabulary_),
                dogruluk=dogruluk,
                egitim_zamani=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                siniflar=sorted(pipeline.named_steps["clf"].classes_.tolist()),
            )
            durum = self.durum

        if cv_arka_planda:
            threading.Thread(
                target=self._cv_arka_plan,
                args=(pipeline, metinler, etiketler),
                name="vetai-cv",
                daemon=True,
            ).start()
        return durum

    def _cv_arka_plan(self, pipeline, metinler, etiketler) -> None:
        """Capraz dogrulamayi hesaplar; bu arada daha yeni bir egitim olduysa sonucu atar."""
        dogruluk = self._capraz_dogrula(pipeline, metinler, etiketler)
        with self._lock:
            if self._pipeline is pipeline:
                self.durum = dataclasses.replace(self.durum, dogruluk=dogruluk)
        logging.getLogger("vetai.ml").info("Capraz dogrulama tamamlandi: %s", dogruluk)

    @staticmethod
    def _capraz_dogrula(pipeline: Pipeline, metinler: list[str], etiketler: list[str]) -> Optional[float]:
        """Veri yeterliyse k-katli capraz dogrulama skoru dondurur."""
        _, sayilar = np.unique(etiketler, return_counts=True)
        k = int(min(3, sayilar.min()))
        if k < 2:
            return None
        try:
            skorlar = cross_val_score(
                pipeline,
                metinler,
                etiketler,
                cv=StratifiedKFold(n_splits=k, shuffle=True, random_state=42),
                scoring="accuracy",
            )
            return float(round(skorlar.mean(), 4))
        except Exception:  # pragma: no cover - CV bir sekilde basarisizsa tahmini engelleme
            return None

    def egitildi_mi(self) -> bool:
        return self._pipeline is not None

    # --------------------------------------------------------------- tahmin
    def tahmin_et(self, metin: str, top_k: int = 3, tur: Optional[str] = None) -> List[Tahmin]:
        """Metin icin en olasi `top_k` hastaligi olasiliklariyla dondurur.

        `tur` verilirse (kedi/kopek) metne tur token'i eklenir ve o turde
        gorulmeyen hastaliklarin olasiligi sifirlanip dagilim yeniden
        normalize edilir (tur filtresi).
        """
        with self._lock:
            pipeline = self._pipeline
            oneriler = dict(self._oneri_haritasi)
            idler = dict(self._id_haritasi)
            turler = dict(self._tur_haritasi)
            aciliyetler = dict(self._aciliyet_haritasi)

        if pipeline is None:
            return []

        hazir = metin_hazirla(metin, tur)
        # Hicbir token sozluge dusmediyse model sadece sinif onceligini yansitir;
        # bu durumda tahmin uretmek yaniltici olur. (Tur token'i sayilmaz.)
        if not pipeline.named_steps["tfidf"].transform([metin]).nnz:
            return []

        olasiliklar = np.asarray(pipeline.predict_proba([hazir])[0], dtype=float)
        siniflar = pipeline.named_steps["clf"].classes_

        if tur in ("kedi", "kopek"):
            for j, sinif in enumerate(siniflar):
                if turler.get(str(sinif), "genel") not in ("genel", tur):
                    olasiliklar[j] = 0.0
            toplam = olasiliklar.sum()
            if toplam > 0:
                olasiliklar = olasiliklar / toplam

        en_iyi = np.argsort(olasiliklar)[::-1][:top_k]
        return [
            Tahmin(
                hastalik=str(siniflar[i]),
                olasilik=float(round(olasiliklar[i], 4)),
                oneri=oneriler.get(str(siniflar[i]), ""),
                aciklayici_kelimeler=self.aciklayici_kelimeler(metin, str(siniflar[i])),
                hastalik_id=idler.get(str(siniflar[i]), ""),
                aciliyet=aciliyetler.get(str(siniflar[i]), ""),
            )
            for i in en_iyi
            if olasiliklar[i] > 0
        ]

    def aciklayici_kelimeler(self, metin: str, hastalik: str, limit: int = 4) -> List[str]:
        """Bu tahmini en cok destekleyen kelimeler (yorumlanabilirlik).

        TF-IDF agirligi x ilgili sinifin Logistic Regression katsayisi.
        """
        with self._lock:
            pipeline = self._pipeline
        if pipeline is None:
            return []

        vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]
        clf: LogisticRegression = pipeline.named_steps["clf"]

        siniflar = clf.classes_.tolist()
        if hastalik not in siniflar:
            return []

        vec = vectorizer.transform([metin])
        if not vec.nnz:
            return []

        idx = siniflar.index(hastalik)
        # Ikili siniflandirmada coef_ tek satirdir; cok sinifta sinif basina satir.
        katsayilar = clf.coef_[0] if clf.coef_.shape[0] == 1 else clf.coef_[idx]

        isimler = vectorizer.get_feature_names_out()
        katkilar = [
            (isimler[j], float(vec[0, j] * katsayilar[j]))
            for j in vec.nonzero()[1]
        ]
        katkilar = [(ad, skor) for ad, skor in katkilar if skor > 0]
        katkilar.sort(key=lambda t: t[1], reverse=True)
        return [ad.replace("_", " ") for ad, _ in katkilar[:limit]]


def _temel_aciliyetler(idler: dict[str, str]) -> dict[str, str]:
    """hastalik adi -> temel aciliyet; data/hastalik_aciliyet.json'dan (varsa)."""
    import json
    import os

    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hastalik_aciliyet.json")
    try:
        with open(yol, encoding="utf-8") as f:
            id_aciliyet = json.load(f)
    except (OSError, ValueError):
        return {}
    return {ad: id_aciliyet[hid] for ad, hid in idler.items() if hid in id_aciliyet}


# Uygulama genelinde tek siniflandirici ornegi
siniflandirici = SemptomSiniflandirici()


def egit(cv_arka_planda: bool = True) -> ModelDurumu:
    return siniflandirici.egit(cv_arka_planda=cv_arka_planda)


def tahmin_et(metin: str, top_k: int = 3, tur: Optional[str] = None) -> List[Tahmin]:
    return siniflandirici.tahmin_et(metin, top_k=top_k, tur=tur)


def kararsiz_mi(tahminler: List[Tahmin]) -> bool:
    """Arayuz tek hastalik yerine 'su tablolardan biri olabilir' dili kullanmali mi?"""
    if not tahminler:
        return True
    ilk = tahminler[0].olasilik
    ikinci = tahminler[1].olasilik if len(tahminler) > 1 else 0.0
    return ilk < GUVEN_ESIGI or (ilk - ikinci) < MARJ_ESIGI


def durum() -> ModelDurumu:
    return siniflandirici.durum


if __name__ == "__main__":  # python ml_model.py
    d = egit()
    print(f"Egitildi: {d.egitildi} | ornek={d.ornek_sayisi} sinif={d.sinif_sayisi} "
          f"ozellik={d.ozellik_sayisi} dogruluk={d.dogruluk}")
    for ornek in [
        "kedim iki gundur kusuyor ve hic mama yemiyor",
        "kopegim kulagini kasiyor ve kafasini salliyor",
        "erkek kedim idrar yapamiyor kum kabinda zorlaniyor",
        "kopegim cikolata yedi simdi titriyor",
    ]:
        print(f"\n> {ornek}")
        for t in tahmin_et(ornek):
            print(f"   {t.olasilik:6.1%}  {t.hastalik:42} {t.aciklayici_kelimeler}")
