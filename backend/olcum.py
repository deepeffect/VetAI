"""Veri seti v1 üzerinde uçtan uca ölçüm (guardrail + ML + aciliyet).

Eğitime girmeyen iki kümeyi kullanır:
  * val      : data/vetai_sentetik_sikayetler_v1.csv içinde bolum == "val" (550)
  * dış test : data/vetai_dis_test_seti_v1.csv (110, şablon dışı el yazımı)

Modeli veritabanındaki güncel veriyle eğitir (init_db.py çalıştırılmış olmalı),
sonra her cümle için projenin GERÇEK yolunu (kokler guardrail -> tür filtresi ->
ML -> aciliyet birleştirme) uygular ve tablo basar.

Kullanim:
    python olcum.py            # tüm ölçümler
    python olcum.py --hizli    # yalnızca ML doğruluğu
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import logging
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.disable(logging.WARNING)

import ml_model  # noqa: E402
from bilgi import acil_kaliplar, kokler  # noqa: E402

VERI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SEVIYE = {"yesil": 0, "turuncu": 1, "kirmizi": 2}


def oku(ad: str) -> list[dict]:
    with open(os.path.join(VERI, ad), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def olc(kume: list[dict], ad: str, id_ad: dict[str, str], hizli: bool) -> None:
    n = len(kume)
    top1 = top3 = kararsiz = kararsiz_dogru = tahmin_yok = guard_gecti = 0
    acil_ok = acil_n = acil_fp = yesil_n = 0
    aciliyet_dogru = aciliyet_n = 0

    for r in kume:
        hedef = r.get("hastalik_adi") or id_ad[r["hastalik_id"]]
        metin, tur = r["metin"], r["tur"]

        if not hizli:
            karar, _, _ = kokler.guardrail(metin)
            guard_gecti += karar == "devam"

        tahminler = ml_model.tahmin_et(metin, top_k=3, tur=tur)
        if not tahminler:
            tahmin_yok += 1
            continue
        dogru = tahminler[0].hastalik == hedef
        top1 += dogru
        top3 += hedef in [t.hastalik for t in tahminler]
        k = ml_model.kararsiz_mi(tahminler)
        kararsiz += k
        kararsiz_dogru += k and dogru

        if not hizli and "aciliyet_etkin" in r:
            seviye, _ = acil_kaliplar.aciliyet_tespit(metin, tahminler[0].aciliyet or None)
            aciliyet_n += 1
            aciliyet_dogru += seviye == r["aciliyet_etkin"]
            if r["aciliyet_etkin"] == "kirmizi":
                acil_n += 1
                acil_ok += seviye == "kirmizi"
            if r["aciliyet_etkin"] == "yesil":
                yesil_n += 1
                acil_fp += seviye == "kirmizi"

    print(f"\n== {ad} (n={n}) ==")
    print(f"  top-1 doğruluk      : {top1 / n:.3f}")
    print(f"  top-3 doğruluk      : {top3 / n:.3f}")
    print(f"  tahmin üretilemeyen : {tahmin_yok}")
    print(f"  kararsız bayrağı    : {kararsiz / n:.2f}  (doğru tahminlerin {kararsiz_dogru / max(top1, 1):.2f}'i)")
    if not hizli:
        print(f"  guardrail 'devam'   : {guard_gecti / n:.3f}")
        if aciliyet_n:
            print(f"  aciliyet (3 sınıf)  : {aciliyet_dogru / aciliyet_n:.3f}")
            print(f"  kırmızı yakalama    : {acil_ok}/{acil_n}   yeşil→kırmızı yanlış: {acil_fp}/{yesil_n}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hizli", action="store_true")
    a = ap.parse_args()

    durum = ml_model.egit(cv_arka_planda=False)
    if not durum.egitildi:
        raise SystemExit("Model eğitilemedi; önce: python init_db.py --reset")
    print(f"Model: {durum.ornek_sayisi} örnek, {durum.sinif_sayisi} sınıf, "
          f"{durum.ozellik_sayisi} özellik, çapraz doğrulama={durum.dogruluk}")

    with open(os.path.join(VERI, "oneriler.json"), encoding="utf-8") as f:
        id_ad = {k: v["hastalik_adi"] for k, v in json.load(f).items()}

    tum = oku("vetai_sentetik_sikayetler_v1.csv")
    val = [r for r in tum if r["bolum"] == "val"]
    olc(val, "val (üretilmiş + el yazımı)", id_ad, a.hizli)
    olc([r for r in val if r["kaynak_tipi"] == "el_yazimi"], "val — yalnızca el yazımı", id_ad, a.hizli)
    olc(oku("vetai_dis_test_seti_v1.csv"), "dış test (şablon dışı)", id_ad, a.hizli)

    if not a.hizli:
        alakasiz = [
            "Kedime hangi mamayı almalıyım?", "Köpeğimin adı ne olsun?", "Merhaba",
            "2+2 kaç eder", "Randevu almak istiyorum", "Kısırlaştırma kaç yaşında yapılır",
            "TEKNOFEST kriterlerini açıkla", "İkinci maddeyi detaylandır",
        ]
        c = collections.Counter(kokler.guardrail(m)[0] for m in alakasiz)
        print(f"\n== alakasız {len(alakasiz)} cümle == {dict(c)}")


if __name__ == "__main__":
    main()
