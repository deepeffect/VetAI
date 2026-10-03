"""Anlam ayrımı, halk dili ve anlam katmanı testleri (Gemini çağırmaz, kota harcamaz).

Kontrol edilenler:
  1. Anlam ayrımı + kök tabanlı guardrail: yanıltıcı kelimeler yanlış belirti
     kodu üretmiyor ("sıcak çarptı" -> TRAVMA değil, "nöbetçi" -> NÖBET değil ...).
  2. Aciliyet bayrakları: "sıcak çarptı", "elektrik çarptı", "ilacımı yuttu" kırmızı;
     olumsuz cümle ("sıcak çarpmadı") bayrak üretmiyor.
  3. Halk dili veri dosyası: her hastalık için en az 20 tarif, tür tutarlılığı,
     anlam testi setiyle çakışma yok.
  4. ML (veritabanındaki güncel veriyle eğitilir): tuzak cümlelerde doğru ilk sıra.
  5. Anlam katmanı birleştirme matematiği ve Gemini yanıt doğrulaması.
  6. Uçtan uca analiz zinciri, Gemini SAHTE bir yanıtla taklit edilerek
     (veritabanına yazmaz).
Sonda anlam testi setinde (data/vetai_anlam_testi_v1.csv) yalnızca ML'in
başarısı raporlanır; Gemini'li ölçüm için: python olcum.py --anlam 20

Kullanım:
    python anlam_testi.py
"""

from __future__ import annotations

import collections
import csv
import json
import logging
import os
import sys

from konsol import utf8_cikti_ayarla

utf8_cikti_ayarla()
logging.disable(logging.WARNING)

import numpy as np  # noqa: E402

import anlam_katmani  # noqa: E402
import gemini_api  # noqa: E402
import ml_model  # noqa: E402
from bilgi import acil_kaliplar, kokler  # noqa: E402

VERI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class Sonuc:
    def __init__(self) -> None:
        self.gecen = 0
        self.kalan = 0

    def dogrula(self, ad: str, kosul: bool, ayrinti: str = "") -> None:
        if kosul:
            self.gecen += 1
            print(f"  [GEÇTİ] {ad}")
        else:
            self.kalan += 1
            print(f"  [KALDI] {ad} {ayrinti}".rstrip())


def kodlar(metin: str) -> set[str]:
    belirti, baglam = kokler.belirti_bul_gevsek(metin)
    return set(belirti) | set(baglam)


