# VetAI — Backend Onarım Notları

Bu belge, sunucunun hiç açılmamasına yol açan üç ayrı arızayı, her biri için
yapılan düzeltmeyi ve düzeltme sonrası çalıştırılan testlerin sonuçlarını
anlatır. Frontend tarafındaki tasarım değişiklikleri için bkz. `Frontend.md`.

---

## 1. Özet: ne bozuktu, ne değişti?

| Belirti | Kök neden | Çözüm |
| --- | --- | --- |
| `uvicorn main:app --reload` açılışta `sqlite3.OperationalError: no such column: symptoms.hastalik_id` verip kapanıyordu; arayüzde "Bağlantı yok", Vite tarafında `ECONNREFUSED 127.0.0.1:8000` | `backend/vetai.db` eski (20 sınıflı) sürümden kalmıştı. SQLAlchemy'nin `create_all` çağrısı **var olan** tabloya yeni kolon eklemez; `hastalik_id` ve `aciliyet` kolonları eksik kaldı | Açılışta eksik kolonlar `ALTER TABLE` ile tamamlanıyor, v1 öncesi kayıtlar temizleniyor, veri yoksa otomatik yükleniyor |
| `python init_db.py` komutu `UnicodeEncodeError: 'charmap' codec can't encode character` ile düşüyordu | Windows'ta çıktı dosyaya ya da boruya yönlendirildiğinde Python stdout'u sistem kod sayfasıyla (cp1252) açar; "ı, ş, ğ" harfleri kodlanamaz | Yeni `backend/konsol.py`: bütün giriş noktaları stdout/stderr'i UTF-8'e alıyor |
| Her analiz ve sohbet şablon metne düşüyordu; kayıtlarda `400 INVALID_ARGUMENT — Thinking level is not supported for this model` | Kod 3.x'e özgü `thinking_level` alanını gönderiyordu, `.env` dosyasında ise `GEMINI_MODEL=gemini-2.5-flash` yazılı | Düşünme ayarı artık model sürümüne göre seçiliyor (3.x → `thinking_level`, 2.5 → `thinking_budget`, 2.0 ve öncesi → alan gönderilmiyor) |

Yeni dosya: `backend/konsol.py`.
Değişen dosyalar: `backend/database.py`, `backend/init_db.py`, `backend/main.py`,
`backend/gemini_api.py`, `backend/olcum.py`.

---

## 2. Sorun 1 — Eski veritabanı şeması sunucuyu düşürüyordu

### 2.1 Ne oluyordu?

`backend/vetai.db` dosyası, veri seti v1'e (55 hastalık) geçilmeden önceki
sürümden kalmıştı: 105 satır ve şu kolonlar:

```
id, tur, semptom, hastalik, oneri, kaynak, guven, olusturma_tarihi
```

Model ise `hastalik_id` ve `aciliyet` kolonlarını da okuyor. `init_database()`
yalnızca `Base.metadata.create_all` çağırdığı için tablo "zaten var" sayılıyor ve
hiç güncellenmiyordu. Açılış sırası şöyleydi:

```
lifespan -> ml_model.egit() -> _veriyi_yukle() -> SELECT ... symptoms.hastalik_id
   -> sqlite3.OperationalError: no such column
   -> "Application startup failed. Exiting."
```

Sunucu hiç dinlemeye başlamadığı için Vite'ın `/api` proxy'si her istekte
`ECONNREFUSED` veriyor, arayüz de "BACKEND KAPALI" uyarısını gösteriyordu.
Yani arayüzdeki hata bir frontend sorunu değil, bu çökmenin yansımasıydı.

### 2.2 Düzeltme

**a) Eksik kolonların tamamlanması — `backend/database.py:87`**

```python
def eksik_kolonlari_tamamla() -> list[str]:
    """Var olan tablolara sonradan eklenen nullable kolonlari ALTER ile ekler."""
    denetci = inspect(engine)
    ...
    baglanti.execute(text(f"ALTER TABLE {tablo.name} ADD COLUMN {kolon.name} {tip}"))
```

