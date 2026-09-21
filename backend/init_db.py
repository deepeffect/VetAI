"""Veritabanını oluşturur ve başlangıç (seed) eğitim verisini yükler.

Kullanim:
    python init_db.py           # tablo yoksa oluştur, veri yoksa doldur
    python init_db.py --reset   # tabloyu sıfırla ve baştan doldur

Veri seti bilinçli olarak "her hastalık için aynı şikâyetin farklı söyleyişlerini"
içerir; Logistic Regression'ın ezber yerine dil kalıplarını öğrenmesi için
sınıf başına en az 4-5 varyasyon gerekir.
"""

from __future__ import annotations

import argparse

from database import Base, KAYNAK_SEED, Symptom, engine, get_session, init_database

# --------------------------------------------------------------------------
# Hastalık başına sabit tavsiye metni (tabloda `oneri` kolonuna yazılır)
# --------------------------------------------------------------------------
ONERILER: dict[str, str] = {
    "Gastroenterit": (
        "12 saat katı gıda verilmeyip temiz suya erişim sağlanmalı, ardından 2-3 gün "
        "az yağlı/haşlanmış tavuk-pirinç gibi hafif bir diyete geçilmelidir. Kusma 24 "
        "saati aşarsa, dışkıda kan varsa veya hayvan su içemiyorsa dehidrasyon riski "
        "nedeniyle aynı gün veteriner kontrolü gerekir."
    ),
    "Parvoviral Enterit": (
        "ACİL. Özellikle aşısı tamamlanmamış yavrularda öldürücü seyreder. Evde tedavi "
        "denenmemeli; hayvan derhal en yakın veteriner kliniğine götürülmelidir. "
        "Yoğun sıvı desteği ve izolasyon gerekir, virüs diğer köpeklere çok bulaşıcıdır."
    ),
    "Üst Solunum Yolu Enfeksiyonu": (
        "Hayvan sıcak ve cereyansız bir ortamda tutulmalı, burun çevresi nemli bezle "
        "temizlenmeli, ısıtılmış kokulu mama ile iştahı desteklenmelidir. Gözde yoğun "
        "akıntı, nefes darlığı veya 48 saatten uzun iştahsızlık varsa veterinere gidilmelidir."
    ),
    "Dış Parazit Enfestasyonu": (
        "Tüyler pire tarayıcısıyla kontrol edilmeli, yatak ve tekstil yüksek sıcaklıkta "
        "yıkanmalıdır. Veteriner önerisiyle uygun kilo/tür için ruhsatlı dış parazit "
        "damlası uygulanmalı; kedilere asla köpek için üretilmiş ürün kullanılmamalıdır."
    ),
    "Mantar Enfeksiyonu (Dermatofitoz)": (
        "Lezyonlar insana da bulaşabileceği için temas sonrası eller yıkanmalıdır. "
        "Bölge kuru tutulmalı, hayvanın yalamasını önlemek için gerekirse yaka takılmalıdır. "
        "Kesin tanı için veterinerde lamba muayenesi ve kültür yapılması gerekir."
    ),
    "Kulak Enfeksiyonu (Otitis)": (
        "Kulak kanalına pamuklu çubuk sokulmamalıdır. Veterinerin önereceği kulak "
        "temizleme solüsyonu dışında evde madde damlatılmamalı; kulak zarı delikse "
        "bazı damlalar kalıcı hasar verir. Koku ve koyu akıntı varsa muayene şarttır."
    ),
    "İdrar Yolu Tıkanıklığı (FLUTD)": (
        "ACİL. Özellikle erkek kedilerde idrar yapamama 24-48 saat içinde öldürücüdür. "
        "Karın bölgesine baskı uygulanmamalı, hayvan vakit kaybetmeden veterinere "
        "götürülmelidir. Sonda ile idrar boşaltımı gerekebilir."
    ),
    "Diş Eti İltihabı (Gingivitis)": (
        "Sert kemik ve çok sert ödül verilmemeli, hayvana özel diş macunu ile düzenli "
        "fırçalama alışkanlığı kazandırılmalıdır. İnsan diş macunu toksiktir. İleri tartar "
        "birikiminde veterinerde anestezi altında diş temizliği gerekir."
    ),
    "Kronik Böbrek Yetmezliği": (
        "Suya erişim artırılmalı, mümkünse su çeşmesi ve yaş mama tercih edilmelidir. "
        "Tanı ancak kan ve idrar tahlili ile konur. Erken teşhiste böbrek destek maması "
        "ile yaşam süresi belirgin uzar; vakit kaybetmeden tahlil yaptırılmalıdır."
    ),
    "Diabetes Mellitus": (
        "Su ve mama tüketimi ile idrar miktarı günlük not edilmelidir. Tanı kan şekeri "
        "ve fruktozamin testi ile konur. Tedavi insülin ve sabit öğün düzeni gerektirir; "
        "kendi kendine insülin dozu ayarlanmamalıdır."
    ),
    "İç Parazit (Solucan)": (
        "Dışkıda pirinç tanesi benzeri halkalar aranmalı, mama kabı ve tuvalet alanı "
        "günlük temizlenmelidir. Veteriner önerisiyle kiloya uygun iç parazit ilacı "
        "verilmeli ve 2-3 hafta sonra tekrarlanmalıdır."
    ),
    "Eklem/Kalça Rahatsızlığı": (
        "Kaygan zeminlere halı serilmeli, merdiven ve yükseğe atlama sınırlandırılmalı, "
        "fazla kilo varsa diyetle azaltılmalıdır. İnsan ağrı kesicileri (parasetamol, "
        "ibuprofen) hayvanlar için öldürücüdür, kesinlikle verilmemelidir."
    ),
    "Zehirlenme": (
        "ACİL. Veteriner söylemeden kusturma denenmemeli, süt/yağ verilmemelidir. "
        "Yenilen maddenin ambalajı yanına alınarak hayvan derhal kliniğe götürülmelidir. "
        "İlk 1-2 saat mide boşaltımı için kritik zaman aralığıdır."
    ),
    "Alerjik Dermatit": (
        "Son değişen mama, tasma, şampuan veya temizlik ürünü gözden geçirilmelidir. "
        "Bölge serin suyla yıkanabilir; kaşımayı önlemek için yaka kullanılmalıdır. "
        "Tekrarlayan olgularda veterinerde alerji testi ve diyet denemesi yapılır."
    ),
    "Konjonktivit": (
        "Gözler dışarıdan içeriye doğru steril serum fizyolojik ile temizlenebilir. "
        "Kortizonlu damlalar kornea yarası varsa durumu ağırlaştırır; veteriner "
        "görmeden damla kullanılmamalıdır."
    ),
    "Kennel Cough (Bulaşıcı Trakeobronşit)": (
        "Tasma yerine göğüs tasması kullanılarak gırtlak basıncı azaltılmalı, hayvan "
        "diğer köpeklerden uzak tutulmalıdır. Öksürük 1 haftayı aşar, iştahsızlık veya "
        "ateş eklenirse zatürre riski nedeniyle veterinere gidilmelidir."
    ),
    "Sıcak Çarpması": (
        "ACİL. Hayvan gölgeye alınıp vücudu ILIK suyla (buzlu su damar büzülmesi yaptığı "
        "için değil) yavaşça soğutulmalı ve derhal veterinere götürülmelidir. İç organ "
        "hasarı dışarıdan görülmese de saatler sonra ortaya çıkabilir."
    ),
    "Kabızlık": (
        "Su tüketimi artırılmalı, yaş mamaya geçilmeli, kedilerde tüy yumağı için malt "
        "verilebilir. 48 saatten uzun dışkı yapamama, kusma ile birlikteyse tıkanıklığı "
        "düşündürür ve veteriner muayenesi gerektirir."
    ),
    "Epileptik Nöbet": (
        "ACİL. Nöbet sırasında ağza el veya cisim sokulmamalı, hayvan sadece sert "
        "cisimlerden uzaklaştırılmalı ve nöbetin süresi ölçülmelidir. 3 dakikayı aşan "
        "veya art arda gelen nöbetlerde vakit kaybetmeden kliniğe gidilmelidir."
    ),
    "Kene Kaynaklı Enfeksiyon": (
        "Kene, cımbızla deriye en yakın noktadan çevrilmeden düz çekilerek çıkarılmalı, "
        "elle ezilmemelidir. Ateş, halsizlik ve iştahsızlık varsa kan parazitleri için "
        "kan testi gerekir; tedavi gecikirse kansızlık gelişebilir."
    ),
}

