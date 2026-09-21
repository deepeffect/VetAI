# VetAI — Frontend Yenileme Notları

Bu belge, arayüzün "klişe yapay zekâ" görünümünden (simsiyah zemin, neon yeşil
vurgular, mono yazı tipli sayaçlar) **ferah, adaçayı yeşili odaklı ve minimalist**
bir tasarıma geçişini ve bununla birlikte yapılan Türkçe karakter düzeltmelerini
anlatır.

---

## 1. Özet: ne değişti?

| Önce | Sonra |
| --- | --- |
| Simsiyah zemin (`#0b1120`), neon yeşil (`#10b981`) vurgular | Açık tema varsayılan (`#f4f8f5`), orta tonlu adaçayı yeşili (`#47755c` / `#5a8d71`) |
| Tek tema (koyu, zorunlu) | Açık tema **varsayılan** + yumuşak koyu tema (üst çubuktaki düğmeyle, tercih `localStorage`'a yazılır) |
| Gemini için mor/violet vurgu, parlayan barlar, kırmızı "pulse ring" | Tek vurgu rengi (yeşil) + sakin durum renkleri; parlama/neon efekti yok |
| Sayılar mono yazı tipiyle ("terminal" hissi) | Inter + `tabular-nums`; mono yalnızca gerçek kod/komut için |
| Sıkışık paneller, ince ayraçlar | Bol boşluklu kartlar (`rounded-2xl`, yumuşak gölge, 16px iç boşluk) |
| Türkçe karaktersiz metinler ("Hayvaninizin sikayetini anlatin") | Kusursuz Türkçe ("Hayvanınızın şikâyetini anlatın") |
| Bulgu rozetleri ham NLP token'ı ("nefes darligi") | Ekranda Türkçe etiket ("Nefes darlığı") |

Yeni dosyalar: `frontend/src/lib/turkce.ts`, `frontend/src/lib/tema.ts`,
`backend/migrate_turkce.py`.

---

## 2. Renk paleti (HEX)

### 2.1 Adaçayı (sage) skalası — ana renk

Ne fosforlu ne boğucu; orta tonlu, doğayı ve güveni çağrıştıran bir yeşil.

| Token | HEX | Nerede kullanılır |
| --- | --- | --- |
| `sage-50` | `#f1f6f2` | En açık zemin tonu |
| `sage-100` | `#e0ede4` | Rozet zemini (alternatif) |
| `sage-200` | `#c4dccc` | Ayraç / pasif kenarlık |
| `sage-300` | `#9fc4ad` | Veri dağılımı barları, koyu temada yeşil metin |
| `sage-400` | `#78a88b` | İkincil grafik dolgusu |
| `sage-500` | `#5a8d71` | **Olasılık barı dolgusu**, durum noktası |
| `sage-600` | `#47755c` | **Ana buton zemini**, açık temada yeşil metin |
| `sage-700` | `#3a5f4b` | Buton hover, koyu yeşil metin |
| `sage-800` | `#304c3d` | Derin vurgu |
| `sage-900` | `#283e33` | En koyu yeşil |

### 2.2 Nötr skala (yeşile çalan gri)

Saf gri yerine hafif yeşile çalan nötrler kullanıldı; arayüz böylece soğuk
değil, ılık duruyor.

| Token | HEX |
| --- | --- |
| `stone-50` | `#f7faf8` |
| `stone-100` | `#eef3f0` |
| `stone-200` | `#e2ebe5` |
| `stone-300` | `#c9d5cd` |
| `stone-400` | `#9aa9a0` |
| `stone-500` | `#6e8077` |
| `stone-600` | `#55665c` |
| `stone-700` | `#3f4f46` |
| `stone-800` | `#2a362f` |
| `stone-900` | `#1e2b24` |

### 2.3 Açık tema yüzeyleri (varsayılan)

| Amaç | Değişken | HEX |
| --- | --- | --- |
| Sayfa zemini | `--vt-canvas` | `#f4f8f5` |
| İkincil zemin (segment, kbd) | `--vt-canvas-soft` | `#edf3ef` |
| Kart yüzeyi | `--vt-card` | `#ffffff` |
| Kart içi kutu | `--vt-raised` | `#f7faf8` |
| Kenarlık | `--vt-line` | `#e2ebe5` |
| İnce ayraç | `--vt-line-soft` | `#eef3f0` |
| Ana metin | `--vt-ink` | `#1e2b24` |
| Açıklama metni | `--vt-ink-soft` | `#55665c` |
| Etiket / yardımcı metin | `--vt-ink-muted` | `#6e8077` |
| Dolgu buton | `--vt-accent` | `#47755c` |
| Buton hover | `--vt-accent-hover` | `#3a5f4b` |
| Yeşil metin/ikon | `--vt-accent-ink` | `#47755c` |
| Yeşil rozet zemini | `--vt-accent-soft` | `#e7f1ea` |
| Yeşil rozet kenarlığı | `--vt-accent-line` | `#cfe3d6` |

### 2.4 Yumuşak koyu tema

Simsiyah değil; yeşile çalan koyu bir zemin.

| Amaç | HEX |
| --- | --- |
| Sayfa zemini | `#171f1b` |
| İkincil zemin | `#1c2521` |
| Kart yüzeyi | `#1f2823` |
| Kart içi kutu | `#25302a` |
| Kenarlık | `#303b34` |
| İnce ayraç | `#28332c` |
| Ana metin | `#e8efe9` |
| Açıklama metni | `#a9b8ae` |
| Yardımcı metin | `#8a9a90` |
| Dolgu buton | `#4e8067` |
| Buton hover | `#5a9076` |
| Yeşil metin/ikon | `#9fc4ad` |
| Yeşil rozet zemini | `#26362e` |
| Yeşil rozet kenarlığı | `#364c3f` |

### 2.5 Durum renkleri

Sağlık uygulaması olduğu için acil/uyarı renkleri doygun değil, "kısılmış"
tonlarda: dikkat çekiyor ama paniğe sevk etmiyor.

| Durum | Açık tema | Koyu tema |
| --- | --- | --- |
| Acil — ikon/dolgu | `#c0503f` | `#b8503f` |
| Acil — metin | `#b04437` | `#e5a79c` |
| Acil — zemin | `#fdf2f0` | `#2a1e1c` |
| Acil — kenarlık | `#f2dad5` | `#452924` |
| Uyarı — bar dolgusu | `#c0892f` | `#b8892f` |
| Uyarı — metin | `#9a6516` | `#e0bd84` |
| Uyarı — zemin | `#fbf4e7` | `#2a2419` |
| Uyarı — kenarlık | `#efe0c4` | `#453a26` |

### 2.6 Kontrast (WCAG) kontrolü

Tüm ana metin çiftleri AA eşiğinin (4.5:1) üzerinde:

| Çift | Oran |
| --- | --- |
| Ana metin / sayfa zemini (açık) | 13.7 : 1 |
| Açıklama metni / sayfa zemini (açık) | 5.7 : 1 |
| Beyaz / ana buton (`#47755c`) | 5.3 : 1 |
| Yeşil metin / beyaz kart | 5.3 : 1 |
| Ana metin / kart (koyu) | 13.0 : 1 |
| Yeşil metin / kart (koyu) | 7.9 : 1 |
| Beyaz / ana buton (koyu) | 4.6 : 1 |

---

## 3. Tema mimarisi (Tailwind v4)

Tüm renkler `frontend/src/index.css` içinde tanımlı. Bileşenler **ham renk
kullanmaz**, yalnızca anlamsal sınıfları kullanır (`bg-card`, `text-ink-soft`,
`border-line`, `bg-accent`…). Tema değiştiğinde tek bir CSS değişkeni seti
değişir; bileşenlerde yüzlerce `dark:` sınıfı taşımaya gerek kalmaz.

Yapı üç katmandan oluşur:

```css
/* 1) Koyu mod, <html class="dark"> sınıfına bağlanır (OS tercihine değil) */
@custom-variant dark (&:where(.dark, .dark *));

/* 2) Temadan bağımsız ham palet */
@theme {
  --color-sage-500: #5a8d71;
  --color-sage-600: #47755c;
  --font-sans: "Inter", ui-sans-serif, system-ui, "Segoe UI", …;
}

/* 3) Temaya göre değişen anlamsal değerler */
:root { --vt-canvas: #f4f8f5; --vt-card: #ffffff; --vt-ink: #1e2b24; … }
.dark { --vt-canvas: #171f1b; --vt-card: #1f2823; --vt-ink: #e8efe9; … }

/* 4) Bu değerleri Tailwind sınıflarına bağla.
      "inline" sayesinde değer sabitlenmez, var() olarak kalır. */
@theme inline {
  --color-canvas: var(--vt-canvas);
  --color-card:   var(--vt-card);
  --color-ink:    var(--vt-ink);
  --shadow-soft:  var(--vt-shadow-soft);
}
```

Bunun sonucunda `bg-canvas`, `bg-card`, `text-ink`, `shadow-soft` gibi sınıflar
üretilir ve tema anahtarı çevrildiğinde otomatik olarak yeni değeri alır.

### Tema anahtarı nasıl çalışıyor?

1. `frontend/index.html` içindeki küçük betik, React yüklenmeden önce
   `localStorage`'daki tercihi okuyup `<html>` etiketine `dark` sınıfını ekler.
   Böylece açılışta renk sıçraması (FOUC) olmaz.
2. `frontend/src/lib/tema.ts` içindeki `useTema()` kancası aynı mantığı React
   tarafında yönetir ve seçimi `localStorage`'a yazar.
3. **Varsayılan açık temadır.** Koyu tema yalnızca kullanıcı üst çubuktaki
   ay/güneş düğmesine bastığında açılır.

---

## 4. Tipografi

| Öğe | Değer |
| --- | --- |
| Yazı tipi | `Inter` (Google Fonts), yedek: `system-ui`, `Segoe UI` — Türkçe karakterleri tam destekler |
| Gövde metni | 15px / 1.6 |
| Sohbet metni | 14.5px / 1.75 (`leading-7`) |
| Kart başlığı (hastalık) | 14.5px / 600 |
| Boş ekran başlığı | 26px (mobil) → 30px (masaüstü) / 600 |
| Bölüm etiketi | 11px, `uppercase`, `tracking-[0.06em]`, `text-ink-muted` |
| Sayılar | `.tnum` sınıfı (`font-variant-numeric: tabular-nums`) |
| Başlıklar | `letter-spacing: -0.014em`, `text-wrap: balance` |

Mono yazı tipi yalnızca gerçekten kod olan yerlerde kullanılıyor
(`uvicorn main:app --reload`, `gemini-2.5-flash`).

---

## 5. Sınıf sözlüğü (kopyala-yapıştır)

```jsx
{/* Kart */}
<section className="rounded-2xl border border-line bg-card p-4 shadow-soft">…</section>

{/* Ana buton */}
<button className="rounded-xl bg-accent px-4 py-2 text-white transition-colors
                   hover:bg-accent-hover disabled:bg-line disabled:text-ink-muted">…</button>

{/* Yeşil rozet (bulgu, durum) */}
<span className="rounded-full border border-accent-line bg-accent-soft px-2.5 py-1
                 text-[11.5px] font-medium text-accent-ink">Kusma</span>

{/* Nötr rozet */}
<span className="rounded-full border border-line bg-canvas-soft px-2.5 py-1
                 text-[11.5px] text-ink-muted">Ateş yok</span>

{/* Bölüm etiketi */}
<span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
  Model olasılıkları
</span>

{/* Uyarı kutusu */}
<div className="rounded-lg border border-warn-line bg-warn-soft px-3 py-2.5 text-warn-ink">…</div>

{/* Acil kutusu */}
<div className="rounded-xl border border-danger-line bg-danger-soft p-4 text-danger-ink">…</div>
```

---

## 6. Bileşen bileşen değişiklikler

| Dosya | Değişiklik |
| --- | --- |
| `src/index.css` | Tüm tasarım sistemi: palet, anlamsal token'lar, açık/koyu tema, animasyonlar, odak halkası, kaydırma çubuğu, `prefers-reduced-motion` desteği |
| `index.html` | Türkçe başlık/açıklama, Inter bağlantısı, adaçayı renkli favicon, tema önyükleme betiği, `theme-color` meta etiketleri |
| `src/App.tsx` | Yapışkan (sticky) üst çubuk + tema düğmesi; boş ekran dikeyde ortalanmış ferah bir "hero"; örnek şikâyetler kart biçiminde; yan panel kendi içinde kayan yapışkan sütun; giriş alanının arkası opak (içerik altından sızmıyor) |
| `src/components/ChatBubble.tsx` | Kullanıcı balonu dolu yeşil; asistan yanıtı beyaz kart + yumuşak gölge; hata durumu kısık kırmızı |
| `src/components/Composer.tsx` | Tür seçimi "segmented control"; odakta kenarlık yeşile döner; karakter sayacı `tnum`; `Enter/Shift+Enter` ipuçları sadeleşti |
| `src/components/AnalysisResult.tsx` | Yapay zekâ yorumu artık kutu içinde değil, yanıtın ana gövdesi; acil uyarısı sakin ama net; bulgu rozetleri Türkçe etiketli, "(yok)" bulguları nötr renkte |
| `src/components/DiseaseCard.tsx` | İlk tahmin yumuşak yeşil zeminle vurgulu; destekleyen ifadeler Türkçeleştirilmiş sade rozetler |
| `src/components/ProbabilityBar.tsx` | Parlama (glow) kaldırıldı; yüksek = yeşil, orta = amber, düşük = nötr; yüzde `tnum` ile |
| `src/components/StatusPanel.tsx` | Her bölüm ayrı kart; satırlar ince ayraçlarla; "Yükleniyor…" durumu; backend kapalıyken net kurtarma talimatı |
| `src/components/Icons.tsx` | Ortak çizgi ayarları tek yerde; `ShieldIcon`, `SunIcon`, `MoonIcon` eklendi; `ChartIcon` sadeleşti |
| `src/lib/tema.ts` | **Yeni.** Açık/koyu tema kancası |
| `src/lib/turkce.ts` | **Yeni.** NLP token'larını ekranda Türkçe etikete çeviren sözlük |

---

## 7. Türkçe karakter düzeltmeleri

### 7.1 Arayüz (frontend)

Tüm görünen metinler yeniden yazıldı. Örnekler:

| Önce | Sonra |
| --- | --- |
| `Hayvaninizin sikayetini anlatin` | `Hayvanınızın şikâyetini anlatın` |
| `Cevrimici` | `Çevrim içi` |
| `Egitim ornegi` / `Hastalik sinifi` | `Eğitim örneği` / `Hastalık sınıfı` |
| `TF-IDF ozelligi` / `Capraz dogrulama` | `TF-IDF özelliği` / `Çapraz doğrulama` |
| `Yapay zeka` | `Yapay zekâ` |
| `Devre disi` / `Onay bekleyen` | `Devre dışı` / `Onay bekleyen` |
| `Kopek` | `Köpek` |
| `Sikayeti yazin. Ornek: …` | `Şikâyeti yazın. Örnek: …` |
| `Ne yapmali` | `Ne yapmalı` |

### 7.2 Bulgu etiketleri — neden ayrı bir sözlük var?

`backend/nlp_engine.py`, TF-IDF tutarlılığı için tüm metni ASCII'ye katlar
("kaşıntı" ve "kasinti" aynı token'ı üretsin diye). Bu yüzden API bize
`nefes_darligi`, `istahsizlik` gibi **teknik token'lar** döner. Bu token'lar
modelin eğitim verisiyle eşleştiği için değiştirilemez.

Çözüm: `frontend/src/lib/turkce.ts` içinde 54 kanonik token için ekran etiketi
sözlüğü. Çeviri yalnızca görüntüleme anında yapılır, modele dokunulmaz:

```ts
bulguyuCoz("nefes darligi") // → { etiket: "Nefes darlığı", olumsuz: false }
bulguyuCoz("ates (yok)")    // → { etiket: "Ateş yok",      olumsuz: true  }
terimEtiketi("istahsizlik") // → "İştahsızlık"
```

Sözlükte olmayan bir token gelirse ham hâli okunabilir biçimde gösterilir;
arayüz bozulmaz.

### 7.3 Backend'de düzeltilen kullanıcıya görünen metinler

| Dosya | Ne düzeltildi |
| --- | --- |
| `backend/init_db.py` | 20 hastalık adı ve 20 öneri metni (`Dis Parazit Enfestasyonu` → `Dış Parazit Enfestasyonu`, `Kronik Bobrek Yetmezligi` → `Kronik Böbrek Yetmezliği`, `Idrar Yolu Tikanikligi (FLUTD)` → `İdrar Yolu Tıkanıklığı (FLUTD)` …) |
| `backend/main.py` | Tüm `mesaj`, `ai_yorum`, `uyarilar` metinleri; 14 acil durum gerekçesi (`Bilinc kaybi` → `Bilinç kaybı`); şablon yorum metni |
| `backend/gemini_api.py` | Sistem talimatı düzgün Türkçe'ye çevrildi ve **"Türkçe karakterleri eksiksiz kullan"** kuralı eklendi; istem şablonları ve hata metinleri düzeltildi |

`main.py` içinde küçük ama önemli bir ayrıntı: şablon yorumda kullanılan
`acil_gerekce.lower()` çağrısı `turkish_lower()` ile değiştirildi. Python'un
standart `lower()` fonksiyonu `"İdrar"` kelimesini `"i̇drar"` (birleşik noktalı i)
hâline getirir; `turkish_lower()` doğru sonucu verir.

### 7.4 Veritabanı migrasyonu

Hastalık adları ve öneri metinleri SQLite'ta saklandığı için `init_db.py`'yi
düzeltmek mevcut kayıtları değiştirmez (`init_db.py` yalnızca boş tabloyu
doldurur). Bunun için `backend/migrate_turkce.py` eklendi:

```bash
cd backend
python migrate_turkce.py
```

Betik yalnızca `UPDATE` çalıştırır; hiçbir kayıt silinmez, canlı öğrenme ile
eklenmiş satırlar korunur, birden fazla kez çalıştırmak güvenlidir.
**Bu depodaki `vetai.db` üzerinde çalıştırıldı:** 105 kaydın tamamı korunarak
62 kaydın hastalık adı, 105 kaydın öneri metni güncellendi.

Hastalık adı aynı zamanda modelin etiketi olduğu için migrasyondan sonra
backend yeniden başlatılmalı (veya `POST /api/retrain` çağrılmalı).

### 7.5 Bilinçli olarak ASCII kalanlar

Bunlar **hata değil**, tasarım gereğidir:

- **NLP token'ları** (`nefes_darligi`, `istahsizlik`): TF-IDF sözlüğünün
  anahtarları. Türkçeleştirilirse mevcut eğitim verisiyle eşleşme bozulur.
- **Kod tanımlayıcıları ve API alan adları** (`hastalik`, `olasilik`,
  `aciklayici_kelimeler`, `tur: "kopek"`): frontend ile backend şeması birebir
  eşleşmeli; JSON anahtarlarında Türkçe karakter kullanılmaz.
- **Eğitim cümleleri** (`init_db.py` içindeki `ORNEKLER`) ve **backend kod
  yorumları**: hiçbir zaman ekranda gösterilmez, NLP zaten ASCII'ye katlar.
  İstenirse ayrıca düzeltilebilir.

---

## 8. Yeni bir bileşen eklerken

1. **Ham renk yazma.** `#ffffff`, `bg-emerald-500` gibi değerler yerine anlamsal
   sınıfları kullan: `bg-card`, `text-ink`, `border-line`, `bg-accent`.
2. **Kart iskeleti** hazır: `rounded-2xl border border-line bg-card p-4 shadow-soft`.
3. **Metin hiyerarşisi:** başlık `text-ink`, açıklama `text-ink-soft`, etiket
   `text-ink-muted`. Üçünden fazla ton kullanma.
4. **Sayı gösteriyorsan** `tnum` sınıfını ekle.
5. **Yeni renk gerekiyorsa** önce `:root` ve `.dark` bloklarına `--vt-*`
   değişkenini ekle, sonra `@theme inline` içinde Tailwind'e bağla. Tek yerde
   tanımla, iki temada da tanımla.
6. **Türkçe metin** doğrudan JSX içine yazılır; backend'den gelen NLP token'ları
   için `lib/turkce.ts` sözlüğünü kullan.
7. Erişilebilirlik: tıklanabilir öğelere `aria-label`, durum değiştiren
   düğmelere `aria-pressed`/`aria-expanded`, süslemelik ikonlara
   `aria-hidden="true"`.

---

## 9. Çalıştırma ve doğrulama

```bash
# Backend
cd backend
python migrate_turkce.py          # yalnızca bir kez, eski veritabanı için
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173
npm run build                     # tsc + vite build (hatasız derleniyor)
```

Yapılan görsel doğrulamalar (başsız Chrome ile, gerçek backend'e bağlı):

- Açık tema, boş ekran — 1440px
- Açık ve koyu tema, tam analiz sonucu (Gemini yorumu + 3 tahmin + öneri)
- Acil durum akışı (acil uyarısı + ilaç dozu uyarısı + kısık kırmızı/amber renkler)
- Mobil 400px: yatay taşma yok (`scrollWidth === clientWidth === 400`)

---

## 10. Sonraki adımlar (öneri)

- `ORNEKLER` eğitim cümleleri ve backend kod yorumları da Türkçe karakterlere
  çevrilebilir (işlevsel etkisi yok, tutarlılık için).
- Yan panel şu an yalnızca `lg` ve üzeri genişlikte görünüyor; mobil için
  açılır bir "Sistem durumu" sayfası eklenebilir.
- Sohbet geçmişi `localStorage`'a yazılarak sayfa yenilendiğinde korunabilir.
- Analiz sonucunu paylaşmak/yazdırmak için sade bir "PDF'e aktar" görünümü
  eklenebilir.