# (metin, olması gereken kodlar, olmaması gereken kodlar)
KOD_TESTLERI = [
    ("Köpeğime sıcak çarptı", {"SICAK_TEMAS"}, {"TRAVMA"}),
    ("Kedime güneş çarptı galiba, yerde yatıyor", {"SICAK_TEMAS"}, {"TRAVMA"}),
    ("Köpeğimin başına güneş vurdu, sendeliyor", {"SICAK_TEMAS"}, {"TRAVMA"}),
    ("Köpeğime sıcak çarpmadı ama halsiz", {"HALSIZLIK"}, {"SICAK_TEMAS", "TRAVMA"}),
    ("Köpeğime araba çarptı", {"TRAVMA"}, set()),
    ("Kedim 3. kattan düştü", {"TRAVMA"}, set()),
    ("Kedimin kalbi çok hızlı çarpıyor", {"KALP_CARPINTI"}, {"TRAVMA"}),
    ("Kusura bakmayın, köpeğimin kulağı kokuyor", set(), {"KUSMA"}),
    ("Köpeğim kazara ilacımı yuttu", {"ZEHIR_TEMAS"}, {"TRAVMA"}),
    ("Nöbetçi veteriner var mı, kedim kusuyor", {"KUSMA"}, {"NOBET"}),
    ("Kedimin iştahı düşmüş", {"ISTAHSIZLIK"}, {"TRAVMA"}),
    ("Kedimin ateşi düştü ama halsiz", {"HALSIZLIK"}, {"ATES", "TRAVMA"}),
    ("Kurt köpeğim öksürüyor", {"OKSURUK"}, {"KURT_GORUNTU"}),
    ("Kedim kahve telvesi gibi kustu", {"KAN_KUSMA"}, {"KULAK_SIYAH_KIR"}),
    ("Kedimin kulağında kahve telvesi gibi kir var", {"KULAK_SIYAH_KIR"}, set()),
    ("Köpeğimin nefesi kötü kokuyor", {"AGIZ_KOKUSU"}, {"NEFES_DARLIGI"}),
    ("Kedim soğuk algınlığı geçirdi", {"NEZLE"}, {"USUME"}),
    ("Köpeğim öksürüyor, sonunda da öğürüyor", {"OKSURUK"}, {"KUSMA"}),
    ("Köpeğim titreyerek yere düştü ve kasıldı", {"NOBET"}, {"TRAVMA"}),
    ("Köpeğim elektrik çarpmış gibi titredi", {"TITREME"}, {"TRAVMA"}),
    ("Köpeğimi elektrik çarptı", {"TRAVMA"}, set()),
    ("Köpeğimi bahçede böcek ısırdı, yüzü şişti", {"ARI_SOKMA", "YUZ_SIS"}, {"ISIRIK_YARASI"}),
    ("Kedimi pire ısırdı", {"PIRE_GORUNTU"}, {"ISIRIK_YARASI"}),
    ("Köpeğimi büyük bir köpek ısırdı", {"ISIRIK_YARASI"}, set()),
    ("Kedim öksürük nöbetine giriyor", {"OKSURUK"}, {"NOBET"}),
    ("Kedimin astım krizi tuttu", {"NEFES_DARLIGI"}, {"NOBET"}),
    ("Yaşlı köpeğim duvarlara çarpıyor", {"DENGE"}, {"TRAVMA"}),
    ("Köpeğimin boğazına kemik sıkıştı", {"YABANCI_CISIM"}, {"TRAVMA"}),
    ("Erkek kedim sancılanıyor, çiş yapamıyor", {"IDRAR_YAPAMAMA"}, {"DOGUM_UZUN"}),
    ("Kedimin doğum günüydü, iki kez kustu", {"KUSMA"}, {"DOGUM_UZUN"}),
    ("Kedimin gözü ağlıyor gibi sulanıyor", {"GOZ_AKINTISI"}, {"AGRI"}),
    ("Bir kaşık yoğurt verdim, kedim kusuyor", {"KUSMA"}, {"KOLTUK_ALTI_KIZARIK"}),
    ("Köpeğim kah kuh yapıyor", {"OKSURUK"}, set()),
    ("Köpeğim göğsü hırıl hırıl", {"HIRILTI"}, set()),
    ("Köpeğim kızak çekiyor", {"POPO_SURTME"}, set()),
    ("Kedim idrarını yapamıyor", {"IDRAR_YAPAMAMA"}, set()),
    ("Köpeğimin kusması geçti ama ishali var", {"ISHAL"}, {"KUSMA"}),
    ("Kedim ağzına bir şey koymuyor", {"ISTAHSIZLIK"}, set()),
]

# (metin, beklenen seviye, olması gereken bayrak kodu | None, olmaması gereken bayrak kodu | None)
ACIL_TESTLERI = [
    ("Köpeğime sıcak çarptı", "kirmizi", "SICAK_CARPMASI", None),
    ("Köpeğimi elektrik çarptı", "kirmizi", "ELEKTRIK", None),
    ("Köpeğim kazara ilacımı yuttu", "kirmizi", "ZEHIR_TEMAS", None),
    ("Köpeğime sıcak çarpmadı ama biraz halsiz", None, None, "SICAK_CARPMASI"),
    ("Kedimin kalbi çok hızlı çarpıyor", None, None, "TRAVMA"),
    # Hastalık adı geçen bilgi sorusu acil bayrağı üretmez
    ("Sıcak çarpması belirtileri nelerdir?", "yesil", None, "SICAK_CARPMASI"),
    ("Elektrik çarpması olursa ne yapmalı?", "yesil", None, "ELEKTRIK"),
]

