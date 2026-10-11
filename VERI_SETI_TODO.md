# Veri Seti Yol Haritası — Açık İşler

Branch: `db_random_error_fix` (veri seti v1 + sohbet + kendini onaran veritabanı)
Son güncelleme: 2026-10-11

Kaynaklar: zip paketindeki `dokuman/VetAI_veri_seti_arastirmasi.md` ve
`entegrasyon/README_ENTEGRASYON.md` (26–27 Eylül 2026), 11 Ekim 2026 kod incelemesi.
Chatbot / Gemini maddeleri için bkz. `CHATBOT_TODO.md`.

Bölüm sırası önem sırasıdır: 0 → 1 → 2 → 3 sırayla; 4 ve 5 fırsat buldukça.

---

## 0. Ön koşullar (önce bunlar)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python init_db.py --reset        # 27 Eylül tarihli vetai.db eski şemada; temiz kurulum
python olcum.py                  # README'deki tabloyla aynı sonuçlar alınmalı
```

- [ ] Temiz veritabanı: `python init_db.py --reset` (diskteki dosyada `kaynak_id`
      kolonu ve halk dili satırları yok; açılıştaki yerinde onarım çalışıyor ama
      eski satırların `kaynak_id`'si boş kalıyor ve index açılmıyor)
- [ ] Zip'teki üretim betiklerini repoya al → `backend/data/uretim/`:
      `uret.py`, `kb.py`, `kb_belirtiler.py`, `kb_hastaliklar_1.py`,
      `kb_hastaliklar_2.py`, `dogrula.py`, `dis_test_seti.py`, `entegrasyon_uret.py`
      (kaynak: `~/Downloads/vetai_veri_paketi_v1_2 (1).zip`; repoda yoklar ve veri
      setini büyütmenin / yeni hastalık eklemenin tek yolu bunlar)
- [ ] Araştırma raporunu ve veri seti README'sini `docs/` altına koy
      (`VetAI_veri_seti_arastirmasi.md`, `README_VetAI_veri_seti.md`)
- [ ] `init_db.seed()` içindeki iki `raise SystemExit` (satır 85 ve 164) →
      `ValueError`; yalnızca `__main__` içinde `SystemExit`'e çevir
      (`main.py` lifespan'daki `except Exception` SystemExit'i yakalamıyor;
      veri uyumsuzluğunda sunucu hiç açılmıyor)
- [ ] `database.py:125` print'indeki "ş" → ASCII ya da `logger.info`
      (UTF-8 ayarı yapmamış bir betikten çağrılınca `UnicodeEncodeError`)
- [ ] `migrate_turkce.py` sil (`init_db.ONERILER` artık yok, import anında çöküyor)
- [ ] Canlı öğrenme eşiği ML güvenine dönsün: `main.py:373` `tahmin.olasilik`
      yerine `tahmin.ml_olasilik` (None değilse) kullanılsın. Gemini karışımı
      0,45 eşiğini aşıp takip sorularını `auto` eğitim verisi yapıyor; yeni veri
      setlerini bu yol kirletmesin

## 1. Boru hattı: çok veri setli yükleyici

Bugün `init_db.py` adı sabit iki dosya okuyor (`vetai_sentetik_sikayetler_v1.csv`,
`vetai_halk_dili_tanimlari_v1.csv`). Hedef: yeni set = dosyayı koy + manifeste yaz.

- [ ] `backend/data/veri_setleri.json` manifesti; her set için:
      `dosya`, `onek` (kimlik öneki: VA, HD, GR…), `kaynak` (seed / sentetik /
      gercek / llm_etiket / ceviri), `rol` (egitim / olcum), `lisans`, `aciklama`
- [ ] Ortak şema: `id, metin, tur, hastalik_id, bolum` (+ isteğe bağlı
      `aciliyet_etkin`, `not`). `hastalik_id` `oneriler.json`'da olmak zorunda;
      yoksa önce bilgi tabanına hastalık ekle (bkz. 4)
- [ ] `database.py`: `KAYNAK_GERCEK` (1,0), `KAYNAK_LLM_ETIKET` (0,5),
      `KAYNAK_CEVIRI` (0,5) sabitleri + `KAYNAK_AGIRLIK`; `ml_model._veriyi_yukle`
      ağırlığı zaten oradan okuyor, başka değişiklik gerekmez
- [ ] `init_db.py`: manifestteki `rol == egitim` setleri sırayla yükle;
      `halk_dili_yukle`'nin "kaynak_id'si olmayan satırı ekle" mantığını
      genelleştir (her set için `kaynak_id LIKE '<onek>%'`)
- [ ] `python init_db.py --sil <onek>`: bir setin tüm satırlarını geri al
- [ ] `olcum.py`: `rol == olcum` setleri otomatik ölç; tabloyu README'ye yaz
- [ ] Tekilleştirme: `kaynak_id` benzersiz; yeni satır mevcutlarla
      `token_overlap >= TEKRAR_ESIGI` ise atla ve logla (`main.py`'deki kontrol)
- [ ] `/api/stats` ve frontend StatusPanel yeni kaynak türlerini göstersin
- [ ] `eksik_kolonlari_tamamla`: ALTER ile eklenen `index=True` kolonlara
      `CREATE INDEX IF NOT EXISTS`

## 2. Gerçek Türkçe cümle toplama (en yüksek öncelik)

Projenin tek gerçek göstergesi bu. Önce ölçüm, eğitime sonra.

- [ ] Form (Google Forms / Microsoft Forms): tür (kedi / köpek), sahibin kendi
      cümlesi ("veterinere ne dediniz?"), veterinerin koyduğu tanı, isteğe bağlı
      yaş ve ırk. Ad, telefon, konum **alınmaz**
- [ ] Hedef 150–200 cümle; etiketi veteriner hekim ya da son sınıf öğrencisi
      `hastalik_id`'ye eşlesin; 55 tabloya girmeyen tanılar "diger" listesinde kalsın
- [ ] `backend/data/vetai_gercek_sikayetler_v1.csv` (önek `GR`), manifestte
      `rol: olcum`, `kaynak: gercek`
- [ ] `python olcum.py` → README tablosuna "gerçek cümle" satırı
      (beklenen top-1 yaklaşık %70; el yazımı val %88'in altında kalması normal)
- [ ] Hata analizi: yanlış tahminleri `hastalik_id` çiftlerine göre say; eksik
      halk dili ifadelerini `halk_dili_sozlugu.json` ve `bilgi/kokler.py`'ye ekle
- [ ] 500 cümleyi geçince: `bolum` train / val böl, `rol: egitim`'e al, val ve
      dış testte kazancı ölç; kazanç yoksa `olcum`'da bırak

## 3. VetRehberi / Petlebi Sosyal (yalnızca yazılı izinle)

Gerçek Türkçe sahip metninin tek büyük kaynağı: VetRehberi 10.674 veteriner
yanıtlı soru, Petlebi Sosyal ~100.000 topluluk sorusu. İkisinin de açık lisansı yok.

- [ ] İzin yazısı: akademik / tez kullanımı, atıf, anonimleştirme, ham veriyi
      dağıtmama taahhüdü. Yanıt gelmeden kazıma **yok** (site kuralları + KVKK)
- [ ] İzin gelirse: kedi / köpek kategorisi, soru + veteriner yanıtı; ad, telefon,
      e-posta, konum temizliği; izin metni `backend/data/LISANSLAR.md`'ye
- [ ] Etiketleme: Gemini'ye 55 hastalık kataloğu + soru + veteriner yanıtı →
      `hastalik_id` + güven; güven eşiği altı "etiketsiz"; veteriner %10 örnekleme
      kontrolü (`anlam_katmani.SISTEM_TALIMATI` kataloğu yeniden kullanılabilir)
- [ ] Önce `rol: olcum` (önek `VR` / `PL`); sonra `kaynak: llm_etiket` ile
      0,5 ağırlıkta eğitime al, val ve dış testte kazancı ölç
- [ ] Tezde ayrı bölüm: "gerçek sahip metniyle dış doğrulama"

## 4. Sentetik büyütme ve bilgi tabanı

- [ ] `python uret.py --hedef 120 --tohum 7 --cikti vetai_sentetik_sikayetler_v2.csv`
      (~6.600 satır); v1 ile aynı val / dış testte ölç; kazanç 1 puanın altındaysa alma
- [ ] Yeni hastalıklar: `kb_hastaliklar_2.py`'ye kayıt → `python kb.py` →
      `python entegrasyon_uret.py` → `oneriler.json`, `hastalik_aciliyet.json`,
      `vetai_bilgi_tabani.json` yeniden üretilir. Adaylar: Addison, lenfoma, kalp
      kurdu. **Kuduz** hastalık sınıfı değil, uygulama katmanında halk sağlığı uyarısı
- [ ] LLM parafraz (halk dili setinin devamı): hastalık başına 20 kısa / yazım
      hatalı / konuşma dili cümle, önek `HD2`, `kaynak: seed`;
      `vetai_anlam_testi_v1.csv` ile çakışma yok (`dogrula.py`)
- [ ] Yaygınlık öncülleri: VetCompass açık yayınlarından `yayginlik` (1–3) →
      `anlam_katmani.birlestir` / ML çıktısında çarpan (raporun 4. katmanı, yapılmadı)
- [ ] **Veteriner hekim incelemesi**: `vetai_bilgi_tabani.csv` 55 satır, özellikle
      `evde` / `kacin` metinleri ve aciliyet düzeyleri (CHATBOT_TODO 3 ile aynı madde)
- [ ] Türkçe bilgi zenginleştirme (RAG için `vetai_bilgi_tabani.json`): Türkçe
      Vikipedi hastalık kategorileri (CC BY-SA), Ankara Üniv. Açık Ders VET 427 / 422
      (CC BY-NC-SA), DergiPark olgu sunumları (CC BY-NC); kopyalama değil özetleme

## 5. İngilizce açık setler (düşük öncelik)

| Set | Lisans / erişim | Ne için | Ne için değil |
|---|---|---|---|
| Pet Health Symptoms (HF `karenwky`, 2.000 cümle, 5 sınıf) | MIT, açık | Çevirip "şikâyet mi / değil mi" guardrail testi, üslup örneği | 55 hastalık etiketi (sınıflar kaba, veri sentetik) |
| PetEVAL (HF `SAVSNET`, 17.600 klinik kayıt, 429 hastalık) | Apache 2.0, kayıt + iletişim bilgisi | ICD-11 bölüm → `sistem` eşlemesi, etiket şeması | Sahip dili (klinisyen notu), çeviri emeği yüksek |
| PetQA (Korece, gerçek sahip soruları) | CC BY-NC-ND; depo 11 Ekim 2026'da hâlâ 404 | Açılınca iç kıyas | Dağıtım ve çeviri (ND) |
| Kaggle Animal Disease Prediction (zip'te 147 satır) | Apache 2.0 | Bilgi tabanı çapraz kontrolü | Cümle üretimi (tablo verisi, İngilizce) |

- [ ] Pet Health Symptoms: 200 "Owner Observation" cümlesini çevir, `rol: olcum`,
      yalnızca guardrail "devam" oranını ölç
- [ ] PetEVAL: erişim al, ICD-11 bölümlerini `sistem` alanına eşle, 55 hastalıkla
      kesişen alt kümeyi say; değerse çevir (`kaynak: ceviri`, 0,5)
- [ ] PetQA deposunu ayda bir kontrol et

## 6. Kurallar (her set için)

- Önce `rol: olcum`, sonra eğitim. `val` (550) ve dış test (110) **asla** eğitime girmez.
- Her satırda `kaynak` + `kaynak_id` öneki; set bazında etki ölçülür, gerekirse `--sil` ile geri alınır.
- Eğitime giren her set için README'ye satır: n, top-1, top-3, kaynak, lisans.
- Lisans: CC BY / MIT / Apache → atıf ve lisans metni `backend/data/LISANSLAR.md`'de;
  NC / ND → yalnızca iç kullanım; izinsiz kazıma yok; kişisel veri anonim.
- Tez ve sunumda "sentetik (yapay) başlangıç veri seti"; gerçek cümle sayısı ayrı yazılır.

## 7. İlerleme tablosu

README'deki ölçüm tablosu (3 Ekim 2026) başlangıç çizgisi; her yeni setten sonra güncelle.

| Küme | n | Top-1 başlangıç | Son ölçüm | Tarih |
|---|---|---|---|---|
| val (üretilmiş + el yazımı) | 550 | 0,915 | | |
| val — yalnızca el yazımı | 165 | 0,879 | | |
| dış test (şablon dışı) | 110 | 0,945 | | |
| anlam testi — halk dili | 110 | 0,982 | | |
| **gerçek cümleler (GR)** | 0 | — | | |
| çapraz doğrulama (eğitim havuzu) | 3.688 | 0,820 | | |