Model ile veritabanı karşılaştırılır, eksik olan **nullable** kolonlar eklenir.
`NOT NULL` bir kolon `ALTER` ile güvenle eklenemeyeceği için atlanır; öyle bir
durumda tam kurulum (`python init_db.py --reset`) gerekir. `init_database()`
(`backend/database.py:119`) bu adımı her açılışta çalıştırır ve eklenen kolonları
terminale yazar:

```
[database] Eski şemaya eklenen kolonlar: symptoms.hastalik_id, symptoms.aciliyet
```

**b) v1 öncesi kayıtların temizlenmesi — `backend/init_db.py:59`**

Kolonları eklemek tek başına yetmez: eski satırların hastalık adları bugünkü
bilgi tabanında (`data/oneriler.json`) karşılıksızdır ve modeli bozar. Bu yüzden
`hastalik_id` alanı boş olan eğitim kayıtları silinir:

```
[init_db] v1 öncesi 101 kayıt silindi (eski veri setinin hastalıkları bugünkü bilgi tabanında yok).
```

Kullanıcı sorgularından gelen `pending` satırlar **korunur**; zaten eğitime
girmedikleri için (ağırlık 0.0) modele etkileri yoktur.

**c) Açılışın kendi kendini onarması — `backend/main.py:216`**

```python
    init_database()
    # Bos ya da eski surumden kalan bir veritabani sunucuyu durdurmasin:
    # sema tamamlanir, v1 oncesi kayitlar temizlenir, veri yoksa yuklenir.
    try:
        init_db.seed(sessiz=True)
    except Exception:
        logger.exception(
            "Başlangıç verisi yüklenemedi. Terminalde şunu çalıştırın: "
            "python init_db.py --reset"
        )
```

Artık `vetai.db` hiç yokken de, eski sürümden kalmışken de tek komut yeterli:
`uvicorn main:app --reload`. `sessiz=True`, yapacak iş olmadığında her açılışta
gereksiz çıktı basılmasını önler; `python init_db.py` elle çalıştırıldığında
bilgi mesajları eskisi gibi görünür.

---

## 3. Sorun 2 — Windows konsolunda Türkçe karakter çökmesi

`python init_db.py` çıktısı bir dosyaya ya da boruya yönlendirildiğinde
(örneğin `python init_db.py > kurulum.log`) Python stdout'u sistemin kod
sayfasıyla açar. cp1252/cp857 "ı", "ş", "ğ" harflerini kodlayamadığı için betik,
işini bitirdikten sonra bile `UnicodeEncodeError` ile düşüyordu.

Yeni `backend/konsol.py:14`:

```python
def utf8_cikti_ayarla() -> None:
    """stdout/stderr'i UTF-8'e alir; desteklenmeyen karakteri hata yerine degistirir."""
    for akis in (sys.stdout, sys.stderr):
        yeniden_ayarla = getattr(akis, "reconfigure", None)
        ...
        yeniden_ayarla(encoding="utf-8", errors="replace")
```

Çağrıldığı yerler: `main.py:58`, `init_db.py:138`, `olcum.py:27`.
(`olcum.py` içinde aynı işi yapan satır arası kod, tek kaynak olsun diye bu
fonksiyonla değiştirildi.) Bu düzeltme, arayüz metinlerinde olduğu gibi terminal
çıktısında da Türkçe karakterlerin eksiksiz kalmasını sağlar.

---

## 4. Sorun 3 — Gemini katmanı her istekte 400 dönüyordu

### 4.1 Ne oluyordu?

`.env` dosyasında model `gemini-2.5-flash` olarak ayarlı, kod ise Gemini 3.x'e
özgü `thinking_level` alanını gönderiyordu:

```
[ERROR] vetai.gemini: Gemini çağrısı başarısız (model_bulunamadi):
400 INVALID_ARGUMENT. {'error': {'message': 'Thinking level is not supported for this model.'}}
[WARNING] vetai: Sohbet: Gemini devre dışı (model_bulunamadi), şablon metin kullanılıyor.
```

Sunucu bu hatayı yutup şablon metne düştüğü için uygulama "çalışıyor" görünüyor,
ama yapay zekâ katmanı fiilen hiç devrede olmuyordu (`ai_aktif: false`).