# (metin, beklenen guardrail kararı): bilgi sorusu kapsam dışı kalır, hayvanlı anlatım devam eder
GUARDRAIL_TESTLERI = [
    ("Sıcak çarpması belirtileri nelerdir?", "kapsam_disi"),
    ("Araba çarpması sonrası ne yapılır?", "kapsam_disi"),
    ("Köpeğimde sıcak çarpması var gibi", "devam"),
    ("Köpeğime sıcak çarptı", "devam"),
]

# (metin, tür, beklenen ilk tahmin id, ilk sırada OLMAMASI gereken id)
ML_TESTLERI = [
    ("Köpeğime sıcak çarptı", "kopek", "sicak_carpmasi", "travma"),
    ("Köpeğe güneş geçti sanırım, çok halsiz", "kopek", "sicak_carpmasi", "travma"),
    ("Köpeğime araba çarptı", "kopek", "travma", None),
    ("Kedim soğuk algınlığı geçiriyor, hapşırıyor", "kedi", "kedi_nezlesi", None),
    ("Köpeğimin nefesi çok kötü kokuyor", "kopek", "dis_hastaligi", None),
    ("Kedimi pire ısırdı, kaşınıyor", "kedi", "pire", None),
    ("Köpeğim kah kuh yapıyor, sonunda öğürüyor, pansiyondan geldi", "kopek", "kulube_oksurugu", None),
    ("Köpeğim kızak çekiyor, poposu balık gibi kokuyor", "kopek", "anal_kese", None),
]


def test_kodlar(s: Sonuc) -> None:
    print("\n== 1. Anlam ayrımı + kök tabanlı bulgular ==")
    for metin, olmali, olmamali in KOD_TESTLERI:
        k = kodlar(metin)
        eksik, fazla = olmali - k, olmamali & k
        s.dogrula(metin, not eksik and not fazla, f"eksik={sorted(eksik)} fazla={sorted(fazla)} bulunan={sorted(k)}")


def test_aciliyet(s: Sonuc) -> None:
    print("\n== 2. Aciliyet bayrakları ==")
    for metin, seviye, olmali, olmamali in ACIL_TESTLERI:
        sev, bayraklar = acil_kaliplar.aciliyet_tespit(metin)
        kodlar_ = {k for k, _ in bayraklar}
        ok = (seviye is None or sev == seviye) and (olmali is None or olmali in kodlar_) and (
            olmamali is None or olmamali not in kodlar_
        )
        s.dogrula(f"{metin} -> {sev} {sorted(kodlar_)}", ok)
    for metin, beklenen in GUARDRAIL_TESTLERI:
        karar = kokler.guardrail(metin)[0]
        s.dogrula(f"guardrail: {metin} -> {karar}", karar == beklenen, f"beklenen={beklenen}")


def test_veri(s: Sonuc) -> None:
    print("\n== 3. Halk dili veri dosyaları ==")
    with open(os.path.join(VERI, "vetai_bilgi_tabani.json"), encoding="utf-8") as f:
        kb = {h["id"]: h for h in json.load(f)["hastaliklar"]}
    with open(os.path.join(VERI, "vetai_halk_dili_tanimlari_v1.csv"), encoding="utf-8") as f:
        tanimlar = list(csv.DictReader(f))
    with open(os.path.join(VERI, "vetai_anlam_testi_v1.csv"), encoding="utf-8") as f:
        test = list(csv.DictReader(f))
    sayac = collections.Counter(r["hastalik_id"] for r in tanimlar)
    az = {h: sayac[h] for h in kb if sayac[h] < 20}
    s.dogrula(f"55 hastalığın hepsinde en az 20 tarif (en az {min(sayac.values())})", not az, str(az))
    tur_hatasi = [
        r["metin"] for r in tanimlar + test
        if kb[r["hastalik_id"]]["tur"] in ("kedi", "kopek") and r["tur"] != kb[r["hastalik_id"]]["tur"]
    ]
    s.dogrula("tür tutarlılığı (yalnız kedi / yalnız köpek hastalıkları)", not tur_hatasi, str(tur_hatasi[:3]))
    egitim = {r["metin"].strip().lower() for r in tanimlar}
    cakisan = [r["metin"] for r in test if r["metin"].strip().lower() in egitim]
    s.dogrula("anlam testi seti eğitim tarifleriyle çakışmıyor", not cakisan, str(cakisan[:3]))
    s.dogrula(f"anlam testi seti: {len(test)} cümle", len(test) >= 100)


