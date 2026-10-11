# Chatbot / LLM + Veri Seti — Açık İşler

Branch'ler: `feature/chatbot-llm` (sohbet), `feature/dataset-v1` (veri seti, sohbetin üzerine)
Son güncelleme: 2026-09-27

Tamamlananlar aşağıda işaretli; yapılamayanların nedeni yanında yazıyor.

---

## 1. Canlı Gemini testleri (anahtar gerekiyor)

Kod tarafı hazır; makinede `backend/.env` ve API anahtarı olmadığı için gerçek
model request-response testleri **hâlâ çalıştırılamadı**.

```powershell
cd backend
copy .env.example .env          # GEMINI_API_KEY=<anahtar> yaz
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_db.py --reset
python gemini_api.py            # tek atımlık duman testi
uvicorn main:app --reload
```

- [ ] **TEST 1** — "Merhaba" → anlamlı Türkçe yanıt
- [ ] **TEST 2** — "Bana bu sistemin nasıl çalıştığını açıkla." → Gemini yanıtı
- [ ] **TEST 3** — "TEKNOFEST kriterlerini üç madde halinde açıkla." ardından
      "İkinci maddeyi detaylandır." → ikinci yanıt önceki listeye atıf yapmalı
      (guardrail artık takip sorusunu "kapsam dışı" sayıp Gemini'ye bırakıyor; doğrulandı)
- [ ] **TEST 8** — `GEMINI_MODEL=olmayan-model` → "Gemini modeli bulunamadı" balonu, crash yok.
      Google 404 yerine 400 dönerse `gemini_api._hata_siniflandir` 400 dalını güncelle.
- [ ] **TEST 9** — Arka arkaya iki mesaj: ikinci mesaj yanıt gelmeden gönderilemez
- [ ] **TEST 12** — Şikâyet mesajı → analiz kartındaki metin Gemini'den (`ai_aktif: true`)
- [ ] Şikâyet sonrası takip sorusu ("Evde ne yapabilirim?") → önceki tahminlere göre
      yanıt, yeni hastalık adı uydurmuyor
- [ ] Gemini Markdown/liste döndürdüğünde arayüz düzgün
- [ ] Yanıt süresi notu; yavaşsa `GEMINI_MODEL=gemini-3.5-flash-lite`

## 2. Sistem promptu ince ayarı (canlı testten sonra)

Dosya: `backend/chat_service.py` → `SOHBET_TALIMATI`

- [ ] Yanıtlar uzunsa kelime sınırını ya da `max_output_tokens` değerini düşür
- [ ] Alan dışı sorularda çok dağılıyorsa 4. kuralı sıkılaştır
- [ ] Analiz bağlamı verildiğinde model listeyi tekrar etmek yerine yorumluyor mu?
- [ ] Bağlama `aciliyet` düzeyi ve `aciliyet_bayraklari` da eklenebilir
      (`gemini_api.analiz_baglami` şu an yalnızca kırmızı/değil bilgisini taşıyor)

## 3. Veri seti — yapıldı / kaldı

Veri seti v1 paketinin kalan işleri ve görev dağılımı: `VERI_SETI_TODO.md` (2026-10-11).

- [x] Veri seti v1 `backend/data/` altına alındı, `init_db.py` CSV'den yüklüyor
- [x] Kök tabanlı guardrail (`bilgi/kokler.py`), kapsama %43 → %99,5
- [x] Kısa kök kelime-başı kuralı ve basit olumsuzlama eklendi
      ("İkinci maddeyi detaylandır" artık kapsam dışı, "ateşi yok" düşürülüyor)
- [x] Aciliyet: 57 regex + hastalık temel aciliyeti, kırmızı yakalama %20 → %95
- [x] Tür token'ı + tür filtresi, marj tabanlı kararsızlık
- [x] İnsan sağlığı guardrail'i hayvan sözcüğü yoksa belirtiden önce çalışıyor
      ("benim başım ağrıyor ateşim var" → kapsam dışı)
- [x] `olcum.py` ile val (550) ve dış test (110) ölçümleri; sonuçlar README'de
- [ ] **Veteriner hekim incelemesi**: 55 hastalıklı bilgi tabanı, özellikle
      `evde` / `kacin` metinleri ve aciliyet düzeyleri (`data/oneriler.json`,
      `data/hastalik_aciliyet.json`)
- [ ] **Gerçek cümle toplama**: çevreden 150–200 gerçek şikâyet; `olcum.py`'ye
      üçüncü küme olarak eklenip ölçülmeli (beklenen top-1 ~%70)
- [ ] `frontend/src/lib/turkce.ts` içindeki elle yazılmış `BULGU_ETIKETLERI`
      artık gerekmiyor (backend kanonik ad döndürüyor); sadeleştirilebilir
- [ ] `migrate_turkce.py` eski şemaya ait; silinebilir
- [ ] Negasyon aciliyet regex'lerinde ele alınmıyor; kullanıcıya bayraklar gösteriliyor,
      ileride `nlp_engine` `yok_` token'larıyla bayrak düşürme eklenebilir

## 4. İsteğe bağlı iyileştirmeler

- [ ] Streaming yanıt (`generate_content_stream` + SSE)
- [ ] Sohbet kalıcılığı (`localStorage` ya da backend oturumu)
- [ ] RAG: `vetai_bilgi_tabani.json` → retriever → `chat_service.baglam_olustur()`
- [ ] `/api/chat` için istemci başına rate limit (herkese açık dağıtımda şart)
- [ ] Lint yapılandırması (ESLint / ruff); şu an tek kontrol `tsc -b`
- [ ] HawkScan güvenlik taraması (`HAWK_API_KEY` yoktu)

## 5. Merge öncesi

- [ ] Canlı Gemini testleri geçti
- [ ] `npm run build` ve `python olcum.py` hatasız (2026-09-27 itibarıyla geçiyor)
- [ ] PR sırası: `feature/chatbot-llm` → `Frontend`, ardından `feature/dataset-v1` → `Frontend`
      (branch'ler `main`'den değil `Frontend`'den açıldı; güncel tema orada)
- [ ] `backend/.env` ve `vetai.db` commit'e girmedi (gitignore'da)
- [ ] Eski `vetai.db` olan makinelerde `python init_db.py --reset` çalıştırılmalı
