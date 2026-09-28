"""Veritabanını oluşturur ve başlangıç (seed) eğitim verisini yükler.

Kaynak: data/vetai_sentetik_sikayetler_v1.csv (sentetik başlangıç veri seti v1,
55 hastalık, 3.025 satır). Ayrıntı ve sınırlar için data/UYARI_OKUYUN.txt.

Kurallar:
  * Yalnızca `bolum == train` satırları yüklenir. `val` satırları ve
    data/vetai_dis_test_seti_v1.csv hiçbir zaman eğitime girmez; ölçüm için
    ayrılmıştır (bkz. olcum.py).
  * `kaynak_tipi == el_yazimi` -> kaynak 'seed' (ağırlık 1.0)
    `kaynak_tipi == uretilmis` -> kaynak 'sentetik' (ağırlık 0.7)
  * Öneri metni bilgi tabanından (data/oneriler.json) gelir: açıklama + evde
    yapılacaklar + kaçınılacaklar + veteriner uyarısı.
  * hastalik_id ve aciliyet_etkin kolonları da saklanır.

Kullanim:
    python init_db.py           # tablo yoksa oluştur, veri yoksa doldur
    python init_db.py --reset   # tabloyu sıfırla ve baştan doldur
                                # (eski 20 sınıflı veritabanından geçişte ZORUNLU)
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from konsol import utf8_cikti_ayarla
from database import (
    Base,
    KAYNAK_PENDING,
    KAYNAK_SEED,
    KAYNAK_SENTETIK,
    Symptom,
    engine,
    get_session,
    init_database,
)

VERI_DIZINI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SIKAYET_CSV = os.path.join(VERI_DIZINI, "vetai_sentetik_sikayetler_v1.csv")
ONERILER_JSON = os.path.join(VERI_DIZINI, "oneriler.json")

KAYNAK_ESLEME = {"el_yazimi": KAYNAK_SEED, "uretilmis": KAYNAK_SENTETIK}


def oneriler_yukle() -> dict[str, dict]:
    with open(ONERILER_JSON, encoding="utf-8") as f:
        return json.load(f)


def egitim_satirlari() -> list[dict]:
    """CSV'den yalnızca eğitim (train) satırlarını okur."""
    with open(SIKAYET_CSV, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["bolum"] == "train"]


def _eskimis_kayitlari_temizle(session) -> int:
    """v1 öncesi (20 sınıflı) eğitim kayıtlarını siler ve sayılarını döndürür.

    Eski sürümde `hastalik_id` kolonu yoktu; o dönemden kalan satırların
    hastalık adları bugünkü bilgi tabanında (data/oneriler.json) karşılıksız
    olduğu için modeli bozarlar. Kullanıcı sorgularından gelen `pending`
    satırlar eğitime girmediğinden korunur.
    """
    sorgu = session.query(Symptom).filter(
        Symptom.kaynak != KAYNAK_PENDING, Symptom.hastalik_id.is_(None)
    )
    sayi = sorgu.count()
    if sayi:
        sorgu.delete(synchronize_session=False)
        session.commit()
    return sayi


def seed(reset: bool = False, sessiz: bool = False) -> None:
    """Veri setini yükler. `sessiz=True` ise yapacak iş yokken çıktı üretmez."""
    if reset:
        print("[init_db] Tablolar siliniyor (--reset)...")
        Base.metadata.drop_all(bind=engine)

    init_database()

    session = get_session()
    try:
        eskiyen = _eskimis_kayitlari_temizle(session)
        if eskiyen:
            print(
                f"[init_db] v1 öncesi {eskiyen} kayıt silindi "
                "(eski veri setinin hastalıkları bugünkü bilgi tabanında yok)."
            )

        mevcut = (
            session.query(Symptom)
            .filter(Symptom.kaynak.in_([KAYNAK_SEED, KAYNAK_SENTETIK]))
            .count()
        )
        if mevcut:
            if not sessiz:
                print(f"[init_db] Zaten {mevcut} seed kaydı var, ekleme yapılmadı.")
                print("[init_db] Sıfırdan yüklemek için: python init_db.py --reset")
            return

        oneriler = oneriler_yukle()
        satirlar = egitim_satirlari()
        eksik = {r["hastalik_id"] for r in satirlar} - set(oneriler)
        if eksik:
            raise SystemExit(f"[init_db] HATA: öneri metni tanımsız hastalık(lar): {eksik}")

        kayitlar = []
        for r in satirlar:
            bilgi = oneriler[r["hastalik_id"]]
            kayitlar.append(
                Symptom(
                    tur=r["tur"],
                    semptom=r["metin"].strip(),
                    hastalik=bilgi["hastalik_adi"],
                    hastalik_id=r["hastalik_id"],
                    oneri=bilgi["oneri_metni"],
                    aciliyet=r["aciliyet_etkin"] or bilgi["aciliyet"],
                    kaynak=KAYNAK_ESLEME.get(r["kaynak_tipi"], KAYNAK_SENTETIK),
                    guven=1.0,
                )
            )
        session.add_all(kayitlar)
        session.commit()

        el = sum(1 for k in kayitlar if k.kaynak == KAYNAK_SEED)
        print(f"[init_db] {len(kayitlar)} eğitim örneği yüklendi ({el} el yazımı, {len(kayitlar) - el} üretilmiş).")
        print(f"[init_db] {len({k.hastalik for k in kayitlar})} farklı hastalık sınıfı tanımlı.")
        print("[init_db] val ve dış test satırları bilinçli olarak yüklenmedi (ölçüm için).")
    finally:
        session.close()


if __name__ == "__main__":
    utf8_cikti_ayarla()
    parser = argparse.ArgumentParser(description="VetAI veritabanı kurulumu")
    parser.add_argument("--reset", action="store_true", help="Tabloyu sıfırla ve baştan yükle")
    args = parser.parse_args()
    seed(reset=args.reset)