### 4.2 Düzeltme — `backend/gemini_api.py:201`

```python
def _dusunme_yapilandirmasi(types, thinking_level: str):
    surum = _model_surumu(MODEL_ADI)
    if surum >= (3, 0):
        return types.ThinkingConfig(thinking_level=thinking_level)
    if surum >= (2, 5):
        butce = _DUSUNME_BUTCESI.get(thinking_level, 0)
        if butce == 0 and "pro" in MODEL_ADI:
            butce = 128          # 2.5 Pro dusunmeyi tamamen kapatamaz
        return types.ThinkingConfig(thinking_budget=butce)
    # 2.0 ve oncesi dusunme ayarini hic desteklemez; alan gonderilmez.
    return None
```

| Model | Gönderilen alan | Not |
| --- | --- | --- |
| `gemini-3.8-flash` (kod varsayılanı) | `thinking_level` | MINIMAL'i reddediyor, LOW ile çalışıyor (aşağıya bakın) |
| `gemini-3.x` (diğerleri) | `thinking_level="MINIMAL"` | 3.x serisinin beklediği biçim |
| `gemini-2.5-flash` (`.env` değeri) | `thinking_budget=0` | Düşünme kapalı |
| `gemini-2.5-pro` | `thinking_budget=128` | Bu model düşünmeyi tamamen kapatmaya izin vermiyor |
| `gemini-2.0-flash` ve öncesi | (alan gönderilmez) | Düşünme ayarını hiç desteklemiyor |

Sürüm, model adından `re.search(r"gemini-(\d+)(?:\.(\d+))?", ad)` ile okunur;
tanınmayan bir ad gelirse düşünme ayarı hiç gönderilmez (en güvenli davranış).

### 4.3 Aynı ailede seviye farkı: geri çekilme zinciri

Doğrulama sırasında ikinci bir uyumsuzluk çıktı: kodun **varsayılan modeli**
`gemini-3.8-flash`, doğru alanı alsa bile `MINIMAL` değerini kabul etmiyor:

```
400 INVALID_ARGUMENT. Thinking level MINIMAL is not supported for this model.
Please retry with other thinking level.
```

Yani `.env` içindeki `GEMINI_MODEL` satırı silinseydi yapay zekâ katmanı yine
çalışmayacaktı. Bu yüzden `_uret()` artık tek bir yapılandırmaya bağlı değil,
sırayla dener (`_dusunme_etiketleri`, `backend/gemini_api.py:222`):

```
istenen seviye (MINIMAL)  ->  bir üst seviye (LOW)  ->  alanı hiç gönderme
```

* Yalnızca hata **düşünme ayarı kaynaklıysa** (`_dusunme_hatasi_mi`) bir sonraki
  adıma geçilir; kota, ağ ya da yetki hatasında zincir denenmez.
* İlk başarılı seçim süreç boyunca hatırlanır, sonraki çağrılar doğrudan onunla
  başlar. Ücretsiz katmanda istek sınırı çok düşük olduğu için bu önemli:
  her çağrıda başarısız bir deneme daha yapılmaz.

Kayıttaki görünümü:

```
INFO: Model 'gemini-3.8-flash' düşünme seviyesi 'MINIMAL' kabul etmedi, 'LOW' deneniyor.
INFO: Düşünme ayarı 'LOW' olarak belirlendi (model=gemini-3.8-flash).
```

Böylece `.env` içindeki `GEMINI_MODEL` değeri ne olursa olsun (2.0, 2.5, 3.x ya
da tanınmayan bir ad) istek geçerli kalır.

---

## 5. Değişen dosyalar

