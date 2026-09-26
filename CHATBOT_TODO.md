# Chatbot / LLM — Sonraki Adımlar

Branch: `feature/chatbot-llm`
Son güncelleme: 2026-09-26

Bu belge, chatbot entegrasyonu tamamlandıktan sonra **henüz yapılmamış** ya da
**doğrulanmamış** işleri listeler. Yapılanların özeti için `README.md` içindeki
"Sohbet akışı" bölümüne bakın.

---

## 1. Canlı Gemini testleri (ZORUNLU, anahtar gerekiyor)

Kod tarafı hazır; makinede API anahtarı olmadığı için gerçek model
request-response testleri **çalıştırılamadı**.

### Hazırlık

```powershell
cd backend
copy .env.example .env          # zaten varsa atla
# .env içine GEMINI_API_KEY=<anahtar> yaz (https://aistudio.google.com/apikey)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # google-genai 2.25.0 + truststore
python init_db.py                # veritabanı boşsa
python gemini_api.py             # tek atımlık hızlı duman testi
uvicorn main:app --reload
```

Ayrı terminalde: `cd frontend; npm run dev`

### Kontrol listesi

- [ ] **TEST 1** — "Merhaba" → anlamlı Türkçe yanıt geliyor mu?
- [ ] **TEST 2** — "Bana bu sistemin nasıl çalıştığını açıkla." → Gemini yanıt veriyor mu?
- [ ] **TEST 3** — "TEKNOFEST kriterlerini üç madde halinde açıkla." ardından
      "İkinci maddeyi detaylandır." → ikinci yanıt önceki listeye atıf yapıyor mu?
- [ ] **TEST 8** — `.env` içinde `GEMINI_MODEL=olmayan-model` ile başlat →
      arayüzde "Gemini modeli bulunamadı: '…'" hata balonu çıkmalı, crash olmamalı.
      (Google 404 yerine 400 dönerse `gemini_api._hata_siniflandir` içindeki
      400 dalını mesaja göre güncelle.)
- [ ] **TEST 9** — Arka arkaya iki mesaj: ikinci mesaj birinci yanıt gelmeden
      gönderilemiyor olmalı (buton pasif); sıra user/assistant/user/assistant.
- [ ] **TEST 12** — Şikâyet mesajı ("Kedim iki gündür kusuyor…") → analiz
      kartındaki metin Gemini'den geliyor (`ai_aktif: true`, model rozeti görünür).
- [ ] Şikâyet sonrası takip sorusu ("Evde ne yapabilirim?") → önceki tahminlere
      göre yanıt veriyor mu, yeni hastalık adı uydurmuyor mu?
- [ ] Gemini Markdown/liste döndürdüğünde arayüzde düzgün görünüyor mu?
- [ ] Yanıt süresi: `thinking_level=MINIMAL` ile ortalama gecikmeyi not et.
      Yavaşsa `GEMINI_MODEL=gemini-3.5-flash-lite` dene.

---

## 2. Sistem promptu ince ayarı (canlı testten sonra)

Dosya: `backend/chat_service.py` → `SOHBET_TALIMATI`

- [ ] Yanıtlar çok uzunsa "60-180 kelime" sınırını düşür ya da
      `gemini_api.sohbet(max_output_tokens=…)` değerini azalt.
- [ ] Model alan dışı sorularda çok kolay dağılıyorsa 4. kuralı sıkılaştır.
- [ ] Analiz bağlamı verildiğinde model listeyi tekrar etmek yerine yorumluyor mu?
      Gerekirse `baglam_olustur` içindeki son cümleyi düzenle.

---

## 3. Bilinen / önceden var olan sorunlar

- [ ] **İnsan sağlığı guardrail'i**: "benim başım ağrıyor ateşim var" gibi
      cümlelerde "ateş" alan terimi olduğu için `INSAN_KALIPLARI` devreye
      girmiyor, ML analizi çalışıyor. `main.py` GUARDRAIL 3 mantığı gözden
      geçirilmeli (ör. insan kalıbı eşleşiyorsa alan kontrolünü atla).
- [ ] **Model kararsızlığı**: 101 örnekle çapraz doğrulama ~%53. Bu chatbot
      işi değil, veri seti işi; `init_db.py` seed verisi genişletilmeli.
- [ ] **Norton / TLS**: `truststore` ile çözüldü ama farklı bir makinede
      `CERTIFICATE_VERIFY_FAILED` görülürse önce `pip install truststore`
      yapıldığından emin ol.

---

## 4. İsteğe bağlı iyileştirmeler (kapsam dışı bırakıldı)

- [ ] **Streaming yanıt**: `client.models.generate_content_stream` + SSE.
      Şu an tek parça yanıt; UX için "yazıyor" efekti yeterli görüldü.
- [ ] **Sohbet kalıcılığı**: Sayfa yenilenince sohbet sıfırlanıyor.
      İstenirse `localStorage` (tema ile aynı yöntem) ya da backend oturumu.
- [ ] **RAG / dataset**: Hazır veri seti yok. Eklenecekse yalnızca
      `chat_service.baglam_olustur()` içine bir retriever bloğu koymak yeterli;
      UI ve API katmanı değişmez.
- [ ] **Hız sınırı**: `/api/chat` için istemci başına rate limit yok
      (ör. `slowapi`). Herkese açık dağıtımda gerekli.
- [ ] **Lint**: Projede ESLint/ruff yapılandırması yok; `tsc -b` tek kontrol.
- [ ] **Güvenlik taraması**: HawkScan `HAWK_API_KEY` olmadığı için çalıştırılmadı.

---

## 5. Merge öncesi

- [ ] Yukarıdaki canlı testler geçti.
- [ ] `npm run build` ve `python -c "import main"` (backend klasöründe) hatasız.
- [ ] `git push -u origin feature/chatbot-llm` → PR hedefi **`Frontend`**
      (branch `main`'den değil `Frontend`'den açıldı; güncel tema orada).
- [ ] `backend/.env` ve `vetai.db` commit'e girmedi (gitignore'da) — kontrol et.
