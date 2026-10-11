# Veri Seti v1 Paketi — Yapılacaklar ve Görev Dağılımı

Paket: `vetai_veri_paketi_v1_2 (1).zip` (26–27 Eylül 2026; `veri/`, `kod/`, `entegrasyon/`, `dokuman/`)
Branch: `db_random_error_fix`
Son güncelleme: 2026-10-11

Ekip: **Esat**, **Ümit**, **Asad**, **Mehmet**, **Rüzgar**. Dağılım öneridir; aynı
alandaki maddeler tek kişide toplandı ki ders ve kod birbirine karışmasın.

| Kişi | Alan | Bölüm |
|---|---|---|
| Ümit | Backend entegrasyonu, üretim betikleri, veritabanı | 1, 2 |
| Esat | Bilgi tabanı içeriği ve veteriner incelemesi | 3 |
| Asad | Ölçüm, doğrulama, model | 4 |
| Mehmet | Gerçek cümle toplama ve etiketleme | 5 |
| Rüzgar | Belgeler, lisans, arayüz tarafı | 6 |

---

## 0. Durum (11 Ekim 2026'da doğrulandı, yapılacak iş yok)

- [x] `veri/` altındaki ana dosyalar repoda birebir aynı: şikâyet CSV'si (3.025),
      dış test (110), `vetai_bilgi_tabani.json`, `oneriler.json`, `hastalik_aciliyet.json`,
      `UYARI_OKUYUN.txt`
- [x] 55 hastalık her dosyada aynı küme; öneri metni eksik hastalık yok
- [x] `README_ENTEGRASYON.md` "projeye alma sırası" 7 maddenin 7'si repoda var:
      `kokler.guardrail()`, `aciliyet_tespit()`, `init_db.py` (val ve dış test
      eğitime girmiyor), `metin_hazirla()`, tür filtresi + marj tabanlı kararsızlık
      (`ml_model.py`), `hastalik_aciliyet.json`, `olcum.py` ölçümleri README'de
- [x] Repo paketi aştı: 1.210 halk dili tarifi, anlam testi seti, `halk_dili_sozlugu.json`,
      `bilgi/anlam_ayrimi.py`; `bilgi/kokler.py` ve `bilgi/acil_kaliplar.py` paketteki
      sürümden daha yeni. **Paketin `entegrasyon/` dosyaları repo'nun üstüne kopyalanmaz.**
- [x] Üretim betikleri yeniden üretilebilirlik testi: `uret.py --hedef 55 --tohum 42`
      repodaki CSV'yi **birebir** üretiyor; `dis_test_seti.py`, `entegrasyon_uret.py`
      (`oneriler.json`, `hastalik_aciliyet.json`, `esanlam_sozlugu.py`) birebir aynı.
      Tek fark `acil_kaliplar.py`: repoda elle eklenmiş 14 satır var (anlam_ayrimi bağı)

## 1. Üretim betiklerini repoya alma — **Ümit**

Pakette olup repoda olmayan tek kritik parça. Bunlar olmadan veri büyütülemez,
hastalık eklenemez, `oneriler.json` yeniden üretilemez.

- [ ] `backend/data/uretim/` klasörü: `kod/` içindeki 7 betik (`kb.py`, `kb_belirtiler.py`,
      `kb_hastaliklar_1.py`, `kb_hastaliklar_2.py`, `uret.py`, `dis_test_seti.py`,
      `dogrula.py`) + `entegrasyon/entegrasyon_uret.py`, `esik_analizi.py`
- [ ] Çıktı yollarını repoya göre düzelt: `kb.py` `../veri/` altına yazıyor, `uret.py` ve
      `dis_test_seti.py` bulunduğu klasöre, `entegrasyon_uret.py` kendi klasörüne.
      Hepsi `backend/data/` ve `backend/bilgi/` hedeflesin
- [ ] `entegrasyon_uret.py` artık `acil_kaliplar.py` ve `esanlam_sozlugu.py`'yi
      **üretmesin** (repodaki elle eklemeler silinir); yalnızca `oneriler.json`,
      `hastalik_aciliyet.json`, `nlp_esanlam_sozlugu.json`