| Dosya | Değişiklik |
| --- | --- |
| `backend/konsol.py` | **Yeni.** `utf8_cikti_ayarla()` — konsol çıktısını UTF-8'e alır |
| `backend/database.py` | `eksik_kolonlari_tamamla()` eklendi; `init_database()` artık şemayı da onarıyor |
| `backend/init_db.py` | `_eskimis_kayitlari_temizle()` eklendi; `seed()` fonksiyonuna `sessiz` parametresi |
| `backend/main.py` | Açılışta otomatik veri kurulumu; uyarı metinleri `--reset` komutunu gösteriyor |
| `backend/gemini_api.py` | `_model_surumu()` ve `_dusunme_yapilandirmasi()` eklendi; `_uret()` bunları kullanıyor |
| `backend/olcum.py` | Satır arası kodlama ayarı yerine ortak `utf8_cikti_ayarla()` |
| `start.ps1` | 8000 portu doluysa açık uyarı (bkz. bölüm 8); `-Kontrol` anahtarı; metinler tam Türkçe (UTF-8 BOM) |
| `backend/duman_testi.py` | **Yeni.** Çalışan sunucuya karşı uçtan uca API duman testi (bkz. bölüm 6.2) |
| `README.md`, `package.json` | Yeni açılış davranışı, `duman_testi.py` ve `npm run test:api` |

---

## 6. Test sonuçları

Bütün testler düzeltmelerden sonra, çalışan sunucu üzerinde yapıldı.

### 6.1 Açılış senaryoları

| Senaryo | Sonuç |
| --- | --- |
| Gerçek eski şemalı (20 sınıflı) veritabanıyla açılış | Kolonlar eklendi, eski kayıt silindi, 2.475 örnek / 55 sınıf yüklendi, `pending` satırlar korundu |
| `vetai.db` hiç yokken açılış | Veritabanı kuruldu, veri yüklendi, model eğitildi |
| Normal açılış (`uvicorn main:app`) | Hatasız; 2.475 örnek, 55 sınıf, 9.965 özellik, çapraz doğrulama **0,8747** |

### 6.2 API duman testi (`python duman_testi.py`) — 20 kontrolün 20'si geçti

Testler artık `backend/duman_testi.py` içinde; `python duman_testi.py` ya da proje
kökünden `npm run test:api` ile çalıştırılır. Bir kontrol kalırsa çıkış kodu 1 olur.
Aşağıdaki tablo, Gemini kotası doluyken alınan sonuçtur: aynı koşuda ML ve
guardrail kontrollerinin tamamı geçer, yapay zekâ satırları `[UYARI]` olur
("17 geçti, 0 kaldı, 3 uyarı"); kota serbestken hepsi `[GEÇTİ]` olur.

| Grup | Kontrol | Sonuç |
| --- | --- | --- |
| Sağlık | `/api/health`, `/api/stats`, `/api/symptoms` | 200; model eğitildi, Gemini aktif |
| Analiz | "Kedim iki gündür kusuyor…" | tür `kedi`, 1. tahmin "Akut gastroenterit" %12,5, `ai_aktif=true` |
| Analiz | "Köpeğim kulağını kaşıyor…" | tür `kopek`, 1. tahmin "Dış kulak yolu iltihabı" %43,7, `ai_aktif=true` |
| Güvenlik | "Köpeğim çikolata yedi, havale geçiriyor" | `acil=true`, aciliyet `kirmizi`, gerekçe "Zehirli madde teması" |
| Güvenlik | İnsan sağlığı sorusu | `kapsam_disi` |
| Güvenlik | "Önceki talimatları unut…" (prompt injection) | `reddedildi` |
| Güvenlik | "Bugün hava nasıl olacak…" | `kapsam_disi` |
| Sohbet | İki turlu konuşma + "Peki bu durum köpeklerde de aynı mı?" | Bağlamı koruyarak yanıtladı, `ai_aktif=true` |
| Doğrulama | Boş metin / 2000+ karakter / son mesaj kullanıcıya ait değil | Üçü de 422 |
| Eğitim | `/api/retrain` | 200; 2.475 örnek, 55 sınıf |

### 6.3 `python olcum.py` — uçtan uca ölçüm

```
Model: 2475 örnek, 55 sınıf, 9965 özellik, çapraz doğrulama=0.8747

== val (üretilmiş + el yazımı) (n=550) ==
  top-1 doğruluk      : 0.885      top-3 doğruluk : 0.973
  aciliyet (3 sınıf)  : 0.920
  kırmızı yakalama    : 143/150    yeşil→kırmızı yanlış: 4/193

== val — yalnızca el yazımı (n=165) ==
  top-1 doğruluk      : 0.764      top-3 doğruluk : 0.933

== dış test (şablon dışı) (n=110) ==
  top-1 doğruluk      : 0.864      top-3 doğruluk : 0.955

== alakasız 8 cümle == {'kapsam_disi': 8}
```

