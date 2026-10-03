# Değişiklikler — Anlam katmanı ve halk dili tarifleri (3 Ekim 2026)

Bu belge üç isteğin nasıl karşılandığını, neyin neden değiştiğini ve sistemin
nasıl test edildiğini anlatır:

1. **"Köpeğime sıcak çarptı" cümlesinin "Travma (araç çarpması)" olarak
   sınıflandırılması** ve kelime ortaklığından doğan benzer karışıklıklar.
2. **Hastalıkların halk diliyle anlatılması:** "öksürüyor" yerine "göğsü hırıl
   hırıl", "kah kuh sesler çıkarıyor" gibi tarifler; her hastalık için en az 20
   farklı tarif.
3. **Sistemin test edilmesi** ve bu raporun yazılması.

---

## İçindekiler

1. [Sorunun kökü](#1-sorunun-kökü)
2. [Çözümün mimarisi](#2-çözümün-mimarisi)
3. [Anlam ayrımı tablosu (deterministik)](#3-anlam-ayrımı-tablosu-deterministik)
4. [Gemini anlam katmanı](#4-gemini-anlam-katmanı)
5. [Halk dili: sözlük ve hastalık başına 22 tarif](#5-halk-dili-sözlük-ve-hastalık-başına-22-tarif)
6. [Diğer düzeltmeler](#6-diğer-düzeltmeler)
7. [Arayüz](#7-arayüz)
8. [Test ve ölçüm sonuçları](#8-test-ve-ölçüm-sonuçları)
9. [Bilinen sınırlar ve dürüst notlar](#9-bilinen-sınırlar-ve-dürüst-notlar)
10. [Dosya listesi](#10-dosya-listesi)
11. [Çalıştırma ve ayarlar](#11-çalıştırma-ve-ayarlar)

---

## 1. Sorunun kökü

Ekran görüntüsündeki yanıt üç ayrı katmanın aynı hatayı yapmasından doğuyordu:

| Katman | Ne oluyordu | Neden |
|---|---|---|
| Kök tabanlı guardrail (`bilgi/kokler.py`) | "Travma öyküsü" rozeti | `TRAVMA` kodunun kök listesinde çıplak **"çarptı"** kökü vardı; "sıcak çarptı" da bu kökü içeriyor. |
| ML (TF-IDF + Logistic Regression) | İlk tahmin **Travma %12**, Sıcak çarpması %4,6 | Eğitim verisinde "çarptı" kelimesi **yalnızca** "araba / motosiklet çarptı" cümlelerinde geçiyordu; sıcak çarpması örneklerinin hiçbirinde "sıcak çarptı", "güneş çarptı" ifadesi yoktu. Model kelimeyi saydığı için "çarp" → travma öğrenmişti. |
| Aciliyet gerekçesi (`main.py`) | "Travma (araç çarpması, yüksekten düşme, ısırık) tablosu acil kabul edilir" | Metinde kırmızı bayrak yoktu; gerekçe ML'in yanlış ilk tahmininden üretildi. |

Aynı mekanizma başka cümlelerde de yanlış sonuç veriyordu. Eski sisteme karşı
yazdığım 38 tuzak cümlenin yalnızca **8'i** doğru belirti kodlarını üretiyordu.
Örnekler:

| Cümle | Eski sistemin yanlışı |
|---|---|
| Kedimin kalbi çok hızlı çarpıyor | ML: Travma |
| Kusura bakmayın, köpeğimin kulağı kokuyor | Kusma bulgusu ("kus" kökü) |
| Nöbetçi veteriner var mı, kedim kusuyor | Nöbet bulgusu |
| Köpeğim kazara ilacımı yuttu | Travma bulgusu ("kaza" kökü), ML: Yabancı cisim |
| Kedimin iştahı düşmüş | Travma bulgusu ("düşmüş" kökü) |
| Kurt köpeğim öksürüyor | Bağırsak kurdu bulgusu |
| Kedim kahve telvesi gibi kustu | Kulak kiri bulgusu, ML: **Kulak uyuzu** |
| Köpeğimin nefesi kötü kokuyor | "nefes" → nefes darlığı token'ı |
| Köpeğim titreyerek yere düştü ve kasıldı | Travma bulgusu |
| Erkek kedim sancılanıyor, çiş yapamıyor | Güç doğum bulgusu ("sancı" kökü) |
| Bir kaşık yoğurt verdim | Koltuk altı / kasık kızarıklığı ("kaşık" ≈ "kasık") |
| Köpeğim kah kuh yapıyor / kızak çekiyor | Hiçbir belirti tanınmıyordu |
| Kedim üç gündür idrarını yapamıyor (kullanıcının veritabanında kayıtlı gerçek bir sorgu) | ML: **Hipertiroidi %31** |

---

## 2. Çözümün mimarisi

İstek "kelimeye değil anlama bakılsın, kelimeyi LLM incelesin" idi. Bunu tek bir
LLM çağrısına bağlamak, Gemini kapalıyken ya da kota dolduğunda eski hataya geri
dönmek demekti. Bu yüzden çözüm iki katmanlıdır:

```
Kullanıcı mesajı
  → 1. Anlam ayrımı tablosu (deterministik, her zaman çalışır)      bilgi/anlam_ayrimi.py
        "sıcak çarptı" → sicak_carpmasi   "araba çarptı" → travma_oykusu
        "kusura bakmayın" → (silinir)     "iştahı düştü" → istahsizlik
        → kök tabanlı guardrail, aciliyet ve ML aynı çözümü kullanır
  → 2. ML olasılık dağılımı (55 sınıf, tür filtresi)                 ml_model.py
  → 3. Gemini anlam katmanı (Gemini açıksa)                          anlam_katmani.py
        şikâyeti anlamca okur, KAPALI hastalık listesinden aday seçer
        nihai = 0,7 × anlam + 0,3 × ML
  → 4. Aciliyet birleştirme, sohbet yanıtı (anlam notu bağlama eklenir)
```

**Görev dağılımı:** Gemini yeni hastalık uyduramaz. Hastalık kimlikleri ve
belirti kodları JSON şemasında `enum` ile sınırlıdır, türe uymayan adaylar
sunucuda elenir ve sonuç ML dağılımıyla harmanlanır. Gemini emin değilse
(düşük uyum puanı) sıralamayı ML belirler.

---

## 3. Anlam ayrımı tablosu (deterministik)

Yeni modül: `backend/bilgi/anlam_ayrimi.py`. Her kalıp şunları taşır: ML'e
gidecek kanonik karşılık, kök tabanlı guardrail'e eklenecek kodlar, gerekiyorsa
aciliyet bayrağı ve Gemini istemine eklenen bir açıklama. Eşleşen aralık kök
taramasından önce **maskelenir**; böylece "sıcak çarptı" içindeki "çarptı"
artık Travma kökünü tetiklemez.

| Kalıp | Örnek | Sonuç |
|---|---|---|
| Sıcak çarpması (olay) | sıcak/güneş çarptı, güneş geçti, hararet bastı, sıcaktan yığıldı | `SICAK_TEMAS` + **kırmızı: Sıcak çarpması şüphesi** |
| Sıcak çarpması (ad) | "sıcak çarpması belirtileri nelerdir?" | Token; acil bayrağı **yok**, hayvan sözcüğü yoksa kapsam dışı kalır |
| Araç çarpması | araba/motor/bisiklet çarptı, ezdi, trafik kazası geçirdi | `TRAVMA` + kırmızı |
| Elektrik çarpması | elektrik çarptı / kablo ısırdı | `TRAVMA` + kırmızı (benzetme "elektrik çarpmış gibi" hariç) |
| Kalp çarpıntısı | kalbi hızlı/küt küt çarpıyor, çarpıntı | yeni kod `KALP_CARPINTI` |
| Duvarlara çarpma | duvarlara çarpıyor | `DENGE` (tek seferlik darbe değil) |
| "Düştü" deyimleri | iştahı / kilosu / ateşi / tüyü / dişi / enerjisi düştü | İştahsızlık, kilo kaybı, tüy dökülmesi …; travma değil |
| Bir yerden düşme | balkondan, 3. kattan, merdivenden düştü | `TRAVMA` |
| Nöbette yere düşme | kasılıp yere düştü | Travma sayılmaz (yalnız nöbet bağlamında) |
| Eş sesli / deyim | kusura bakmayın, kazara, nöbetçi, doğum günü, kurt köpeği, kuş yakaladı, zehir gibi zeki | Yanlış kod üretmez |
| Kahve telvesi | gibi kustu / gibi kaka / yemiş | Kanlı kusma / siyah dışkı / kafein zehirlenmesi; kulak kiri değil |
| İlaç / zehir yutma | ilacımı yuttu, fare zehri yemiş | `ZEHIR_TEMAS` + kırmızı; yabancı cisimden ayrı |
| Ağız / göz | nefesi kokuyor, gözü ağlıyor, ağzı sulanıyor | Ağız kokusu, göz akıntısı, salya |
| Solunum | öksürüp öğürüyor, öksürük nöbeti, astım krizi, soğuk algınlığı / üşüttü | Öksürük (kusma değil), solunum atağı (epilepsi değil), yeni kod `NEZLE` |
| Isırık / sokma | arı/böcek soktu, pire/kene ısırdı | Alerji / parazit; kavga ısırığı değil |
| Diğer | araba tuttu, arabada kaldı, boğazına kemik sıkıştı, karnı taş gibi, kulak uyuzu | Kusma, sıcak öyküsü, yabancı cisim, karın şişliği/ağrısı, kulak uyuzu |

Kalıplar olumsuzluğu tanır: "sıcak **çarpmadı**", "iştahı **düşmedi**" kalıbı
tetiklemez.

---

## 4. Gemini anlam katmanı

Yeni modül: `backend/anlam_katmani.py`.

- **İstem:** sistem talimatında anlam kuralları (deyimler, halk dili,
  olumsuzlama, tür uyumu, istem enjeksiyonuna karşı kural), 55 hastalığın
  kataloğu (ad, tür, ana belirtiler, öykü, *halk dilinde nasıl anlatıldığı*) ve
  155 belirti kodu. Kullanıcı mesajında: tür, son iki kullanıcı mesajı (bağlam),
  kelime tabanlı bulgular, anlam ayrımı notları ve ML'in ilk 8 adayı (ipucu).
- **Çıktı (JSON şema):** `saglik_sikayeti`, `ozet`, `belirtiler[]`,
  `adaylar[{hastalik_id, uyum 0–100, gerekce}]`, `anlam_notu`.
- **Birleştirme:** `s_i = uyum_i / 100`; anlam katmanının dağıtmadığı olasılık
  ML'e göre paylaştırılır: `p_anlam = s + (1 − Σs)·p_ML`,
  `nihai = 0,7·p_anlam + 0,3·p_ML`. Tür filtresinin elediği sınıflar geri gelmez.
- **Halk dili ile belirti bulunamadığında:** Kök tabanlı guardrail hiçbir
  belirti bulamazsa ("hayvan var ama belirti yok") metin yine de anlam
  katmanına okutulur; Gemini bir şikâyet görürse analiz devam eder.
- **Şikâyet olmayan mesaj:** Gemini "sağlık şikâyeti değil" derse analiz kartı
  üretilmez, sohbet serbest yanıtlar.
- **Dayanıklılık:** Gemini kapalı / kota dolu / zaman aşımı / bozuk JSON →
  katman sessizce devre dışı kalır, sonuç ML + anlam ayrımı tablosuna dayanır.
  Kota hatasında 60 sn, kalıcı hatada (model yok, yetki) 10 dk yeni çağrı
  denenmez. Aynı metin için sonuç önbelleğe alınır (256 kayıt).
- **Sohbet yanıtı:** Gemini'nin sohbet çağrısına giden analiz bağlamına anlam
  özeti ve yanıltıcı kelime notu eklenir; yazılan yanıt düzeltilmiş tabloyla
  tutarlı olur.

`gemini_api.py` bu iş için genelleştirildi: JSON şemalı çağrı
(`yapilandirilmis_uret`), çağrı başına model ve zaman aşımı, model başına
düşünme ayarı hafızası.

---

## 5. Halk dili: sözlük ve hastalık başına 22 tarif

### 5.1 `backend/data/vetai_halk_dili_tanimlari_v1.csv` — 1.210 tarif

55 hastalığın **her biri için 22** farklı sahip anlatımı (istenen alt sınır 20).
Tarifler bilerek tıbbi terimden uzak, günlük dille yazıldı; her hastalıkta
2–3 tanesi ASCII / noktalamasız (gerçek kullanıcı yazımına benzesin diye).
Örnekler:

| Hastalık | Tarif |
|---|---|
| Kulübe öksürüğü | "Köpeğim kah kuh diye öksürüyor, sonunda öğürüyor, keyfi yerinde." |
| Kulübe öksürüğü | "Köpeğimin göğsü hırıl hırıl, kesik kesik öksürüyor, oyun oynuyor ama." |
| Sıcak çarpması | "Köpeğime sıcak çarptı galiba, dili sarkmış, hızlı hızlı soluyor ve sendeliyor." |
| Sıcak çarpması | "Kedime güneş geçti sanırım, balkonda kaldı, ağzı açık soluyor ve çok halsiz." |
| Anal kese | "Köpeğim kızak çekiyor, poposunu halıda sürtüyor, kuyruk altını yalıyor." |
| Pankreatit | "Köpeğim bayramda kavurma yedi, ertesi gün dua eder gibi ön ayaklarını uzatıp poposunu kaldırıyor, kusuyor." |
| Akut gastroenterit | "Köpeğimin midesi bozuldu galiba, dünden beri hem kusuyor hem sulu sulu yapıyor." |

Doğrulama (`anlam_testi.py`): her hastalıkta ≥ 20 tarif, "yalnız kedi / yalnız
köpek" hastalıklarında tür tutarlılığı, v1 verisiyle ve test setiyle çakışma yok.

**Veritabanına yükleme:** `init_db.py` bu dosyayı `seed` kaynağıyla (eğitim
ağırlığı 1,0) yükler. Satırlar yeni `kaynak_id` kolonuyla (`HD0001` …) izlenir;
var olan bir veritabanına yalnızca eksik satırlar eklenir. **Sunucu açılışında
otomatik çalışır**, `--reset` gerekmez. Mevcut `backend/vetai.db` bu oturumda
güncellendi: 2.475 → **3.685** eğitim satırı (kullanıcı sorgularından gelen 13
`pending` kayda dokunulmadı).

### 5.2 `backend/data/halk_dili_sozlugu.json`

| Bölüm | İçerik | Kullanan |
|---|---|---|
| `belirti_kokleri` | 681 yeni halk dili kökü ("kah kuh", "öhö", "fokur fokur", "kızak", "ağzına bir şey koymuyor", "idrarını yapam", "kemikleri sayıl" …) | `kokler.py` (guardrail, rozetler) |
| `yeni_kodlar` | `KALP_CARPINTI`, `NEZLE` | rozetler, Gemini kod listesi |
| `ml_ifadeleri` | 115 ifade → eğitim verisinin tanıdığı kanonik karşılık ("kah kuh" → öksürük, "kızak çekiyor" → poposunu yere sürtüyor) | `nlp_engine.py` (TF-IDF) |
| `hastalik_ipuclari` | 55 hastalığın halk dilinde tipik anlatımı | Gemini kataloğu |

Her yeni kök, 3.025 v1 cümlesine karşı yanlış tetikleme için tarandı; bu
taramada yakalanan üç hatalı kök düzeltildi ("uyukl" → "büyüklüğünde",
"pişik" → "yapışık", "kabuk bağla" → yanlış kod).

---

## 6. Diğer düzeltmeler

| Değişiklik | Neden |
|---|---|
| `kokler.py`: çıplak "düşmüş" / "düşerek" kökleri `TRAVMA`'dan çıkarıldı | "iştahı düşmüş", "ateşi düşmüş" travma sayılıyordu; bir yerden düşme kalıpla yakalanıyor |
| `kokler.py`: çıplak "sancı" kökü `DOGUM_UZUN`'dan çıkarıldı | "sancılanıyor" (erkek kedi, idrar) güç doğum sayılıyordu |
| `kokler.py`: ASCII eşleşmede yazım çelişkisi kontrolü | "kaşık" metni "kasık" kökünü tetikliyordu; "kasıntı" gibi eksik yazım hâlâ "kaşıntı" kabul edilir |
| `kokler.py`: olumsuzlamaya "geçti / düzeldi / iyileşti" eklendi | "kusması geçti" artık kusma bulgusu değil |
| `nlp_engine.py`: belirti fiilleri için önek eşleme | "öksürdü", "hırıldıyor", "hapşırdı", "aksırıyor", "titredi" tek kanonik token'a iner |
| `ml_model.py`: tür kelimeleri ("kedim", "köpeğime") ML özelliği değil | Tür bilgisi zaten tür token'ı ve tür filtresinde; kelime, yalnız-o-türe-ait hastalıklara yapay itme yapıyordu ("Köpeğim kusuyor" → **Parvovirüs** (kırmızı), "Kedimde kanlı ishal" → Hipertiroidi) |
| `main.py`: acil gerekçesi | Kırmızı düzey tahmin edilen hastalıktan geldiğinde gerekçe "X tablosu acil kabul edilir (bulgular: …)" olur; turuncu "Kusma" bayrağı tek başına kırmızı gerekçe gibi gösterilmez |
| `ml_model.py`: tam dağılım API'si (`dagilim`, `tahminlere_cevir`) | Anlam katmanı 55 sınıfın tamamını yeniden ağırlıklandırabilsin |

---

## 7. Arayüz

- **Anlam kontrolü kutusu** (analiz kartı): Gemini'nin şikâyeti nasıl okuduğu,
  yanıltıcı kelime notu ve kelime tabanlı model başka bir tabloyu öne
  çıkardıysa "sıralama ifadenin anlamına göre düzeltildi" bilgisi.
- **Hastalık kartı:** "Anlam kontrolünün gerekçesi" ve kelime tabanlı modelin
  kendi yüzdesi.
- **Olasılık başlığı:** "TF-IDF + Logistic Regression + anlam kontrolü".
- **Durum paneli:** "Anlam kontrolü: Aktif / Devre dışı".
- Yeni ML token'larının Türkçe etiketleri (`lib/turkce.ts`).

API alanları (geriye uyumlu, hepsi isteğe bağlı): `anlam_aktif`, `anlam_model`,
`anlam_ozeti`, `anlam_notu`, `ml_ilk_tahmin`; tahminlerde `ml_yuzde`,
`anlam_gerekcesi`; `/api/health` içinde `anlam_katmani`, `anlam_model`.

---

## 8. Test ve ölçüm sonuçları

### 8.1 `python anlam_testi.py` — 74 / 74 geçti (Gemini çağırmaz)

| Bölüm | Kontrol | Sonuç |
|---|---|---|
| Anlam ayrımı + kökler | 38 tuzak cümlede doğru / yanlış kodlar | 38 / 38 (eski sistem: **8 / 38**) |
| Aciliyet | sıcak / elektrik çarptı, ilaç yuttu kırmızı; "çarpmadı" ve bilgi soruları bayraksız | 7 / 7 |
| Guardrail | bilgi sorusu kapsam dışı, hayvanlı anlatım devam | 4 / 4 |
| Veri dosyaları | ≥ 20 tarif, tür tutarlılığı, çakışma yok | 4 / 4 |
| ML ilk tahmin | sıcak çarptı, güneş geçti, araba çarptı, soğuk algınlığı, nefesi kokuyor, pire ısırdı, kah kuh, kızak | 8 / 8 |
| Birleştirme / doğrulama | olasılık matematiği, uydurma kod/hastalık eleme, tür filtresi | 7 / 7 |
| Uçtan uca (Gemini taklit) | "Köpeğime sıcak çarptı" → Sıcak çarpması, "Travma öyküsü" rozeti yok, acil gerekçesi doğru; "kah kuh" → Kulübe öksürüğü; mama sorusu kart üretmez | 6 / 6 |

### 8.2 `python olcum.py` — önce / sonra (yalnızca ML, Gemini'siz)

| Küme | n | Önce top-1 | Sonra top-1 | Önce top-3 | Sonra top-3 |
|---|---|---|---|---|---|
| val (üretilmiş + el yazımı) | 550 | 0,885 | **0,915** | 0,973 | 0,984 |
| val — yalnızca el yazımı | 165 | 0,764 | **0,879** | 0,933 | 0,976 |
| dış test (şablon dışı) | 110 | 0,864 | **0,945** | 0,955 | 0,991 |
| anlam testi — halk dili (yeni) | 110 | 0,755 | **0,982** | 0,909 | 1,000 |
| anlam testi — tuzak cümleler (yeni) | 32 | 0,781 | **0,969** | 0,969 | 1,000 |

| Aciliyet / diğer | Önce | Sonra |
|---|---|---|
| Aciliyet doğruluğu (val, 3 sınıf) | 0,920 | 0,942 |
| Aciliyet doğruluğu (el yazımı) | 0,824 | 0,903 |
| Kırmızı yakalama (val) | 143 / 150 | 144 / 150 |
| Kırmızı yakalama (el yazımı) | 33 / 39 | 35 / 39 |
| Yeşil cümlede yanlış kırmızı | 4 / 193 | 2 / 193 |
| "Kararsız" bayrağı (val) | %17 | %8 |
| Alakasız 8 cümle kapsam dışı | 8 / 8 | 8 / 8 |

"Önce" değerleri, eski kodun eski veritabanı yedeğiyle ayrı bir git worktree'de
aynı test dosyalarına karşı çalıştırılmasıyla ölçüldü.

### 8.3 Canlı Gemini testleri (`gemini-2.5-flash`, ayrı test sunucusu)

| Mesaj | Kelime tabanlı ML | ML + anlam katmanı |
|---|---|---|
| Köpeğime sıcak çarptı | Sıcak çarpması %40 | **Sıcak çarpması %82**; not: "'Çarptı' burada sıcak çarpması anlamında, araç kazası değil."; acil gerekçesi: Sıcak çarpması şüphesi |
| Köpeğim kazara ilacımı yuttu, şimdi titriyor | Zehirlenme %93 | **Zehirlenme %98**; not: "'Kazara' kelimesi kaza/travma öyküsü anlamında değildir." |
| Kedim kahve telvesi gibi bir şey kustu, çok halsiz | **Kulak uyuzu** (yanlış) | Zehirlenme %20 / Akut gastroenterit %16 / Panlökopeni %16 (kararsız); not: kulak kiriyle ilgisi yok |
| Köpeğimin göğsü hırıl hırıl, kah kuh sesler çıkarıyor | Kulübe öksürüğü %25 | Kulübe öksürüğü %34 / Trakeal kollaps %27 / Kalp yetmezliği %21 |
| Sıcak çarpması belirtileri nelerdir? | — | Analiz kartı yok, genel bilgi yanıtı (düzeltmeden sonra; bkz. 9) |
| (1) "Öğle sıcağında uzun yürüdük." (2) "Şimdi sürekli kusuyor ve sendeliyor." | Sıcak çarpması %57 | Sıcak çarpması %65; gerekçe önceki mesajdaki sıcak öyküsünü kullandı |

Tablodaki "kelime tabanlı ML" yüzdeleri, tür kelimeleri ML özelliğinden
çıkarılmadan önceki modele aittir; son modelde Gemini'siz "Köpeğime sıcak
çarptı" **%61 Sıcak çarpması** veriyor. Anlam katmanı çağrısı 1,7–2,7 sn, sohbet
yanıtı dahil toplam 3,6–4,6 sn sürdü. Testlerde yaklaşık 11 başarılı
`gemini-2.5-flash` ve 3 `gemini-3.5-flash-lite` isteği harcandı.
Canlı testler, kullanıcının veritabanı kirlenmesin diye veritabanının bir
kopyasıyla 8010 portunda ayrı bir sunucuda yapıldı; sunucu iş bitince kapatıldı.

### 8.4 Diğer

- `python duman_testi.py` (Gemini anahtarı boş test sunucusuna karşı): **16 / 16**.
- Ön yüz: `tsc -b` ve `vite build` hatasız.
- **Yapılamayan:** Tarayıcıda görsel arayüz testi. Claude Chrome eklentisi bu
  oturumda bağlı değildi; yeni arayüz kutuları derleme ve API alanları
  düzeyinde doğrulandı, ekranda görülmedi.

---

## 9. Bilinen sınırlar ve dürüst notlar

- **Gemini istek sayısı ikiye çıktı.** Her şikâyet artık bir anlam çağrısı + bir
  sohbet çağrısı yapar. Ücretsiz katmanda `gemini-2.5-flash` **dakikada 5
  istekle** sınırlı; test sırasında 3 şikâyetten sonra `429` alındı. Kota
  dolunca sistem tasarlandığı gibi ML'e geri düştü. Ayrı bir kota havuzu için
  `GEMINI_ANLAM_MODEL=gemini-3.5-flash-lite` önerilir; bu model bu oturumda 3
  cümlede denendi ve aynı doğrulukta çalıştı (`gemini-2.5-flash-lite` yeni
  projelere kapalı, 404 döndü). Kullanıcının `.env` dosyası değiştirilmedi.
- **Test setleri iyimser.** Halk dili tarifleri ve anlam testi cümleleri aynı
  kaynak (Claude) tarafından yazıldı; üslup benzerliği nedeniyle %98 gibi
  değerler gerçek kullanıcı metnini temsil etmez. Asıl gösterge yine el
  yazımı val (%88) ve dış test (%94,5) kümeleridir; gerçek kullanıcı
  cümleleriyle ölçüm hâlâ gerekli.
- **Çapraz doğrulama düştü (0,874 → 0,820)** ama karşılaştırılamaz: eğitim
  havuzu değişti (1.210 daha çeşitli tarif eklendi) ve tür kelimeleri özellik
  olmaktan çıktı. Ayrık test kümelerinin hepsi iyileşti.
- **Tür kelimelerinin çıkarılması** sentetik val'de ~0,7 puan maliyetli
  (0,922 → 0,915); karşılığında kısa gerçekçi cümlelerde yanlış alarm azaldı.
- **Gemini'siz tahmin kaymaları:** "Kedim iki gündür kusuyor ve hiç mama
  yemiyor, çok halsiz" cümlesinin ilk sırası Akut gastroenterit'ten (%12)
  Pankreatit'e (%21) kaydı; ikisi de düşük güvenli, "kararsız" işaretli
  tahminler. `duman_testi.py`'deki
  analiz kontrolü "acil" durumunu da başarılı analiz sayacak şekilde, takip
  sorusu kontrolü Gemini kapalıyken "atlandı" diyecek şekilde güncellendi.
- **Gemini ara sıra kodu fazla özelleştiriyor:** "kah kuh" ifadesini iki
  denemede "Kaz sesi öksürük" koduna eşledi; istemde düzeltildi ama LLM
  davranışı garanti değildir. Hastalık sıralaması bu durumdan etkilenmedi.
- **Canlı öğrenme:** Anlam katmanının düzelttiği ilk tahmin, güveni ≥ 0,45 ise
  `auto` kaydı olarak (ağırlık 0,35) eğitime girer. Yani Gemini'nin düzeltmesi
  zamanla ML'e de öğretilir.
- **Tıbbi içerik veteriner hekim onayından geçmedi.** Yeni tarifler, kökler ve
  acil kalıpları (sıcak / elektrik çarpması, ilaç yutma kırmızı) genel
  veteriner bilgisine dayanır; `data/UYARI_OKUYUN.txt` uyarısı bu dosyalar
  için de geçerlidir.

---

## 10. Dosya listesi

**Yeni**

| Dosya | Açıklama |
|---|---|
| `backend/bilgi/anlam_ayrimi.py` | Deyim / eş sesli ifade ayrımı tablosu (47 kalıp) |
| `backend/anlam_katmani.py` | Gemini anlam katmanı (istem, JSON şema, doğrulama, birleştirme, önbellek) |
| `backend/anlam_testi.py` | 74 kontrollü test betiği (Gemini çağırmaz) |
| `backend/data/vetai_halk_dili_tanimlari_v1.csv` | 1.210 halk dili tarifi (55 × 22), eğitime girer |
| `backend/data/vetai_anlam_testi_v1.csv` | 142 cümlelik anlam testi seti (110 halk dili + 32 tuzak), eğitime girmez |
| `backend/data/halk_dili_sozlugu.json` | Halk dili kökleri, ML ifadeleri, yeni kodlar, hastalık ipuçları |
| `DEGISIKLIKLER.md` | Bu belge |

**Değişen**

| Dosya | Değişiklik |
|---|---|
| `backend/main.py` | Anlam katmanı entegrasyonu, yeni yanıt alanları, acil gerekçesi |
| `backend/ml_model.py` | Tam dağılım API'si, tür kelimesiz tokenizer, yeni `Tahmin` alanları |
| `backend/gemini_api.py` | JSON şemalı çağrı, model/zaman aşımı parametresi, analiz bağlamında anlam notu |
| `backend/nlp_engine.py` | Anlam ayrımı, halk dili ifadeleri, önek eşleme |
| `backend/bilgi/kokler.py` | Maskeleme, halk dili kökleri, kök düzeltmeleri, yazım çelişkisi, olumsuzlama |
| `backend/bilgi/acil_kaliplar.py` | Anlam ayrımı aciliyet bayrakları |
| `backend/database.py` | `kaynak_id` kolonu (açılışta otomatik eklenir) |
| `backend/init_db.py` | Halk dili tariflerini idempotent yükleme |
| `backend/olcum.py` | Anlam testi seti, `--anlam N` canlı ölçüm |
| `backend/duman_testi.py` | "acil" sonucu kabul, Gemini kapalıyken takip sorusu atlanır |
| `backend/.env.example` | `ANLAM_KATMANI`, `GEMINI_ANLAM_MODEL`, `ANLAM_ZAMAN_ASIMI_MS`, `ANLAM_DUSUNME` |
| `frontend/src/api.ts`, `components/AnalysisResult.tsx`, `components/DiseaseCard.tsx`, `components/StatusPanel.tsx`, `lib/turkce.ts` | Anlam kontrolü kutusu, gerekçe, durum satırı, etiketler |
| `README.md` | Mimari, veri seti, ölçümler, ortam değişkenleri |

---

## 11. Çalıştırma ve ayarlar

```powershell
cd backend
uvicorn main:app --reload        # açılışta eksik halk dili tarifleri veritabanına eklenir
python anlam_testi.py            # 74 test, Gemini harcamaz
python olcum.py                  # ölçüm, Gemini harcamaz
python olcum.py --anlam 20       # + 20 cümlede canlı anlam katmanı (20 Gemini isteği)
```

Başlangıç logunda şunu görmelisiniz:

```
ML modeli hazir: 3685 ornek, 55 sinif, ...
Gemini katmani: AKTIF
Anlam katmani: AKTIF (model=gemini-2.5-flash)
```

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `ANLAM_KATMANI` | `1` | `0` → yalnızca ML + anlam ayrımı tablosu |
| `GEMINI_ANLAM_MODEL` | (boş → `GEMINI_MODEL`) | Ayrı kota için ör. `gemini-3.5-flash-lite` |
| `ANLAM_ZAMAN_ASIMI_MS` | `15000` | Anlam çağrısı zaman aşımı |
| `ANLAM_DUSUNME` | `MINIMAL` | `LOW` daha dikkatli ama daha yavaş |
