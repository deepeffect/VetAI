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

# Model bir tahmini "guvenilir" saymak icin gereken minimum olasilik.
GUVEN_ESIGI = 0.28


@dataclass
class Tahmin:
    hastalik: str
    olasilik: float
    oneri: str = ""
    aciklayici_kelimeler: List[str] = field(default_factory=list)


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
            metinler = [k.semptom for k in kayitlar]
            etiketler = [k.hastalik for k in kayitlar]
            agirliklar = [KAYNAK_AGIRLIK.get(k.kaynak, 0.5) for k in kayitlar]

            # Her hastalik icin tavsiye metni (ilk dolu olan gecerli sayilir)
            oneriler: dict[str, str] = {}
            for k in kayitlar:
                if k.oneri and k.hastalik not in oneriler:
                    oneriler[k.hastalik] = k.oneri
            return metinler, etiketler, agirliklar, oneriler
        finally:
            session.close()

    def egit(self) -> ModelDurumu:
        """Veritabanindaki guncel veriyle modeli bastan egitir."""
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

        dogruluk = self._capraz_dogrula(pipeline, metinler, etiketler)
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
        return self.durum

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
    def tahmin_et(self, metin: str, top_k: int = 3) -> List[Tahmin]:
        """Metin icin en olasi `top_k` hastaligi olasiliklariyla dondurur."""
        with self._lock:
            pipeline = self._pipeline
            oneriler = dict(self._oneri_haritasi)

        if pipeline is None:
            return []

        olasiliklar = pipeline.predict_proba([metin])[0]
        siniflar = pipeline.named_steps["clf"].classes_

        # Hicbir token sozluge dusmediyse model sadece sinif onceligini yansitir;
        # bu durumda tahmin uretmek yaniltici olur.
        if not pipeline.named_steps["tfidf"].transform([metin]).nnz:
            return []

        en_iyi = np.argsort(olasiliklar)[::-1][:top_k]
        return [
            Tahmin(
                hastalik=str(siniflar[i]),
                olasilik=float(round(olasiliklar[i], 4)),
                oneri=oneriler.get(str(siniflar[i]), ""),
                aciklayici_kelimeler=self.aciklayici_kelimeler(metin, str(siniflar[i])),
            )
            for i in en_iyi
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


# Uygulama genelinde tek siniflandirici ornegi
siniflandirici = SemptomSiniflandirici()


def egit() -> ModelDurumu:
    return siniflandirici.egit()


def tahmin_et(metin: str, top_k: int = 3) -> List[Tahmin]:
    return siniflandirici.tahmin_et(metin, top_k=top_k)


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