### 6.4 Frontend ile bütünleşme

| Kontrol | Sonuç |
| --- | --- |
| Vite proxy (`http://localhost:5173/api/health`) | 200 — `ECONNREFUSED` yok |
| `npm run build` (`tsc -b && vite build`) | Hatasız; 95 modül, 310 kB JS (gzip 100 kB) |

Arayüz bağlantıyı 3 saniyede bir yeniden denediği için sayfayı yenilemeye gerek
yoktur; sunucu açıldığında "Bağlantı yok" rozeti kendiliğinden düzelir.

---

## 7. Çalıştırma ve sorun giderme

```powershell
# 1) Backend (tek komut yeterli; veritabanı gerekirse kendiliğinden kurulur)
cd backend
uvicorn main:app --reload

# 2) Frontend (ayrı terminal, kök dizinden)
npm run dev            # http://localhost:5173

# İkisini birlikte:
npm run dev:all

# Yalnızca ön kontrol (pencere açmaz: port boş mu, .env ve node_modules yerinde mi)
.\start.ps1 -Kontrol
```

| Belirti | Yapılacak |
| --- | --- |
| Açılışta yine "no such column" benzeri bir şema hatası | `cd backend && python init_db.py --reset` (tabloyu sıfırlayıp baştan yükler) |
| `ai_aktif: false` ve kayıtlarda `model_bulunamadi` | `backend/.env` içindeki `GEMINI_MODEL` değerini kontrol edin; boş bırakılırsa kod varsayılanı (`gemini-3.8-flash`) kullanılır |
| Arayüzde "BACKEND KAPALI" | Backend terminalindeki son satıra bakın; sunucu kapanmışsa sebebi orada yazar |
| `[WinError 10013] ... bir yuvaya erişilmeye çalışıldı` | 8000 portu başka bir sürecin elinde; bkz. bölüm 8 |

### Eski veritabanı yedeği

Onarımdan önceki 20 sınıflı veritabanı **silinmedi**, şurada duruyor:

```
backend/vetai_eski_20sinif_yedek.db     (105 satır: 101 seed + 4 pending)
```

`.gitignore` içindeki `*.db` kuralı gereği depoya girmez. Geri dönmek gerekirse
bu dosya `backend/vetai.db` olarak kopyalanabilir — ancak eski veri bugünkü
55 sınıflı bilgi tabanıyla uyumlu olmadığı için önerilmez.

---

## 8. Port çakışması — `[WinError 10013]`

### 8.1 Ne oluyordu?

Backend penceresinde şu satır görünüyordu:

```
VetAI Backend - http://127.0.0.1:8000/docs
INFO:     Will watch for changes in these directories: ['C:\Users\Umut\Documents\GitHub\VetAI\backend']
ERROR:    [WinError 10013] Erişim izinlerince izin verilmeyen bir şekilde bir yuvaya erişilmeye çalışıldı
```

Sebep bir izin ya da güvenlik duvarı sorunu değil: **8000 portu zaten başka bir
sürecin elindeydi** (arka planda çalışmaya devam eden bir VetAI sunucusu).
Windows'ta asyncio soketi `SO_EXCLUSIVEADDRUSE` ile açtığı için ikinci bağlanma
denemesi, beklenen "address already in use" (10048) yerine "erişim reddedildi"
(10013) hatası verir; mesaj bu yüzden yanıltıcıdır.

