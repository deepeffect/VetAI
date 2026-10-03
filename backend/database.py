"""SQLite baglantisi ve ORM modelleri.

Tek bir `symptoms` tablosu hem egitim veri seti hem de canli ogrenme deposu
olarak kullanilir. `kaynak` kolonu, elle girilmis "altin" veriyi (seed) kullanici
sorgularindan otomatik tureyen veriden (auto / pending) ayirir; ml_model.py
bu ayrimi egitimde ornek agirligi olarak kullanir.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "vetai.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# check_same_thread=False -> FastAPI'nin threadpool'undan gelen istekler icin gerekli.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# --- Kayit kaynaklari -------------------------------------------------------
KAYNAK_SEED = "seed"          # init_db.py: veri setindeki elle yazilmis ornekler
KAYNAK_SENTETIK = "sentetik"  # init_db.py: uret.py ile kurallı üretilmiş cümleler
KAYNAK_AUTO = "auto"          # yuksek guvenle siniflandirilip otomatik ogrenilen veri
KAYNAK_PENDING = "pending"    # dusuk guvenli, egitime girmez, insan onayi bekler

# Egitimde kaynaga gore ornek agirligi (pseudo-labeling'in modeli bozmamasi icin)
KAYNAK_AGIRLIK = {
    KAYNAK_SEED: 1.0,
    KAYNAK_SENTETIK: 0.7,
    KAYNAK_AUTO: 0.35,
    KAYNAK_PENDING: 0.0,
}


class Symptom(Base):
    """Bir semptom metni <-> hastalik eslesmesi (tek egitim ornegi)."""

    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tur = Column(String(32), nullable=False, index=True)       # kedi / kopek / genel
    semptom = Column(Text, nullable=False)                     # ham serbest metin
    hastalik = Column(String(128), nullable=False, index=True)  # ML etiketi (Turkce ad)
    hastalik_id = Column(String(64), nullable=True, index=True) # bilgi tabani anahtari (ör. "parvovirus")
    oneri = Column(Text, nullable=False, default="")           # kullaniciya gosterilecek tavsiye
    aciliyet = Column(String(16), nullable=True)               # kirmizi / turuncu / yesil (veri setinden)
    kaynak_id = Column(String(32), nullable=True, index=True)  # veri dosyasındaki satır kimliği (ör. "HD0001")

    # --- ek meta alanlar (canli ogrenme icin) ---
    kaynak = Column(String(16), nullable=False, default=KAYNAK_SEED, index=True)
    guven = Column(Float, nullable=False, default=1.0)
    olusturma_tarihi = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:  # pragma: no cover - debug yardimcisi
        return f"<Symptom {self.id} {self.tur}/{self.hastalik} ({self.kaynak})>"


def eksik_kolonlari_tamamla() -> list[str]:
    """Var olan tablolara sonradan eklenen nullable kolonlari ALTER ile ekler.

    `Base.metadata.create_all` yalnizca olmayan tabloyu olusturur; var olan bir
    tabloyu guncellemez. Bu yuzden eski surumden kalan bir vetai.db dosyasinda
    yeni kolonlar (ornegin hastalik_id, aciliyet) eksik kalir ve tabloya yapilan
    her sorgu "no such column" hatasiyla patlar. Bu fonksiyon o farki kapatir.

    Geriye eklenen kolon adlarini dondurur (ornegin ["symptoms.hastalik_id"]).
    """
    denetci = inspect(engine)
    eklenenler: list[str] = []
    for tablo in Base.metadata.sorted_tables:
        if not denetci.has_table(tablo.name):
            continue
        mevcut = {k["name"] for k in denetci.get_columns(tablo.name)}
        for kolon in tablo.columns:
            if kolon.name in mevcut:
                continue
            if not kolon.nullable:
                # NOT NULL kolon ALTER ile guvenle eklenemez; tam yeniden kurulum
                # gerekir (python init_db.py --reset).
                continue
            tip = kolon.type.compile(engine.dialect)
            with engine.begin() as baglanti:
                baglanti.execute(
                    text(f"ALTER TABLE {tablo.name} ADD COLUMN {kolon.name} {tip}")
                )
            eklenenler.append(f"{tablo.name}.{kolon.name}")
    return eklenenler


def init_database() -> None:
    """Tablolari (yoksa) olusturur ve eski semadaki eksik kolonlari tamamlar."""
    Base.metadata.create_all(bind=engine)
    eksikler = eksik_kolonlari_tamamla()
    if eksikler:
        print(f"[database] Eski şemaya eklenen kolonlar: {', '.join(eksikler)}")


def get_session() -> Session:
    """Tek kullanimlik session. Cagiran kapatmaktan sorumludur."""
    return SessionLocal()


def get_db():
    """FastAPI dependency: istek basina session acar ve kapatir."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
