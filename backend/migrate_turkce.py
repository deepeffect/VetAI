"""Mevcut veritabanındaki metinleri düzgün Türkçe'ye taşır (tek seferlik bakım aracı).

Proje ilk sürümünde hastalık adları ve öneri metinleri Türkçe karakter
kullanmadan ("Dis Parazit Enfestasyonu" gibi) yazılmıştı. Bu adlar arayüzde
doğrudan gösterildiği için düzeltildi; ancak `init_db.py` yalnızca boş bir
veritabanını doldurur, var olan kayıtlara dokunmaz.

Bu betik, elde duran veritabanındaki kayıtları yeni yazımla günceller:

    python migrate_turkce.py

Yaptığı tek şey UPDATE'tir; hiçbir kayıt silinmez, canlı öğrenme ile eklenmiş
satırlar (kaynak='auto' / 'pending') korunur. Birden fazla kez çalıştırmak
güvenlidir, ikinci çalıştırmada değişecek kayıt bulunmaz.

Not: hastalık adı aynı zamanda modelin etiketi olduğu için, betikten sonra
backend yeniden başlatılmalı (ya da POST /api/retrain çağrılmalı); model
böylece yeni etiketlerle yeniden eğitilir.
"""

from __future__ import annotations

from database import Symptom, get_session, init_database
from init_db import ONERILER

# Eski yazım -> yeni yazım. Türkçe karakter gerektirmeyen adlar listede yok.
ESKI_YENI_ADLAR: dict[str, str] = {
    "Ust Solunum Yolu Enfeksiyonu": "Üst Solunum Yolu Enfeksiyonu",
    "Dis Parazit Enfestasyonu": "Dış Parazit Enfestasyonu",
    "Idrar Yolu Tikanikligi (FLUTD)": "İdrar Yolu Tıkanıklığı (FLUTD)",
    "Dis Eti Iltihabi (Gingivitis)": "Diş Eti İltihabı (Gingivitis)",
    "Kronik Bobrek Yetmezligi": "Kronik Böbrek Yetmezliği",
    "Ic Parazit (Solucan)": "İç Parazit (Solucan)",
    "Eklem/Kalca Rahatsizligi": "Eklem/Kalça Rahatsızlığı",
    "Kennel Cough (Bulasici Trakeobronsit)": "Kennel Cough (Bulaşıcı Trakeobronşit)",
    "Sicak Carpmasi": "Sıcak Çarpması",
    "Kabizlik": "Kabızlık",
    "Epileptik Nobet": "Epileptik Nöbet",
    "Kene Kaynakli Enfeksiyon": "Kene Kaynaklı Enfeksiyon",
}


def migrate() -> None:
    init_database()
    session = get_session()
    try:
        # 1) Hastalık adlarını yeni yazıma çevir
        ad_sayisi = 0
        for eski, yeni in ESKI_YENI_ADLAR.items():
            ad_sayisi += (
                session.query(Symptom)
                .filter(Symptom.hastalik == eski)
                .update({Symptom.hastalik: yeni}, synchronize_session=False)
            )
        session.commit()

        # 2) Öneri metinlerini init_db.py'deki güncel sürümle eşitle
        oneri_sayisi = 0
        for ad, metin in ONERILER.items():
            oneri_sayisi += (
                session.query(Symptom)
                .filter(Symptom.hastalik == ad, Symptom.oneri != metin)
                .update({Symptom.oneri: metin}, synchronize_session=False)
            )
        session.commit()

        # 3) Sözlükte karşılığı olmayan etiket kaldıysa uyar
        bilinmeyen = {
            h
            for (h,) in session.query(Symptom.hastalik).distinct().all()
            if h not in ONERILER
        }

        print(f"[migrate] Hastalık adı güncellenen kayıt : {ad_sayisi}")
        print(f"[migrate] Öneri metni güncellenen kayıt  : {oneri_sayisi}")
        if bilinmeyen:
            print(f"[migrate] UYARI: öneri metni tanımsız etiket(ler): {sorted(bilinmeyen)}")
        print("[migrate] Bitti. Backend'i yeniden başlatın veya POST /api/retrain çağırın.")
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