# --------------------------------------------------------------------------
# Eğitim örnekleri: (tür, semptom metni, hastalık)
# --------------------------------------------------------------------------
ORNEKLER: list[tuple[str, str, str]] = [
    # --- Gastroenterit ---
    ("genel", "kedim iki gundur kusuyor ve ishali var, mama yemiyor", "Gastroenterit"),
    ("kopek", "kopegim surekli kusuyor sulu diski yapiyor ve halsiz", "Gastroenterit"),
    ("kedi", "kedim istifra ediyor ve karni guruldiyor, istahsiz", "Gastroenterit"),
    ("genel", "sabahtan beri kusma ve yumusak diski var, durgun duruyor", "Gastroenterit"),
    ("kopek", "cop karistirdi sonrasinda kusma ve ishal basladi", "Gastroenterit"),
    ("kedi", "kedi kusuyor istahsizlik var ates yok", "Gastroenterit"),

    # --- Parvoviral Enterit ---
    ("kopek", "yavru kopegim kanli ishal yapiyor ve surekli kusuyor cok halsiz", "Parvoviral Enterit"),
    ("kopek", "asisi yapilmamis enik kanli diski ve agir kusma, ayaga kalkamiyor", "Parvoviral Enterit"),
    ("kopek", "kopek yavrusu pis kokulu kanli ishal, su icmiyor ve bitkin", "Parvoviral Enterit"),
    ("kopek", "iki aylik kopegim kanli ishal kusma ve atesi var", "Parvoviral Enterit"),
    ("kopek", "yavru kopekte siddetli kanli surgun ve halsizlik", "Parvoviral Enterit"),

    # --- Ust Solunum Yolu Enfeksiyonu ---
    ("kedi", "kedim hapsiriyor burnu akiyor ve gozleri sulaniyor", "Üst Solunum Yolu Enfeksiyonu"),
    ("kedi", "surekli hapsirik burun akintisi ve istahsizlik var", "Üst Solunum Yolu Enfeksiyonu"),
    ("kedi", "yavru kedide goz akintisi hapsirma ve hafif ates", "Üst Solunum Yolu Enfeksiyonu"),
    ("genel", "burun akintisi hapsirma ve durgunluk var", "Üst Solunum Yolu Enfeksiyonu"),
    ("kedi", "barinaktan aldigim kedi hapsiriyor ve gozu cipaklaniyor", "Üst Solunum Yolu Enfeksiyonu"),

    # --- Dis Parazit ---
    ("genel", "kopegimde pire var surekli kasiniyor", "Dış Parazit Enfestasyonu"),
    ("kedi", "kedimin tuylerinde siyah noktalar var ve cok kasiniyor", "Dış Parazit Enfestasyonu"),
    ("kopek", "kene buldum ve hayvan durmadan kasiniyor tuy dokuyor", "Dış Parazit Enfestasyonu"),
    ("genel", "asiri kasinti ve tuy dokulmesi, deride kizariklik", "Dış Parazit Enfestasyonu"),
    ("kedi", "kedi boynunu kasiyor kepek ve pire pislikleri goruluyor", "Dış Parazit Enfestasyonu"),

    # --- Mantar ---
    ("kedi", "kedimin sirtinda yuvarlak tuysuz alan ve kabuklanma var", "Mantar Enfeksiyonu (Dermatofitoz)"),
    ("genel", "deride halka seklinde kizarik lezyon ve tuy dokulmesi", "Mantar Enfeksiyonu (Dermatofitoz)"),
    ("kopek", "kulak kenarinda kepeklenme ve tuysuz bolgeler olustu", "Mantar Enfeksiyonu (Dermatofitoz)"),
    ("kedi", "yavru kedide yuzunde kabuklu yara ve tuy dokulmesi", "Mantar Enfeksiyonu (Dermatofitoz)"),
    ("genel", "deri dokuntusu kabuklanma ve lokal tuy kaybi var", "Mantar Enfeksiyonu (Dermatofitoz)"),

    # --- Otitis ---
    ("kopek", "kopegim kulagini kasiyor ve kafasini salliyor", "Kulak Enfeksiyonu (Otitis)"),
    ("genel", "kulagindan kotu koku geliyor ve koyu akinti var", "Kulak Enfeksiyonu (Otitis)"),
    ("kedi", "kedinin kulaginda siyah kir var surekli kasiyor", "Kulak Enfeksiyonu (Otitis)"),
    ("kopek", "sarkik kulakli kopegim kulagina dokundurtmuyor ve agri var", "Kulak Enfeksiyonu (Otitis)"),
    ("genel", "kulak kasintisi kafa sallama ve kizariklik", "Kulak Enfeksiyonu (Otitis)"),

    # --- FLUTD ---
    ("kedi", "erkek kedim idrar yapamiyor kum kabinda zorlaniyor", "İdrar Yolu Tıkanıklığı (FLUTD)"),
    ("kedi", "kedim sik sik tuvalete gidiyor ama cis yapamiyor ve miyavliyor", "İdrar Yolu Tıkanıklığı (FLUTD)"),
    ("kedi", "idrarinda kan var ve idrar yaparken agri cekiyor", "İdrar Yolu Tıkanıklığı (FLUTD)"),
    ("kedi", "kedi kum kabinin icinde uzun sure bekliyor damla damla idrar", "İdrar Yolu Tıkanıklığı (FLUTD)"),
    ("kopek", "kopegim kanli idrar yapiyor ve sik sik isiyor", "İdrar Yolu Tıkanıklığı (FLUTD)"),

    # --- Gingivitis ---
    ("kedi", "kedimin agzi cok kokuyor ve dis etleri kirmizi", "Diş Eti İltihabı (Gingivitis)"),
    ("kopek", "agiz kokusu var ve dislerinde sari tartar birikmis", "Diş Eti İltihabı (Gingivitis)"),
    ("genel", "salyasi akiyor agzi kokuyor ve sert mama yiyemiyor", "Diş Eti İltihabı (Gingivitis)"),
    ("kedi", "dis eti kanamasi ve yemek yerken agzini birakiyor", "Diş Eti İltihabı (Gingivitis)"),
    ("kopek", "agzindan koku geliyor dis eti sismis istahsiz", "Diş Eti İltihabı (Gingivitis)"),

    # --- Bobrek ---
    ("kedi", "yasli kedim cok su iciyor ve kilo veriyor ara ara kusuyor", "Kronik Böbrek Yetmezliği"),
    ("kedi", "surekli su iciyor sik idrar yapiyor ve zayifladi", "Kronik Böbrek Yetmezliği"),
    ("kedi", "on yasindaki kedim istahsiz halsiz ve agzi kokuyor kilo kaybi var", "Kronik Böbrek Yetmezliği"),
    ("genel", "asiri susama kilo kaybi ve durgunluk", "Kronik Böbrek Yetmezliği"),
    ("kedi", "yasli kedide kusma istahsizlik ve cok su icme", "Kronik Böbrek Yetmezliği"),

    # --- Diyabet ---
    ("kopek", "kopegim cok su iciyor cok yiyor ama kilo veriyor", "Diabetes Mellitus"),
    ("kedi", "kilolu kedim surekli su iciyor ve sik sik idrar yapiyor", "Diabetes Mellitus"),
    ("genel", "asiri susama sik idrar ve istah artmasina ragmen zayiflama", "Diabetes Mellitus"),
    ("kopek", "cok su iciyor idrarini kacirmaya basladi ve halsiz", "Diabetes Mellitus"),
    ("kedi", "arka bacaklarinda gucsuzluk ve asiri su icme var", "Diabetes Mellitus"),

    # --- Ic parazit ---
    ("kopek", "yavru kopegin karni sisti ve diskisinda solucan gordum", "İç Parazit (Solucan)"),
    ("kedi", "kedinin poposunu surtuyor ve diskida pirinc gibi seyler var", "İç Parazit (Solucan)"),
    ("genel", "iyi yemesine ragmen zayifliyor ve karni sis", "İç Parazit (Solucan)"),
    ("kopek", "ara ara ishal ve tuyleri matlasti kilo kaybi var", "İç Parazit (Solucan)"),
    ("kedi", "kustugu icinde solucan vardi ve karni sisik", "İç Parazit (Solucan)"),

    # --- Eklem ---
    ("kopek", "kopegim arka ayagini topalliyor ve merdiven cikamiyor", "Eklem/Kalça Rahatsızlığı"),
    ("kopek", "yasli kopegim yurumekte zorlaniyor ve kalkarken zorlaniyor", "Eklem/Kalça Rahatsızlığı"),
    ("genel", "topallama var ve dokununca agri tepkisi veriyor", "Eklem/Kalça Rahatsızlığı"),
    ("kopek", "sabahlari tutuk yuruyor sonra aciliyor topallama var", "Eklem/Kalça Rahatsızlığı"),
    ("kedi", "kedim yuksege atlayamiyor ve arka ayagini basmiyor", "Eklem/Kalça Rahatsızlığı"),

    # --- Zehirlenme ---
    ("kopek", "kopegim cikolata yedi ve kusuyor titriyor", "Zehirlenme"),
    ("genel", "fare zehiri yemis olabilir agzindan kopuk geliyor", "Zehirlenme"),
    ("kedi", "kedim deterjan yaladi ve asiri salya akiyor", "Zehirlenme"),
    ("genel", "zehirli madde yedikten sonra kasilma ve kusma basladi", "Zehirlenme"),
    ("kopek", "bahcedeki ilacli otlari yedi simdi titriyor ve salyasi akiyor", "Zehirlenme"),

    # --- Alerjik dermatit ---
    ("kopek", "mama degistirdikten sonra surekli kasiniyor ve deri kizardi", "Alerjik Dermatit"),
    ("genel", "patilerini yaliyor ve karin bolgesinde kizariklik var", "Alerjik Dermatit"),
    ("kedi", "yeni tasma taktiktan sonra boynunda kizarik dokuntu olustu", "Alerjik Dermatit"),
    ("kopek", "bahar aylarinda kasinti artiyor ve gozleri kiziyor", "Alerjik Dermatit"),
    ("genel", "deri dokuntusu ve siddetli kasinti var parazit yok", "Alerjik Dermatit"),

    # --- Konjonktivit ---
    ("kedi", "kedimin gozu kizarik ve akinti var", "Konjonktivit"),
    ("kopek", "gozunu acamiyor ve sari goz akintisi geliyor", "Konjonktivit"),
    ("genel", "goz kizarikligi ve surekli sulanma var", "Konjonktivit"),
    ("kedi", "gozunu patisiyle ovusturuyor ve gozu sisti", "Konjonktivit"),
    ("kopek", "iki gozunde de akinti ve kizariklik olustu", "Konjonktivit"),

    # --- Kennel cough ---
    ("kopek", "kopegim kuru kuru oksuruyor sanki bogazina bir sey takilmis", "Kennel Cough (Bulaşıcı Trakeobronşit)"),
    ("kopek", "pansiyondan sonra oksuruk basladi ve hirilti var", "Kennel Cough (Bulaşıcı Trakeobronşit)"),
    ("kopek", "sert oksuruk sonrasi ogurme var ates yok", "Kennel Cough (Bulaşıcı Trakeobronşit)"),
    ("genel", "oksuruk ve hiriltili nefes alma var", "Kennel Cough (Bulaşıcı Trakeobronşit)"),
    ("kopek", "parkta diger kopeklerle oynadiktan sonra oksurmeye basladi", "Kennel Cough (Bulaşıcı Trakeobronşit)"),

    # --- Sicak carpmasi ---
    ("kopek", "sicakta yurudukten sonra dili morardi ve hizli nefes aliyor", "Sıcak Çarpması"),
    ("kopek", "arabada kaldi simdi asiri salya ve nefes darligi var", "Sıcak Çarpması"),
    ("genel", "asiri sicakta kaldi halsiz ve zor nefes aliyor", "Sıcak Çarpması"),
    ("kopek", "yazin kosuya ciktik sonra bayildi ve vucudu sicak", "Sıcak Çarpması"),
    ("kedi", "sicak odada kaldi agzi acik hizli nefes aliyor", "Sıcak Çarpması"),

    # --- Kabizlik ---
    ("kedi", "kedim uc gundur diskisini yapamiyor ve zorlaniyor", "Kabızlık"),
    ("genel", "kaka yapamiyor karni sert ve istahsiz", "Kabızlık"),
    ("kedi", "kum kabina giriyor cikiyor ama diski yapamiyor", "Kabızlık"),
    ("kopek", "iki gundur diski yapamadi ve karni sis", "Kabızlık"),
    ("kedi", "tuy yumagi kusuyor ve kabizlik cekiyor", "Kabızlık"),

    # --- Epilepsi ---
    ("kopek", "kopegim havale geciriyor ve agzindan kopuk geldi", "Epileptik Nöbet"),
    ("genel", "yere yatip kasilma geciriyor ve bilincini kaybetti", "Epileptik Nöbet"),
    ("kedi", "aniden titremeye basladi ve tepki vermiyor", "Epileptik Nöbet"),
    ("kopek", "nobet sonrasi sersem gibi yuruyor ve dengesini kaybediyor", "Epileptik Nöbet"),
    ("genel", "tekrarlayan kasilma nobetleri var", "Epileptik Nöbet"),

    # --- Kene kaynakli ---
    ("kopek", "kene aldiktan sonra atesi cikti ve halsiz yatiyor", "Kene Kaynaklı Enfeksiyon"),
    ("kopek", "kopegimde kene vardi simdi istahsiz ve idrari koyu", "Kene Kaynaklı Enfeksiyon"),
    ("genel", "kene tutunmasi sonrasi ates halsizlik ve istahsizlik", "Kene Kaynaklı Enfeksiyon"),
    ("kopek", "dis paraziti var ates ve dis eti solgunlugu goruluyor", "Kene Kaynaklı Enfeksiyon"),
    ("kopek", "kene isirigi sonrasi eklem agrisi ve topallama basladi", "Kene Kaynaklı Enfeksiyon"),
]