def test_ml(s: Sonuc) -> None:
    print("\n== 4. ML (veritabanındaki güncel veriyle) ==")
    for metin, tur, beklenen, yasak in ML_TESTLERI:
        t = ml_model.tahmin_et(metin, top_k=3, tur=tur)
        ilk = t[0].hastalik_id if t else ""
        s.dogrula(
            f"{metin} -> {ilk} (%{t[0].olasilik * 100:.0f})" if t else f"{metin} -> tahmin yok",
            ilk == beklenen and ilk != yasak,
            f"beklenen={beklenen}",
        )


def test_birlestirme(s: Sonuc) -> None:
    print("\n== 5. Anlam katmanı birleştirme ve doğrulama ==")
    idler = ["travma", "apse", "sicak_carpmasi", "diger"]
    p = np.array([0.12, 0.085, 0.046, 0.749])
    son = anlam_katmani.birlestir(p, idler, [anlam_katmani.Aday("sicak_carpmasi", 90)])
    s.dogrula(f"yüksek uyumlu aday ilk sıraya çıkar ({son[2]:.2f})", int(np.argmax(son)) == 2 and son[2] > 0.5)
    s.dogrula("toplam olasılık 1", abs(son.sum() - 1) < 1e-9)
    bos = anlam_katmani.birlestir(p, idler, [])
    s.dogrula("aday yoksa ML dağılımı değişmez", np.allclose(bos, p))
    dusuk = anlam_katmani.birlestir(p, idler, [anlam_katmani.Aday("apse", 5)])
    s.dogrula("düşük uyumda sıralamayı ML belirler", int(np.argmax(dusuk)) == 3)
    elenmis = anlam_katmani.birlestir(np.array([0.5, 0.0, 0.5]), ["a", "b", "c"], [anlam_katmani.Aday("b", 95)])
    s.dogrula("tür filtresinin elediği sınıf geri gelmez", elenmis[1] == 0.0)

    ham = {
        "saglik_sikayeti": True,
        "ozet": "Sıcak çarpması",
        "belirtiler": ["SICAK_TEMAS", "UYDURMA_KOD"],
        "adaylar": [
            {"hastalik_id": "sicak_carpmasi", "uyum": 140, "gerekce": "sıcak çarptı"},
            {"hastalik_id": "uydurma_hastalik", "uyum": 50, "gerekce": ""},
            {"hastalik_id": "panlokopeni", "uyum": 30, "gerekce": "yalnız kedide görülür"},
        ],
        "anlam_notu": "",
    }
    d = anlam_katmani._dogrula(ham, "kopek", "test")
    s.dogrula("bilinmeyen kod / hastalık elenir", d.belirtiler == ["SICAK_TEMAS"] and
              [a.hastalik_id for a in d.adaylar] == ["sicak_carpmasi"])
    s.dogrula("uyum 0-100 aralığına kırpılır", d.adaylar[0].uyum == 100)