Teşhis komutları:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess
netsh interface ipv4 show excludedportrange protocol=tcp   # ayrılmış aralık var mı?
```

Bu makinede ayrılmış (Hyper-V/WSL) port aralığı yoktu; portu tutan süreç
listede açıkça görünüyordu.

### 8.2 Düzeltme — `start.ps1`

`start.ps1` artık backend penceresini açmadan önce portu denetler ve durumu
anlaşılır biçimde söyler:

```
  8000 portu kullanımda: PID 13540 (python).
  Backend bu yüzden '[WinError 10013]' verip kapanır.

  Zaten çalışan bir VetAI sunucusu olabilir; önce şunu deneyin:
     http://127.0.0.1:8000/api/health
  Yanıt veriyorsa backend ayakta demektir, yeniden başlatmanıza gerek yok.
  Eski süreci kapatmak için:
     Stop-Process -Id 13540
```

* Port doluyken backend penceresi **açılmaz** (açılsa saniyesinde kapanacaktı);
  frontend penceresi normal şekilde açılmaya devam eder.
* 5173 doluysa Vite'ın 5174'e geçeceği önceden bildirilir.
* `.\start.ps1 -Kontrol` hiçbir pencere açmadan yalnızca kontrolleri yapar.
* Dosya UTF-8 BOM ile kaydedildi; Windows PowerShell 5.1 BOM'suz UTF-8'i sistem
  kod sayfası sanıp Türkçe harfleri bozduğu için bu şart.

### 8.3 Kontrol

| Durum | Sonuç |
| --- | --- |
| Port doluyken `.\start.ps1 -Kontrol` | Portu tutan PID ve süreç adı, `Stop-Process` komutu, "sorunlar giderilmeli" |
| Port boşken `.\start.ps1 -Kontrol` | "8000 portu boş" + "her şey hazır" |
| Port boşaltıldıktan sonra backend | Kendi penceresinde açıldı, `127.0.0.1:8000` dinleniyor, `[WinError 10013]` yok |
| `http://127.0.0.1:8000/api/health` | 200; 2.475 örnek, 55 sınıf, Gemini aktif |
| Arayüz üzerinden analiz (Vite proxy, 5174) | 200; "Pankreatit" tahmini ve yapay zekâ yorumu geldi (`ai_aktif: true`) |

---

## 9. Gemini ücretsiz katman kotası

Düzeltmelerin ardından yapılan testler sırasında Gemini şu hatayı dönmeye
başladı:

```
[ERROR] vetai.gemini: Gemini çağrısı başarısız (kota): 429 RESOURCE_EXHAUSTED
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-2.5-flash
```

Bu bir kod hatası değil: `gemini-2.5-flash` ücretsiz katmanda **günde 20 istek**
ile sınırlı ve bu sınır test çağrılarıyla doldu. Kota günlük olarak yenilenir.

Sistemin bu durumdaki davranışı tasarlandığı gibidir:

| Durum | Davranış |
| --- | --- |
| ML tahmini var, Gemini yok | Şablon metinle devam eder (`ai_aktif: false`), yanıtta "Gemini katmanı şu anda devre dışı" uyarısı görünür |
| Ne ML tahmini ne Gemini (örneğin kapsam dışı bir takip sorusu) | `/api/chat` kontrollü biçimde `429` döndürür, arayüz hata balonu gösterir |

`duman_testi.py` bu ayrımı bilir: yapay zekâ yorumu gelmediğinde testi
başarısız saymaz, `[UYARI]` satırı basar.

Ücretsiz katmanda sınırlar modele göre değişiyor (bu anahtarla ölçülen):

| Model | Ücretsiz katman sınırı | Sonuç |
| --- | --- | --- |
| `gemini-2.5-flash` (`.env` değeri) | **günde 20 istek** | Dolduğunda o gün boyunca şablon metne düşer |
| `gemini-3.8-flash` (kod varsayılanı) | **dakikada 5 istek** | Günlük tavan yok; yoğun kullanımda kısa süre bekletir |

Bu yüzden `backend/.env` içindeki `GEMINI_MODEL=gemini-2.5-flash` satırını silmek
(kod varsayılanına, `gemini-3.8-flash`'e dönmek) günlük tıkanmayı ortadan
kaldırır; bölüm 4.3'teki geri çekilme zinciri sayesinde bu model artık sorunsuz
çalışıyor. Anahtarın eriştiği modeller `client.models.list()` ile görülebilir.
Kalıcı çözüm için faturalandırma açıp katman yükseltmek gerekir.