def seed(reset: bool = False) -> None:
    if reset:
        print("[init_db] Tablolar siliniyor (--reset)...")
        Base.metadata.drop_all(bind=engine)

    init_database()

    session = get_session()
    try:
        mevcut = session.query(Symptom).filter(Symptom.kaynak == KAYNAK_SEED).count()
        if mevcut:
            print(f"[init_db] Zaten {mevcut} seed kaydı var, ekleme yapılmadı.")
            print("[init_db] Sıfırdan yüklemek için: python init_db.py --reset")
            return

        eksik = {h for _, _, h in ORNEKLER} - set(ONERILER)
        if eksik:
            raise SystemExit(f"[init_db] HATA: öneri metni tanımsız hastalık(lar): {eksik}")

        session.add_all(
            [
                Symptom(
                    tur=tur,
                    semptom=semptom,
                    hastalik=hastalik,
                    oneri=ONERILER[hastalik],
                    kaynak=KAYNAK_SEED,
                    guven=1.0,
                )
                for tur, semptom, hastalik in ORNEKLER
            ]
        )
        session.commit()

        print(f"[init_db] {len(ORNEKLER)} eğitim örneği yüklendi.")
        print(f"[init_db] {len(ONERILER)} farklı hastalık sınıfı tanımlı.")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VetAI veritabanı kurulumu")
    parser.add_argument("--reset", action="store_true", help="Tabloyu sıfırla ve baştan yükle")
    args = parser.parse_args()
    seed(reset=args.reset)