def test_uctan_uca(s: Sonuc) -> None:
    """Gemini'yi sahte yanıtla taklit edip analiz zincirini çalıştırır."""
    print("\n== 6. Uçtan uca analiz (sahte Gemini) ==")
    import main
    from database import get_session
    from fastapi import BackgroundTasks

    def sahte_uret(istem, **_):
        if "sıcak çarptı" in istem:
            veri = {
                "saglik_sikayeti": True,
                "ozet": "Köpekte sıcak çarpması şüphesi.",
                "belirtiler": ["SICAK_TEMAS"],
                "adaylar": [{"hastalik_id": "sicak_carpmasi", "uyum": 92, "gerekce": "Sıcak çarpması anlatılıyor"},
                            {"hastalik_id": "travma", "uyum": 3, "gerekce": "Araç kazası anlatılmıyor"}],
                "anlam_notu": "'Çarptı' burada sıcak çarpması anlamında, araç kazası değil.",
            }
        elif "kah kuh" in istem:
            veri = {
                "saglik_sikayeti": True,
                "ozet": "Köpekte öksürük.",
                "belirtiler": ["OKSURUK"],
                "adaylar": [{"hastalik_id": "kulube_oksurugu", "uyum": 80, "gerekce": "kah kuh öksürük"}],
                "anlam_notu": "",
            }
        else:
            veri = {"saglik_sikayeti": False, "ozet": "", "belirtiler": [], "adaylar": [], "anlam_notu": ""}
        return veri, gemini_api.GeminiYanit(json.dumps(veri), "sahte-model", True)

    eski = (anlam_katmani.etkin_mi, gemini_api.yapilandirilmis_uret, main._ogren)
    anlam_katmani.etkin_mi = lambda: True
    gemini_api.yapilandirilmis_uret = sahte_uret
    main._ogren = lambda *a, **k: False  # veritabanına yazma
    anlam_katmani._onbellek.clear()
    db = get_session()
    try:
        r = main._analizi_calistir("Köpeğime sıcak çarptı", None, db, BackgroundTasks(), gemini_yorumu=False)
        ilk = r.tahminler[0].hastalik if r.tahminler else ""
        s.dogrula(f"'Köpeğime sıcak çarptı' -> {ilk}", ilk.startswith("Sıcak çarpması"))
        s.dogrula("rozetlerde 'Travma öyküsü' yok", "Travma öyküsü" not in r.bulgular, str(r.bulgular))
        s.dogrula(f"acil gerekçesi: {r.acil_gerekce}", r.acil and "Sıcak çarpması" in r.acil_gerekce)
        s.dogrula("anlam alanları dolu", r.anlam_aktif and bool(r.anlam_notu))

        r = main._analizi_calistir("Köpeğim kah kuh yapıyor", None, db, BackgroundTasks(), gemini_yorumu=False)
        ilk = r.tahminler[0].hastalik if r.tahminler else ""
        s.dogrula(f"'Köpeğim kah kuh yapıyor' -> {ilk}", ilk.startswith("Kulübe öksürüğü"))

        r = main._analizi_calistir(
            "Kedime hangi mamayı almalıyım, köpeğimle aynı mama olur mu?", None, db, BackgroundTasks(),
            gemini_yorumu=False,
        )
        s.dogrula(f"şikâyet olmayan soru analiz kartı üretmez ({r.durum})", not r.tahminler)
    finally:
        db.close()
        anlam_katmani.etkin_mi, gemini_api.yapilandirilmis_uret, main._ogren = eski
        anlam_katmani._onbellek.clear()


def rapor_anlam_seti() -> None:
    print("\n== Rapor: anlam testi setinde yalnızca ML (Gemini'siz) ==")
    with open(os.path.join(VERI, "vetai_anlam_testi_v1.csv"), encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))
    for tip in ("halk_dili", "tuzak"):
        kume = [r for r in satirlar if r["tip"] == tip]
        top1 = top3 = 0
        for r in kume:
            t = ml_model.tahmin_et(r["metin"], top_k=3, tur=r["tur"])
            ids = [x.hastalik_id for x in t]
            top1 += bool(ids) and ids[0] == r["hastalik_id"]
            top3 += r["hastalik_id"] in ids
        print(f"  {tip:10} n={len(kume):3}  top-1={top1 / len(kume):.3f}  top-3={top3 / len(kume):.3f}")


def main_() -> int:
    s = Sonuc()
    test_kodlar(s)
    test_aciliyet(s)
    test_veri(s)
    durum = ml_model.egit(cv_arka_planda=True)
    print(f"\n(ML eğitildi: {durum.ornek_sayisi} örnek, {durum.sinif_sayisi} sınıf, "
          f"{durum.ozellik_sayisi} özellik)")
    test_ml(s)
    test_birlestirme(s)
    test_uctan_uca(s)
    rapor_anlam_seti()
    print(f"\nSonuç: {s.gecen} geçti, {s.kalan} kaldı.")
    return 1 if s.kalan else 0


if __name__ == "__main__":
    sys.exit(main_())
