# 🐾 VetAI

Kedi ve köpek sahipleri için Türkçe **semptom ön değerlendirme asistanı**.
Sahibin kendi cümleleriyle yazdığı şikâyeti Türkçe NLP katmanı ayıklar, TF-IDF +
Logistic Regression modeli 55 hastalık tablosu arasında olasılık dağılımı
çıkarır, Gemini **anlam katmanı** şikâyeti anlamca okuyup kelime ortaklığından
doğan yanlışları düzeltir ("sıcak çarptı" araç çarpması değildir), aciliyet
katmanı kırmızı / turuncu / yeşil düzeyini belirler ve Gemini sonucu sahibe
dönük sade bir metne çevirip takip sorularını konuşma bağlamıyla yanıtlar.
Son değişikliklerin ayrıntılı raporu: [`DEGISIKLIKLER.md`](DEGISIKLIKLER.md).

> VetAI teşhis koymaz. Ürettiği sonuçlar istatistiksel bir ön değerlendirmedir
> ve veteriner hekim muayenesinin yerine geçmez. Kullanılan veri seti
> **sentetiktir** ve tıbbi içeriği veteriner hekim onayından geçmemiştir
> (bkz. [Veri seti](#veri-seti)).

---

## İçindekiler

1. [Mimari](#mimari)
2. [Kurulum ve çalıştırma](#kurulum-ve-çalıştırma)
3. [Sohbet akışı (Gemini)](#sohbet-akışı-gemini)
4. [Veri seti](#veri-seti)
5. [Ölçüm sonuçları](#ölçüm-sonuçları)
6. [Backend modülleri ve uç noktalar](#backend-modülleri-ve-uç-noktalar)
7. [NLP, guardrail ve aciliyet katmanı](#nlp-guardrail-ve-aciliyet-katmanı)
8. [Canlı öğrenme](#canlı-öğrenme)
9. [Arayüz](#arayüz)
10. [Ortam değişkenleri](#ortam-değişkenleri)
11. [Bilinen sınırlar ve yol haritası](#bilinen-sınırlar-ve-yol-haritası)
12. [Lisans ve atıf](#lisans-ve-atıf)

---

## Mimari

```
React + TypeScript (Vite, Tailwind v4)          FastAPI (Python 3.13)
┌──────────────────────────┐                   ┌────────────────────────────────────┐
│ App.tsx  (sohbet durumu) │  POST /api/chat   │ main.py                            │
│ Composer (giriş)         │ ────────────────► │  1. Guardrail'ler                  │
│ ChatBubble               │  {messages, tur}  │     injection · insan sağlığı ·    │
│ AnalysisResult           │                   │     kapsam (bilgi/kokler) · doz    │
│ Markdown (lib)           │ ◄──────────────── │     + anlam ayrımı (anlam_ayrimi)  │
│ StatusPanel              │ {message, analiz} │  2. Aciliyet   (bilgi/acil_kaliplar)│
└──────────────────────────┘                   │  3. ML tahmini (ml_model)          │
                                               │  3b. Anlam katmanı (anlam_katmani) │
                                               │  4. Context builder (chat_service) │
                                               │  5. Gemini     (gemini_api)        │
                                               │  6. Canlı öğrenme (database/SQLite)│
                                               └────────────────────────────────────┘
```

**Görev dağılımı bilinçlidir.** Teşhis olasılığını makine öğrenmesi modeli
üretir. Kelime sayan bir model "sıcak çarptı" ile "araba çarptı"yı ayıramadığı
için iki anlam katmanı vardır: deterministik **anlam ayrımı tablosu**
(`bilgi/anlam_ayrimi.py`, her zaman çalışır) ve şikâyeti anlamca okuyup ML
sıralamasını düzelten **Gemini anlam katmanı** (`anlam_katmani.py`; hastalık
listesi kapalıdır, Gemini yeni hastalık uyduramaz, sonuç ML dağılımıyla
harmanlanır). Gemini ayrıca çıktıyı anlaşılır bir metne çevirir ve takip
sorularını yanıtlar. Model Gemini'siz de çalışır (şablon metinle). Aciliyet
kararı modelden bağımsız üçüncü bir katmandır: hastalık belirsiz olsa bile
"nefes darlığı" gibi bir bayrak kırmızı uyarı üretir.

---

## Kurulum ve çalıştırma

> Bu bir istemci–sunucu projesidir; **iki sunucu birden çalışmalıdır.**
> Yalnızca `npm run dev` çalıştırırsanız arayüz açılır ama üst çubukta
> "Bağlantı yok" ve yan panelde "Backend kapalı" görürsünüz.

### 1. Backend (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env               # GEMINI_API_KEY değerini buraya yazın
python init_db.py --reset            # veri setini SQLite'a yükler (3.685 satır, 55 sınıf)
uvicorn main:app --reload            # http://127.0.0.1:8000/docs
```

Başlangıç logunda şunları görmelisiniz:

```
ML modeli hazir: 3685 ornek, 55 sinif, 16357 ozellik (capraz dogrulama arka planda hesaplaniyor)
Gemini katmani: AKTIF
Anlam katmani: AKTIF (model=gemini-2.5-flash)
```

`init_db.py` adımı artık zorunlu değil: sunucu açılışta veritabanı yoksa kurar,
eski sürümden kalmışsa eksik kolonları (`hastalik_id`, `aciliyet`, `kaynak_id`)
ekler, v1 öncesi kayıtları temizler ve eksik halk dili tariflerini yükler.
`--reset` yalnızca tabloyu bilerek sıfırdan kurmak istediğinizde gerekir.
Ayrıntı: [`Backend.md`](Backend.md).

### 2. Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

### Tek komutla

İlk kurulumdan sonra proje kökünde:

```powershell
npm run dev:all                      # start.ps1: iki ayrı pencerede backend + frontend
.\start.ps1 -Kontrol                 # pencere açmadan ön kontrol (port, .env, node_modules)
```

Sunucu ayaktayken uçların hepsini tek komutla denemek için:

```powershell
cd backend
python duman_testi.py                # API duman testi (guardrail, sohbet, 422, retrain)
python anlam_testi.py                # anlam ayrımı / halk dili testleri (sunucu gerekmez, Gemini harcamaz)
```

### Gemini API anahtarı

`backend/.env` içindeki `GEMINI_API_KEY` alanına
[Google AI Studio](https://aistudio.google.com/apikey)'dan aldığınız anahtarı
yazın. Gerçek anahtar yalnızca `.env` dosyasında durur; bu dosya git'e girmez.

**Anahtar olmadan da çalışır:** şikâyet mesajlarında ML tahmini, aciliyet ve
bilgi tabanındaki öneri metinleriyle şablon tabanlı bir yanıt üretilir. Şikâyet
içermeyen serbest sohbet mesajları ("Merhaba", takip soruları) ise anahtar
olmadan yanıtlanamaz; arayüz bunu açıklayıcı bir hata balonu ve "Tekrar dene"
düğmesiyle gösterir.

**Kota:** Anlam katmanı açıkken her şikâyet iki Gemini isteği harcar (anlam
çözümleme + sohbet yanıtı). Ücretsiz katmanda `gemini-2.5-flash` dakikada 5
istekle sınırlıdır; ayrı bir kota havuzu için `.env` içine
`GEMINI_ANLAM_MODEL=gemini-3.5-flash-lite` yazılabilir. Kota dolduğunda sistem
ML + anlam ayrımı tablosuyla çalışmaya devam eder.

> **Windows + antivirüs notu:** Norton gibi TLS tarayan programlar Google'ın
> sertifikasını kendi kök sertifikalarıyla değiştirir; Python bunu varsayılan
> olarak tanımaz ve Gemini çağrıları `CERTIFICATE_VERIFY_FAILED` ile düşer.
> `requirements.txt` içindeki `truststore` paketi işletim sisteminin sertifika
> deposunu kullanarak bu sorunu çözer; ek ayar gerekmez.

---

## Sohbet akışı (Gemini)

```
Kullanıcı mesajı (Composer)
  → App.gonder()             geçmiş + yeni mesaj, tek istek kilidi, iptal edilebilir
  → POST /api/chat           { messages: ChatMessage[], tur }
  → main.sohbet()            guardrail + aciliyet + ML (Gemini'siz)
  → chat_service.baglam_olustur()
                             sistem talimatı + son N mesaj + bu tura ait analiz bağlamı
  → gemini_api.sohbet()      generate_content, rol: user / model
  → { message, analiz? }     asistan balonu (+ şikâyetse analiz kartı)
```

- **Ortak mesaj biçimi** `{ id, role: "user" | "assistant" | "system", content, createdAt? }`
  hem `frontend/src/api.ts` hem `backend/chat_service.py` içinde tanımlıdır.
  İstemciden gelen `system` rolü sunucuda yok sayılır; sistem talimatı yalnızca
  sunucuda yaşar.
- **Bağlam yönetimi:** son 12 mesaj (`CHAT_HISTORY_LIMIT`), mesaj başına 2.000
  karakter kırpma, ardışık aynı rol birleştirme. O tura ait ML tahminleri
  yalnızca son kullanıcı mesajına eklenir; geçmişte tekrar taşınmaz.
- **Tek LLM çağrısı:** şikâyet turlarında ML analizi Gemini'siz çalışır,
  tahminler bağlam olarak tek bir sohbet çağrısına verilir.
- **Hata yönetimi:** anahtar yok / geçersiz / model bulunamadı → 503, kota → 429,
  zaman aşımı → 504, sunucu → 502; hepsi açıklayıcı `detail` alanıyla. Güvenlik
  filtresi ve boş yanıt kontrollü bir asistan mesajına dönüşür. ML tahmini varsa
  Gemini düşse bile şablon metinle yanıt üretilir.
- **Model:** `GEMINI_MODEL` ile seçilir, varsayılan `gemini-3.8-flash`.
  Gemini 3.x için `thinking_level=MINIMAL`, sıcaklık varsayılanda, çağrı başına
  zaman aşımı (`GEMINI_TIMEOUT_MS`), `prompt_feedback` ve `finish_reason` kontrolü.

---

## Veri seti

`backend/data/` altındaki **sentetik başlangıç veri seti v1** (26 Eylül 2026):

| Dosya | İçerik |
|---|---|
| `vetai_sentetik_sikayetler_v1.csv` | 3.025 etiketli Türkçe şikâyet (2.695 kurallı üretim + 330 el yazımı), 55 hastalık × 55, `train` 2.475 / `val` 550 |
| `vetai_dis_test_seti_v1.csv` | 110 şablon dışı, uzun ve dağınık el yazımı cümle (hastalık başına 2). **Eğitime girmez.** |
| `vetai_halk_dili_tanimlari_v1.csv` | 1.210 halk dili tarifi: her hastalık için 22 farklı sahip anlatımı ("göğsü hırıl hırıl", "kah kuh yapıyor", "sıcak çarptı", "kızak çekiyor"). Eğitime `seed` (1,0) olarak girer. |
| `vetai_anlam_testi_v1.csv` | 142 cümle: 110 halk dili (hastalık başına 2) + 32 yanıltıcı kelime içeren "tuzak" cümle. **Eğitime girmez.** |
| `halk_dili_sozlugu.json` | 681 halk dili belirti kökü, 115 ML ifadesi, 2 yeni belirti kodu (`KALP_CARPINTI`, `NEZLE`), 55 hastalığın halk dilinde tipik anlatımı |
| `vetai_bilgi_tabani.json` | 55 hastalık kaydı (tür, yaş/ırk yatkınlığı, seyir, aciliyet, belirti ağırlıkları, ayırıcı tanılar, açıklama, evde yapılacaklar, kaçınılacaklar) + 153 belirti kodu ve 639 sahip-dili ifadesi |
| `oneriler.json` | Hastalık → arayüzde gösterilen öneri metni (açıklama + evde + kaçın + veteriner uyarısı) |
| `hastalik_aciliyet.json` | Hastalık → temel aciliyet (kırmızı / turuncu / yeşil) |
| `UYARI_OKUYUN.txt` | Verinin nasıl üretildiği ve neye güvenilip neye güvenilemeyeceği |

**Nasıl kullanılıyor:** `init_db.py` yalnızca `train` satırlarını yükler; el
yazımı örnekler `seed` (ağırlık 1,0), üretilmiş cümleler `sentetik` (0,7)
kaynağıyla kaydedilir; halk dili tarifleri `seed` olarak eklenir (toplam 3.685
eğitim satırı). `val`, dış test ve anlam testi satırları ölçüm için ayrılmıştır
(`olcum.py`). `backend/bilgi/` altındaki modüller:

| Modül | Görev |
|---|---|
| `anlam_ayrimi.py` | 47 deyim / eş sesli ifade kalıbı ("sıcak çarptı" ≠ "araba çarptı", "kusura bakmayın", "nöbetçi", "iştahı düştü", "kurt köpeği" …). ML, guardrail ve aciliyetten önce çözülür; eşleşen aralık kök taramasında maskelenir. |
| `kokler.py` | 155 belirti kodu için kök tabanlı tanıma (+ halk dili kökleri); `guardrail()` → `devam` / `belirti_sor` / `kapsam_disi`. Kısa kökler yalnızca kelime başında ve Türkçe yazımda eşleşir; "ateşi yok", "kusması geçti" gibi basit olumsuzlamalar düşürülür. |
| `acil_kaliplar.py` | 15 kırmızı + 42 turuncu belirti regex'i (Türkçe/ASCII duyarsız) + anlam ayrımı bayrakları (sıcak / elektrik çarpması, ilaç yutma); `aciliyet_tespit(metin, hastalik_temel)` |
| `esanlam_sozlugu.py` | Belirti kodu → kanonik Türkçe ad (arayüz rozetleri), ifade → kod |

**Dürüst uyarı:** Bu veri setindeki hiçbir cümle gerçek bir hayvan sahibinden
gelmemektedir; tamamı yapay zekâ destekli kurallı üretim ve el yazımıdır.
Etiketler kendi içinde tutarlıdır ve prototipi çalıştırmak için yeterlidir, ama
gerçek kullanıcıların yazım biçimini ve hastalıkların gerçek görülme sıklığını
temsil etmez. Projede, tezde ve sunumlarda **"sentetik (yapay) başlangıç veri
seti"** olarak adlandırılmalıdır.

---

## Ölçüm sonuçları

`python olcum.py` (backend klasöründe) projenin gerçek yolunu (anlam ayrımı →
guardrail → tür filtresi → ML → aciliyet birleştirme) eğitime girmeyen kümeler
üzerinde **Gemini'siz** çalıştırır (3 Ekim 2026; önceki değerler parantez içinde).

| Küme | n | Top-1 | Top-3 | Kararsız bayrağı | Guardrail "devam" | Aciliyet (3 sınıf) | Kırmızı yakalama |
|---|---|---|---|---|---|---|---|
| val (üretilmiş + el yazımı) | 550 | **0,915** (0,885) | 0,984 | %8 | %99,5 | 0,942 | 144 / 150 |
| val — yalnızca el yazımı | 165 | 0,879 (0,764) | 0,976 | %6 | %100 | 0,903 | 35 / 39 |
| dış test (şablon dışı) | 110 | 0,945 (0,864) | 0,991 | %8 | %100 | — | — |
| anlam testi — halk dili | 110 | 0,982 (0,755) | 1,000 | %6 | %98,2 | — | — |
| anlam testi — tuzak cümleler | 32 | 0,969 (0,781) | 1,000 | %0 | %100 | — | — |
| 8 alakasız cümle (mama, isim, TEKNOFEST, takip sorusu…) | 8 | — | — | — | 8 / 8 kapsam dışı | — | — |

Çapraz doğrulama (3 kat, eğitim kümesi): 0,820 (eğitim havuzu değiştiği için
önceki 0,874 ile karşılaştırılamaz). Yeşil cümlelerde yanlış kırmızı: 2 / 193.
Halk dili ve anlam testi cümleleri aynı kaynaktan yazıldığı için bu iki satır
iyimserdir. `python olcum.py --anlam 20` aynı cümlelerde Gemini anlam katmanını
da ölçer (20 Gemini isteği); `python anlam_testi.py` 74 kontrollü testi çalıştırır.

Eski 20 sınıflı, 101 satırlık seed verisiyle çapraz doğrulama %53 idi. Veri seti
entegrasyonundan önce aynı pipeline bu veride %86 top-1 veriyordu ama cümlelerin
%43'ü guardrail'de eleniyor ve kırmızı cümlelerin yalnızca %20'si yakalanıyordu;
tür token'ı + tür filtresi, kök tabanlı guardrail ve hastalık temel aciliyetiyle
bu değerler yukarıdaki tabloya geldi.

El yazımı cümlelerdeki değer (%88), gerçek kullanıcı metninde beklenmesi gereken
seviyeye en yakın göstergedir.

---

## Backend modülleri ve uç noktalar

| Dosya | Sorumluluk |
|---|---|
| `main.py` | FastAPI uygulaması, guardrail'ler, anlam katmanı entegrasyonu, aciliyet birleştirme, `/api/analyze`, `/api/chat` |
| `anlam_katmani.py` | Gemini anlam katmanı: şikâyeti kapalı hastalık/belirti listesiyle (JSON şema) anlamca okur, ML dağılımını `0,7 × anlam + 0,3 × ML` ile düzeltir; Gemini yoksa devre dışı kalır |
| `chat_service.py` | Sohbet servisi ve context builder (sistem talimatı + son N mesaj + analiz bağlamı) |
| `gemini_api.py` | google-genai SDK ile Gemini entegrasyonu: tek atımlık yorum + çok turlu sohbet + JSON şemalı çağrı, hata sınıflandırma, zaman aşımı, TLS düzeltmesi |
| `ml_model.py` | TF-IDF (1–2 gram) + Logistic Regression, tür token'ı ve tür filtresi, tam olasılık dağılımı, marj tabanlı kararsızlık, yorumlanabilirlik (`aciklayici_kelimeler`) |
| `nlp_engine.py` | Türkçe normalizasyon, anlam ayrımı, eş anlamlı + halk dili haritalama, stop-words, kural tabanlı stemmer, olumsuzluk işaretleme (tokenizer) |
| `bilgi/` | Veri setinden türetilen guardrail, aciliyet ve sözlük modülleri (yukarıda) |
| `database.py` | SQLAlchemy modeli, SQLite bağlantısı, `symptoms` tablosu, kaynak ağırlıkları, eski şemaya eksik kolon ekleme |
| `init_db.py` | Veri setini ve halk dili tariflerini CSV'den yükler (`--reset` ile sıfırdan; eksik tarifleri mevcut veritabanına ekler), v1 öncesi kayıtları temizler |
| `konsol.py` | Konsol çıktısını UTF-8'e alır (Windows'ta Türkçe karakter çökmesini önler) |
| `olcum.py` | val + dış test + anlam testi üzerinde uçtan uca ölçüm (`--anlam N`: Gemini ile) |
| `anlam_testi.py` | Anlam ayrımı, halk dili, birleştirme ve uçtan uca (Gemini taklitli) 74 test |
| `duman_testi.py` | Çalışan sunucuya karşı uçtan uca API duman testi |
| `migrate_turkce.py` | Eski veritabanı için tek seferlik Türkçe yazım bakım aracı (yeni şemada gerekmez) |

Açılış davranışı (şema onarımı, otomatik veri kurulumu), Gemini model uyumu ve
sorun giderme için [`Backend.md`](Backend.md).

| Metot | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/chat` | Sohbet (arayüzün kullandığı uç): geçmiş → guardrail → aciliyet → ML → context builder → Gemini → öğrenme |
| `POST` | `/api/analyze` | Tek atımlık analiz (geçmişsiz), aynı çekirdek zincir |
| `GET` | `/api/health` | Sunucu, veritabanı, model ve Gemini durumu |
| `GET` | `/api/stats` | Veri seti istatistikleri ve sınıf dağılımı |
| `GET` | `/api/symptoms` | Son eklenen kayıtlar (canlı öğrenmeyi izlemek için) |
| `POST` | `/api/retrain` | Modeli güncel veriyle yeniden eğitir |

`AnalizYaniti` şeması: `durum` (ok / acil / belirsiz / kapsam_disi / reddedildi),
`tur`, `bulgular` (kanonik belirti adları), `tahminler[]` (hastalık, olasılık,
öneri, açıklayıcı kelimeler), `ai_yorum`, `acil`, `acil_gerekce`, **`aciliyet`**
(kirmizi / turuncu / yesil), **`aciliyet_bayraklari`**, **`kararsiz`**, `uyarilar`,
`ogrenildi`, `model_bilgi`, anlam katmanı alanları `anlam_aktif`, `anlam_ozeti`,
`anlam_notu`, `ml_ilk_tahmin`; tahminlerde `ml_yuzde`, `anlam_gerekcesi`.

---

## NLP, guardrail ve aciliyet katmanı

**Tokenizer (`nlp_engine.py`)** modele giden metni hazırlar: Türkçe'ye duyarlı
küçük harf ve ASCII katlama ("kaşıntı" = "kasinti"), anlam ayrımı ("sıcak çarptı"
→ `sicak_carpmasi`, "araba çarptı" → `travma_oykusu`), çok kelimeli ve tek
kelimeli eş anlamlı + halk dili haritalama ("kah kuh" → öksürük), stop-words,
kural tabanlı gövdeleme, belirti fiilleri için önek eşleme ("öksürdü",
"hırıldıyor") ve olumsuzluk işaretleme (`"ateşi yok"` → `yok_ates`). Tür bilgisi
metnin başına gövdelenmeden geçen bir token olarak eklenir (`kedix` /
`kopekx`); metindeki "kedim / köpeğim" kelimeleri ML özelliği olarak kullanılmaz.

**Guardrail sırası (`main.py`):**

| # | Kontrol | Davranış |
|---|---|---|
| 0 | Anlam ayrımı | Deyim / eş sesli ifadeler kök taramasından önce çözülür ("sıcak çarptı" travma değil); 3–6. adımların hepsi bu çözümü kullanır |
| 1 | Prompt injection | `reddedildi`; ML ve Gemini çağrılmaz |
| 2 | Çok kısa girdi (< 8 karakter) | Ayrıntı ister (sohbette Gemini'ye gider) |
| 3 | İnsan sağlığı, hayvan sözcüğü yok | Kapsam dışı, hekime yönlendirir ("başım ağrıyor" belirti içerse bile) |
| 4 | Kapsam dışı (`kokler` belirti bulamadı, hayvan sözcüğü yok) | ML çalışmaz; sohbette Gemini bağlamla yanıtlar (takip soruları, genel sorular) |
| 5 | İlaç/doz talebi | Doz verilmez; insan ilaçlarının öldürücü olduğu uyarısı |
| 6 | Aciliyet bayrakları | Metindeki 57 kırmızı/turuncu belirti regex'i + anlam ayrımı bayrakları |
| 7 | ML dağılımı + anlam katmanı | Gemini şikâyeti anlamca okur; "şikâyet değil" derse kart üretilmez |
| 7b | Hayvan var ama belirti yok | Anlam katmanı halk dilinde bir şikâyet görmediyse hangi belirtilerin yazılması gerektiğini söyler |
| 8 | Tahmin (ML + anlam düzeltmesi) + tür filtresi | O türde görülmeyen hastalıklar sıfırlanır |
| 8b | Aciliyet birleştirme | max(metin bayrakları, tahmin edilen hastalığın temel aciliyeti) |
| 9 | Kararsızlık | top1 < 0,15 **veya** top1 − top2 < 0,05 ise "olası tablolar" dili |

Aciliyet regex'leri olumsuzlamayı anlamaz; bu yüzden hangi bayrağın uyarıyı
tetiklediği kullanıcıya açıkça gösterilir (`aciliyet_bayraklari`).

---

## Canlı öğrenme

Her analizden sonra yeni ifade `symptoms` tablosuna yazılır, ama modeli bozmayacak
şekilde:

| Kaynak | Açıklama | Eğitim ağırlığı |
|---|---|---|
| `seed` | Veri setindeki el yazımı örnekler | 1,0 |
| `sentetik` | Kurallı üretilmiş cümleler | 0,7 |
| `auto` | Model ≥ %45 güvendeyse otomatik etiketlenir | 0,35 |
| `pending` | Düşük güvenli; eğitime **girmez**, insan onayı bekler | 0 |

Mevcut kayıtlarla Jaccard benzerliği ≥ 0,85 olan ifadeler yeniden kaydedilmez.
Otomatik kayıtlarda `hastalik_id` ve temel aciliyet de saklanır.

---

## Arayüz

Adaçayı yeşili odaklı, açık/koyu temalı, minimalist tasarım sistemi. Renk paleti,
tema mimarisi ve bileşen kuralları için [`Frontend.md`](Frontend.md).

Sohbet özellikleri: Enter gönderir / Shift+Enter alt satır, boş ve yalnızca boşluk
mesaj gönderilmez, istek sürerken tekrar gönderim engellenir, yanıt beklenirken
yazmaya devam edilebilir, hata balonunda "Tekrar dene", yanıt kopyalama, sohbeti
temizleme (bekleyen isteği iptal eder), kullanıcı yukarı kaydırdıysa zorlamayan
auto-scroll, bağımlılıksız ve HTML enjeksiyonsuz Markdown (başlık, liste, kalın,
satır içi kod, kod bloğu, bağlantı). Analiz kartında kırmızı (acil) ve turuncu
(24 saat içinde) uyarılar, bulgu rozetleri, olasılık çubukları ve "bu tahmini
destekleyen ifadeler" gösterilir.

---

## Ortam değişkenleri

`backend/.env.example`:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | — | Google AI Studio anahtarı. Yoksa Gemini katmanı devre dışı |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Kullanılacak model; daha ucuz seçenek `gemini-3.5-flash-lite` |
| `GEMINI_TIMEOUT_MS` | `30000` | Çağrı başına zaman aşımı |
| `CHAT_HISTORY_LIMIT` | `12` | Sohbette Gemini'ye gönderilen azami geçmiş mesaj sayısı |
| `ANLAM_KATMANI` | `1` | Gemini anlam katmanı; `0` → yalnızca ML + anlam ayrımı tablosu |
| `GEMINI_ANLAM_MODEL` | (boş → `GEMINI_MODEL`) | Anlam katmanının modeli; ayrı kota için ör. `gemini-3.5-flash-lite` |
| `ANLAM_ZAMAN_ASIMI_MS` | `15000` | Anlam çağrısı zaman aşımı |
| `ANLAM_DUSUNME` | `MINIMAL` | Anlam çağrısının düşünme seviyesi (`LOW` daha dikkatli, daha yavaş) |
| `DATABASE_URL` | `sqlite:///./vetai.db` | SQLite dosyası |
| `ALLOWED_ORIGINS` | localhost:5173/5174 | CORS |

`frontend/.env.example`: `VITE_API_URL` boş bırakılırsa Vite proxy'si `/api` →
`127.0.0.1:8000` yönlendirmesi yapar.

---

## Bilinen sınırlar ve yol haritası

- **Veri sentetik.** Bir veteriner hekimin bilgi tabanını (özellikle aciliyet
  düzeyleri ve "evde yapılacaklar") gözden geçirmesi ve çevreden 150–200 gerçek
  şikâyet cümlesi toplanıp modelin onlarla ölçülmesi gerekir. Gerçek metinde
  top-1'in %70 civarına inmesi beklenmelidir.
- **Tek belirtili kısa cümleler** ("kedim kusuyor") doğası gereği belirsizdir;
  model doğru biçimde kararsız işaretler ve üç tabloyu birden gösterir.
- **Negasyon** guardrail'de basit kurallarla, aciliyet regex'lerinde hiç ele
  alınmaz; bayraklar bu yüzden şeffaf gösterilir.
- **Streaming yanıt, sohbet kalıcılığı, rate limit** yok; sayfa yenilenince
  sohbet sıfırlanır. Herkese açık dağıtımda `/api/chat` için istemci başına hız
  sınırı eklenmelidir.
- **RAG yok.** İleride bilgi tabanı (`vetai_bilgi_tabani.json`) bir retriever ile
  `chat_service.baglam_olustur()` içine bağlanabilir; UI ve API katmanı değişmez.
- Açık maddelerin güncel listesi: [`CHATBOT_TODO.md`](CHATBOT_TODO.md).
- Veri seti yol haritası (yeni veri seti ekleme, gerçek cümle toplama, lisanslar): [`VERI_SETI_TODO.md`](VERI_SETI_TODO.md).

---

## Lisans ve atıf

Veri seti, bilgi tabanı ve türetilen modüller: **CC BY 4.0** (VetAI projesi,
2026). Aciliyet kuralları Bio-Vet pet-symptom-triage'dan uyarlanmıştır (CC BY
4.0, bio.vet). Hastalık bilgileri genel kaynaklardan (Vikipedi CC BY-SA, MSD
Veterinary Manual yalnızca okuma, VetCompass yayınları, Erciyes Üniv. Vet. Fak.
ders notları) kendi cümlelerle derlenmiştir. Ayrıntı: `backend/data/UYARI_OKUYUN.txt`.
