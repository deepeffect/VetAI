# Kaggle çapraz kontrolü — VERI_SETI_TODO §3

*VetAI · 12.10.2026 · Kaynak: `vetai_veri_paketi_v1_2 · veri/animal_disease_prediction_kedi_kopek.csv` (147 satır: 75 köpek, 72 kedi; 48 farklı hastalık adı)*

**Yöntem.** Kaggle tablosundaki 48 hastalık adının her biri, bilgi tabanımızdaki 55 hastalık id'siyle (`ad_en` alanı üzerinden) elle eşlendi; aynı hastalığın farklı yazımları (ör. "Parvovirus" / "Canine Parvovirus") birleştirildi. Tablo İngilizce ve yalnız belirti kolonlarından oluştuğu için **cümle üretiminde kullanılmadı**; yalnız kapsam kontrolü için okundu.

## Eşleşme tablosu (bizde karşılığı olanlar: 130 satır)

| Kaggle adı (yazımlar birleştirildi) | Satır | Bizdeki id | Not |
|---|---:|---|---|
| Canine Parvovirus, Parvovirus | 21 | parvovirus | |
| Canine Distemper, Distemper | 12 | distemper | |
| Feline Calicivirus, Feline Herpesvirus, Feline (Viral) Rhinotracheitis, (Feline) Upper Respiratory Infection, Feline Respiratory Disease Complex, Feline Respiratory Infection | 30 | kedi_nezlesi | Hepsi aynı kedi üst solunum yolu kompleksi |
| Feline Chlamydia, Feline Chlamydiosis | 2 | kedi_nezlesi / konjunktivit | Chlamydia felis daha çok göz tutar |
| Kennel Cough, Bordetella Infection, Canine Cough | 11 | kulube_oksurugu | |
| Gastroenteritis | 9 | akut_gastroenterit | 8 köpek, 1 kedi |
| Feline Infectious Peritonitis | 8 | fip | |
| Feline Coronavirus | 1 | fip (kısmen) | Koronavirüs çoğu kedide zararsız; FIP onun mutasyonu |
| Feline Leukemia (Virus), Feline Immunodeficiency Virus | 9 | felv_fiv | |
| (Feline) Panleukopenia (Virus) | 7 | panlokopeni | |
| Pancreatitis | 4 | pankreatit | 2 köpek, 2 kedi |
| Feline Asthma | 3 | kedi_astimi | |
| Intestinal Parasites | 2 | bagirsak_parazitleri | |
| Fungal Infection | 2 | dermatofitoz (kısmen) | Tanım belirsiz; kedide en olası deri mantarı |
| Ringworm | 1 | dermatofitoz | |
| Tick-Borne Disease | 1 | kene_hastaliklari | |
| Lyme Disease | 2 | kene_hastaliklari (kısmen) | Kaydımız Ehrlichia/Babesia/Anaplasma'yı kapsıyor, Borrelia'yı değil; Türkiye'de nadir |
| Arthritis | 1 | osteoartrit | |
| Conjunctivitis | 1 | konjunktivit | |
| Inflammatory Bowel Disease | 1 | kronik_enteropati | |
| Feline Renal Disease | 1 | kronik_bobrek | |
| Hyperthyroidism | 1 | hipertiroidi | |

## Bizde olmayanlar (17 satır)

| Kaggle adı | Satır | Durum |
|---|---:|---|
| Canine Leptospirosis, Leptospirosis | 7 | **Yeni hastalık adayı (veteriner onayında)**: `leptospiroz`. Tamamı köpek |
| Canine Hepatitis, Canine Infectious Hepatitis | 4 | Aşıyla nadir; "diğer" listesinde. |
| Heartworm Disease, Canine Heartworm Disease | 2 | Zaten yeni hastalık adayı (veteriner onayında): `kalp_kurdu`. |
| Chronic Bronchitis (köpek) | 1 | Kısmen `kulube_oksurugu` ile karşılanıyor; ayrı sınıf gerekmez |
| Canine Flu, Canine Influenza | 2 | Kısmen `kulube_oksurugu` (CIRDC kompleksi) ile karşılanıyor |
| Allergic Rhinitis (köpek) | 1 | Düşük öncelik |
| *Lyme Disease* | *(2)* | *Yukarıda "kısmen" eşlendi, sayıya dahil değil* |

## Sonuç

1. Kaggle alt kümesindeki 147 satırın 130'u (%88; Lyme ve koronavirüs kısmen) mevcut 55 hastalıkla karşılanıyor. Eksik kalan tek anlamlı grup **leptospiroz**: 7 satırla Kaggle'daki en sık eksik hastalık. Leptospiroz ve kalp kurdu artık aday kayıt olarak hazır; ikisi de veteriner onayı bekliyor.
2. Geri kalan eksikler (köpek hepatiti 4, grip/bronşit 3, alerjik rinit 1) ya aşıyla nadir ya da mevcut sınıflarca kısmen karşılanıyor. Yeni sınıf önerilmiyor; "diğer" listesinde izlenecek. Kaggle tablosu küçük ve kaynağı belirsiz olduğundan **sıklık kanıtı sayılmamalı**.
