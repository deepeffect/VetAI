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

    # --- ek meta alanlar (canli ogrenme icin) ---
    kaynak = Column(String(16), nullable=False, default=KAYNAK_SEED, index=True)
    guven = Column(Float, nullable=False, default=1.0)
    olusturma_tarihi = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:  # pragma: no cover - debug yardimcisi
        return f"<Symptom {self.id} {self.tur}/{self.hastalik} ({self.kaynak})>"


def init_database() -> None:
    """Tablolari (yoksa) olusturur."""
    Base.metadata.create_all(bind=engine)


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