- [ ] Betikler `python -X utf8` ile çalıştırılmalı; `konsol.utf8_cikti_ayarla()` çağrısı ekle
      (Windows'ta `ı` ve `ş` yüzünden `UnicodeEncodeError` alıyorlar, test edildi)
- [ ] `backend/data/uretim/README.md`: "veriyi yeniden üret" komut sırası
      (`kb.py` → `uret.py --hedef 55 --tohum 42` → `dis_test_seti.py` → `entegrasyon_uret.py`
      → `python init_db.py --reset` → `python olcum.py`)
- [ ] `yukle_ornek.py` ve `tahmin_yardimci.py` alınmaz (karşılıkları `init_db.py` ve
      `ml_model.py` içinde); README'ye tek satır not

## 2. Veritabanı ve kod düzeltmeleri — **Ümit**

- [ ] `python init_db.py --reset` ile temiz kurulum (diskteki `vetai.db` 27 Eylül tarihli,
      `kaynak_id` kolonu ve halk dili satırları yok; yerinde onarım index açmıyor)
- [ ] `init_db.seed()` içindeki iki `raise SystemExit` (satır 85, 164) → `ValueError`;
      lifespan'daki `except Exception` SystemExit'i yakalamıyor, veri uyumsuzluğunda
      sunucu hiç açılmıyor
- [ ] `database.py:125` print'indeki "ş" → ASCII ya da `logger.info`
- [ ] `migrate_turkce.py` sil (`init_db.ONERILER` yok, import anında çöküyor)
- [ ] `main.py:373` öğrenme eşiği `tahmin.olasilik` yerine `tahmin.ml_olasilik`
      (None değilse); Gemini karışımı takip sorularını `auto` eğitim verisi yapıyor
- [ ] `eksik_kolonlari_tamamla`: ALTER ile eklenen `index=True` kolonlara
      `CREATE INDEX IF NOT EXISTS`

## 3. Bilgi tabanı içeriği — **Esat**

Paketin kendi uyarısı: tıbbi içerik veteriner onayından geçmedi, en kritik ve en ucuz adım bu.

- [ ] `veri/vetai_bilgi_tabani.csv` (55 satır, pakette var, repoda yok) → `backend/data/`;
      veteriner incelemesi için tablo bu
- [ ] Bir veteriner hekim ya da son sınıf öğrencisi 55 satırı gözden geçirsin:
      `kardinal_belirtiler`, `aciliyet`, `evde`, `kacin`. Düzeltmeler doğrudan
      `kb_hastaliklar_1.py` / `kb_hastaliklar_2.py` içine, sonra `kb.py` + `entegrasyon_uret.py`
- [ ] Aciliyet "abartan" tarafta tutulmuş (Bio-Vet ilkesi); veterinerin "fazla" dediği
      kırmızılar listelensin, karar ekiple verilsin
- [ ] Yeni hastalık adayları: Addison, lenfoma, kalp kurdu. Her biri için `kb_hastaliklar_2.py`
      kaydı + 6 el yazımı örnek + gerekiyorsa `kb_belirtiler.py`'ye kod. **Kuduz** sınıf
      değil, uygulama katmanında halk sağlığı uyarısı
- [ ] Kaggle alt kümesi (`animal_disease_prediction_kedi_kopek.csv`, 147 satır) ile çapraz
      kontrol: orada olup bizde olmayan hastalıklar (leptospirosis, hepatit, kalp kurdu…)
      listelensin; cümle üretiminde **kullanılmaz** (İngilizce, tablo verisi)
- [ ] Türkçe kaynaklarla `aciklama` / `evde` metinlerini zenginleştir: Türkçe Vikipedi
      (CC BY-SA), Ankara Üniv. Açık Ders VET 427 / 422 (CC BY-NC-SA); kopyalama değil özetleme

## 4. Ölçüm ve doğrulama — **Asad**

- [ ] `python dogrula.py` (paket) repodaki CSV üzerinde: tekrar, tür-kod uyumu, özne
      karışıklığı; çıktı `backend/data/uretim/README.md`'ye
- [ ] `python olcum.py` ile README tablosunu yeniden üret (3 Ekim değerleri: val 0,915;
      el yazımı 0,879; dış test 0,945); farklıysa nedenini bul
- [ ] `esik_analizi.py` (paket) ile kararsızlık eşiğini yeniden ölç: marj 0,05 / mutlak 0,15
      hâlâ en iyi mi? Sonuç `ml_model.KARARSIZLIK_MARJ` yorumuna
- [ ] `uret.py --hedef 120 --tohum 7` ile v2 deneme (~6.600 satır): val ve dış testte
      kazanç 1 puanın altındaysa alınmaz; sonuç tabloya
- [ ] Halk dili ve anlam testi aynı kaynaktan yazıldığı için iyimser; Mehmet'in gerçek
      cümleleri geldiğinde üçüncü küme olarak `olcum.py`'ye ekle
- [ ] İlerleme tablosu (aşağıda, bölüm 7) her ölçümden sonra güncellenir

## 5. Gerçek Türkçe cümle toplama — **Mehmet**

Paketin ikinci uyarısı: model gerçek kullanıcı metninde belirgin düşer; tek gerçek gösterge bu.

- [ ] Form (Google Forms): tür (kedi / köpek), sahibin kendi cümlesi ("veterinere ne
      dediniz?"), veterinerin tanısı, isteğe bağlı yaş ve ırk. Ad, telefon, konum **alınmaz**
- [ ] Hedef 150–200 cümle (çevre, kampüs, veteriner klinikleri)
- [ ] Etiketleme: tanıyı 55 `hastalik_id`'den birine eşle; tabloya girmeyenler "diger"
      listesinde (Esat'a yeni hastalık adayı olarak gider)
- [ ] `backend/data/vetai_gercek_sikayetler_v1.csv`, kolonlar `id, hastalik_id, tur, metin, not`
      (dış test setiyle aynı şema), önek `GR`; **eğitime girmez**, ölçüm için
- [ ] VetRehberi.com ve Petlebi Sosyal'e izin yazısı (akademik kullanım, atıf,
      anonimleştirme, dağıtmama). Yanıt gelmeden kazıma **yok**
- [ ] 500 cümleyi geçerse Ümit ile birlikte eğitime alma kararı (ağırlık 1,0, ayrı kaynak türü)

## 6. Belgeler, lisans, arayüz — **Rüzgar**

- [ ] `docs/` klasörü: `README_VetAI_veri_seti.md`, `dokuman/VetAI_veri_seti_arastirmasi.md`,
      `entegrasyon/README_ENTEGRASYON.md` (tarihçe olarak)
- [ ] `backend/data/LISANSLAR.md`: veri seti CC BY 4.0, Bio-Vet aciliyet kuralları CC BY 4.0
      (atıf zorunlu), Kaggle alt kümesi Apache 2.0, Vikipedi CC BY-SA. README'nin
      "Lisans ve atıf" bölümüne bağlantı
- [ ] README "Veri seti" bölümüne "nasıl yeniden üretilir" alt başlığı (Ümit'in uretim
      README'sine bağlantı) ve "sentetik başlangıç veri seti" ifadesinin tez / sunumda
      kullanılacağı notu
- [ ] `nlp_esanlam_sozlugu.json` (pakette var, repoda yok): frontend `bulguyuCoz` için
      kanonik ad kaynağı olarak kullanılabilir mi? Kullanılırsa `frontend/src/lib/turkce.ts`
      içindeki elle yazılmış `BULGU_ETIKETLERI` kaldırılır (CHATBOT_TODO 3'teki madde)
- [ ] StatusPanel ve `/api/stats`: kaynak dağılımında yeni türler (gercek, llm_etiket)
      görünsün; Ümit'in bölüm 2 işinden sonra
- [ ] Zip'i `docs/` altına **koyma** (1,8 MB, içindeki her şey ya repoda ya `uretim/`'de)

## 7. İlerleme tablosu

README'deki 3 Ekim 2026 ölçümü başlangıç çizgisi. Güncelleyen: Asad.

| Küme | n | Top-1 başlangıç | Son ölçüm | Tarih |
|---|---|---|---|---|
| val (üretilmiş + el yazımı) | 550 | 0,915 | | |
| val — yalnızca el yazımı | 165 | 0,879 | | |
| dış test (şablon dışı) | 110 | 0,945 | | |
| anlam testi — halk dili | 110 | 0,982 | | |
| **gerçek cümleler (GR, Mehmet)** | 0 | — | | |
| çapraz doğrulama (eğitim havuzu) | 3.688 | 0,820 | | |

## 8. Sıra ve bağımlılıklar

1. Ümit bölüm 1 ve 2 (betikler + temiz DB) → diğer herkesin zemini
2. Esat bölüm 3 ve Mehmet bölüm 5 paralel başlar, kodu beklemez
3. Asad bölüm 4, Ümit'in `--reset`'inden sonra
4. Rüzgar bölüm 6, lisans ve docs hemen; arayüz maddesi Ümit'ten sonra
