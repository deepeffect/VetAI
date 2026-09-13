"""Veritabanini olusturur ve baslangic (seed) egitim verisini yukler.

Kullanim:
    python init_db.py           # tablo yoksa olustur, veri yoksa doldur
    python init_db.py --reset   # tabloyu sifirla ve bastan doldur

Veri seti bilincli olarak "her hastalik icin ayni sikayetin farkli soyleyislerini"
icerir; Logistic Regression'in ezber yerine dil kaliplarini ogrenmesi icin
sinif basina en az 4-5 varyasyon gerekir.
"""

from __future__ import annotations

import argparse

from database import Base, KAYNAK_SEED, Symptom, engine, get_session, init_database

# --------------------------------------------------------------------------
# Hastalik basina sabit tavsiye metni (tabloda `oneri` kolonuna yazilir)
# --------------------------------------------------------------------------
ONERILER: dict[str, str] = {
    "Gastroenterit": (
        "12 saat kati gida verilmeyip temiz suya erisim saglanmali, ardindan 2-3 gun "
        "az yagli/haslanmis tavuk-pirinc gibi hafif diyete gecilmeli. Kusma 24 saati "
        "asarsa, diskida kan varsa veya hayvan su icemiyorsa dehidrasyon riski nedeniyle "
        "ayni gun veteriner kontrolu gerekir."
    ),
    "Parvoviral Enterit": (
        "ACIL. Ozellikle asisi tamamlanmamis yavrularda oldurucu seyreder. Evde tedavi "
        "denenmemeli; hayvan derhal en yakin veteriner klinigine goturulmelidir. "
        "Yogun sivi destegi ve izolasyon gerekir, virus diger kopeklere cok bulasicidir."
    ),
    "Ust Solunum Yolu Enfeksiyonu": (
        "Hayvan sicak ve cereyansiz bir ortamda tutulmali, burun cevresi nemli bezle "
        "temizlenmeli, isitilmis kokulu mama ile istahi desteklenmelidir. Gozde yogun "
        "akinti, nefes darligi veya 48 saatten uzun istahsizlik varsa veterinere gidilmeli."
    ),
    "Dis Parazit Enfestasyonu": (
        "Tuyler pire tarayicisi ile kontrol edilmeli, yatak ve tekstil yuksek sicaklikta "
        "yikanmalidir. Veteriner onerisiyle uygun kilo/tur icin ruhsatli dis parazit "
        "damlasi uygulanmali; kedilere asla kopek icin uretilmis urun kullanilmamalidir."
    ),
    "Mantar Enfeksiyonu (Dermatofitoz)": (
        "Lezyonlar insana da bulasabilecegi icin temas sonrasi eller yikanmalidir. "
        "Bolge kuru tutulmali, hayvanin yalamasini onlemek icin gerekirse yaka takilmalidir. "
        "Kesin tani icin veterinerde lamba muayenesi ve kultur yapilmasi gerekir."
    ),
    "Kulak Enfeksiyonu (Otitis)": (
        "Kulak kanalina pamuklu cubuk sokulmamalidir. Veterinerin onerecegi kulak "
        "temizleme solusyonu disinda evde madde damlatilmamali; kulak zari delik ise "
        "bazi damlalar kalici hasar verir. Koku ve koyu akinti varsa muayene sarttir."
    ),
    "Idrar Yolu Tikanikligi (FLUTD)": (
        "ACIL. Ozellikle erkek kedilerde idrar yapamama 24-48 saat icinde oldurucudur. "
        "Karin bolgesine baski uygulanmamali, hayvan vakit kaybetmeden veterinere "
        "goturulmelidir. Sonda ile idrar bosaltimi gerekebilir."
    ),
    "Dis Eti Iltihabi (Gingivitis)": (
        "Sert kemik ve cok sert odul verilmemeli, hayvana ozel dis macunu ile duzenli "
        "firca aliskanligi kazandirilmalidir. Insan dis macunu toksiktir. Ileri tartar "
        "birikiminde veterinerde anestezi altinda dis temizligi gerekir."
    ),
    "Kronik Bobrek Yetmezligi": (
        "Suya erisim artirilmali, mumkunse su cesmesi ve yas mama tercih edilmelidir. "
        "Tani ancak kan ve idrar tahlili ile konur. Erken teshiste bobrek destek mamasi "
        "ile yasam suresi belirgin uzar; vakit kaybetmeden tahlil yaptirilmalidir."
    ),
    "Diabetes Mellitus": (
        "Su ve mama tuketimi ile idrar miktari gunluk not edilmelidir. Tani kan sekeri "
        "ve fruktozamin testi ile konur. Tedavi insulin ve sabit ogun duzeni gerektirir; "
        "kendi kendine insulin dozu ayarlanmamalidir."
    ),
    "Ic Parazit (Solucan)": (
        "Diskida pirinc tanesi benzeri halkalar aranmali, mama kabi ve tuvalet alani "
        "gunluk temizlenmelidir. Veteriner onerisiyle kiloya uygun ic parazit ilaci "
        "verilmeli ve 2-3 hafta sonra tekrarlanmalidir."
    ),
    "Eklem/Kalca Rahatsizligi": (
        "Kaygan zeminlere hali serilmeli, merdiven ve yuksege atlama sinirlandirilmali, "
        "fazla kilo varsa diyetle azaltilmalidir. Insan agri kesicileri (parasetamol, "
        "ibuprofen) hayvanlar icin oldurucudur, kesinlikle verilmemelidir."
    ),
    "Zehirlenme": (
        "ACIL. Veteriner soylemeden kusturma denenmemeli, sut/yag verilmemelidir. "
        "Yenilen maddenin ambalaji yanina alinarak hayvan derhal klinige goturulmelidir. "
        "Ilk 1-2 saat mide bosaltimi icin kritik zaman araligidir."
    ),
    "Alerjik Dermatit": (
        "Son degisen mama, tasma, sampuan veya temizlik urunu gozden gecirilmelidir. "
        "Bolge serin suyla yikanabilir; kasimayi onlemek icin yaka kullanilmalidir. "
        "Tekrarlayan olgularda veterinerde alerji testi ve diyet denemesi yapilir."
    ),
    "Konjonktivit": (
        "Gozler disaridan iceriye dogru steril serum fizyolojik ile temizlenebilir. "
        "Kortizonlu damlalar kornea yarasi varsa durumu agirlastirir; veteriner "
        "gormeden damla kullanilmamalidir."
    ),
    "Kennel Cough (Bulasici Trakeobronsit)": (
        "Tasma yerine gogus tasmasi kullanilarak gırtlak basincı azaltilmali, hayvan "
        "diger kopeklerden uzak tutulmalidir. Oksuruk 1 haftayi asar, istahsizlik veya "
        "ates eklenirse zaturre riski nedeniyle veterinere gidilmelidir."
    ),
    "Sicak Carpmasi": (
        "ACIL. Hayvan golgeye alinip vucudu ILIK suyla (buzlu su damar buzulmesi yaptigi "
        "icin degil) yavasca sogutulmali ve derhal veterinere goturulmelidir. Ic organ "
        "hasari disaridan gorulmese de saatler sonra ortaya cikabilir."
    ),
    "Kabizlik": (
        "Su tuketimi artirilmali, yas mamaya gecilmeli, kedilerde tuy yumagi icin malt "
        "verilebilir. 48 saatten uzun diski yapamama, kusma ile birlikteyse tikanikligi "
        "dusundurur ve veteriner muayenesi gerektirir."
    ),
    "Epileptik Nobet": (
        "ACIL. Nobet sirasinda agza el veya cisim sokulmamali, hayvan sadece sert "
        "cisimlerden uzaklastirilmali ve nobetin suresi olculmelidir. 3 dakikayi asan "
        "veya art arda gelen nobetlerde vakit kaybetmeden klinige gidilmelidir."
    ),
    "Kene Kaynakli Enfeksiyon": (
        "Kene, cimbizla deriye en yakin noktadan cevrilmeden duz cekilerek cikarilmali, "
        "elle ezilmemelidir. Ates, halsizlik ve istahsizlik varsa kan parazitleri icin "
        "kan testi gerekir; tedavi gecikirse kansizlik gelisebilir."
    ),
}

# --------------------------------------------------------------------------
# Egitim ornekleri: (tur, semptom metni, hastalik)
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
    ("kedi", "kedim hapsiriyor burnu akiyor ve gozleri sulaniyor", "Ust Solunum Yolu Enfeksiyonu"),
    ("kedi", "surekli hapsirik burun akintisi ve istahsizlik var", "Ust Solunum Yolu Enfeksiyonu"),
    ("kedi", "yavru kedide goz akintisi hapsirma ve hafif ates", "Ust Solunum Yolu Enfeksiyonu"),
    ("genel", "burun akintisi hapsirma ve durgunluk var", "Ust Solunum Yolu Enfeksiyonu"),
    ("kedi", "barinaktan aldigim kedi hapsiriyor ve gozu cipaklaniyor", "Ust Solunum Yolu Enfeksiyonu"),

    # --- Dis Parazit ---
    ("genel", "kopegimde pire var surekli kasiniyor", "Dis Parazit Enfestasyonu"),
    ("kedi", "kedimin tuylerinde siyah noktalar var ve cok kasiniyor", "Dis Parazit Enfestasyonu"),
    ("kopek", "kene buldum ve hayvan durmadan kasiniyor tuy dokuyor", "Dis Parazit Enfestasyonu"),
    ("genel", "asiri kasinti ve tuy dokulmesi, deride kizariklik", "Dis Parazit Enfestasyonu"),
    ("kedi", "kedi boynunu kasiyor kepek ve pire pislikleri goruluyor", "Dis Parazit Enfestasyonu"),

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
    ("kedi", "erkek kedim idrar yapamiyor kum kabinda zorlaniyor", "Idrar Yolu Tikanikligi (FLUTD)"),
    ("kedi", "kedim sik sik tuvalete gidiyor ama cis yapamiyor ve miyavliyor", "Idrar Yolu Tikanikligi (FLUTD)"),
    ("kedi", "idrarinda kan var ve idrar yaparken agri cekiyor", "Idrar Yolu Tikanikligi (FLUTD)"),
    ("kedi", "kedi kum kabinin icinde uzun sure bekliyor damla damla idrar", "Idrar Yolu Tikanikligi (FLUTD)"),
    ("kopek", "kopegim kanli idrar yapiyor ve sik sik isiyor", "Idrar Yolu Tikanikligi (FLUTD)"),

    # --- Gingivitis ---
    ("kedi", "kedimin agzi cok kokuyor ve dis etleri kirmizi", "Dis Eti Iltihabi (Gingivitis)"),
    ("kopek", "agiz kokusu var ve dislerinde sari tartar birikmis", "Dis Eti Iltihabi (Gingivitis)"),
    ("genel", "salyasi akiyor agzi kokuyor ve sert mama yiyemiyor", "Dis Eti Iltihabi (Gingivitis)"),
    ("kedi", "dis eti kanamasi ve yemek yerken agzini birakiyor", "Dis Eti Iltihabi (Gingivitis)"),
    ("kopek", "agzindan koku geliyor dis eti sismis istahsiz", "Dis Eti Iltihabi (Gingivitis)"),

    # --- Bobrek ---
    ("kedi", "yasli kedim cok su iciyor ve kilo veriyor ara ara kusuyor", "Kronik Bobrek Yetmezligi"),
    ("kedi", "surekli su iciyor sik idrar yapiyor ve zayifladi", "Kronik Bobrek Yetmezligi"),
    ("kedi", "on yasindaki kedim istahsiz halsiz ve agzi kokuyor kilo kaybi var", "Kronik Bobrek Yetmezligi"),
    ("genel", "asiri susama kilo kaybi ve durgunluk", "Kronik Bobrek Yetmezligi"),
    ("kedi", "yasli kedide kusma istahsizlik ve cok su icme", "Kronik Bobrek Yetmezligi"),

    # --- Diyabet ---
    ("kopek", "kopegim cok su iciyor cok yiyor ama kilo veriyor", "Diabetes Mellitus"),
    ("kedi", "kilolu kedim surekli su iciyor ve sik sik idrar yapiyor", "Diabetes Mellitus"),
    ("genel", "asiri susama sik idrar ve istah artmasina ragmen zayiflama", "Diabetes Mellitus"),
    ("kopek", "cok su iciyor idrarini kacirmaya basladi ve halsiz", "Diabetes Mellitus"),
    ("kedi", "arka bacaklarinda gucsuzluk ve asiri su icme var", "Diabetes Mellitus"),

    # --- Ic parazit ---
    ("kopek", "yavru kopegin karni sisti ve diskisinda solucan gordum", "Ic Parazit (Solucan)"),
    ("kedi", "kedinin poposunu surtuyor ve diskida pirinc gibi seyler var", "Ic Parazit (Solucan)"),
    ("genel", "iyi yemesine ragmen zayifliyor ve karni sis", "Ic Parazit (Solucan)"),
    ("kopek", "ara ara ishal ve tuyleri matlasti kilo kaybi var", "Ic Parazit (Solucan)"),
    ("kedi", "kustugu icinde solucan vardi ve karni sisik", "Ic Parazit (Solucan)"),

    # --- Eklem ---
    ("kopek", "kopegim arka ayagini topalliyor ve merdiven cikamiyor", "Eklem/Kalca Rahatsizligi"),
    ("kopek", "yasli kopegim yurumekte zorlaniyor ve kalkarken zorlaniyor", "Eklem/Kalca Rahatsizligi"),
    ("genel", "topallama var ve dokununca agri tepkisi veriyor", "Eklem/Kalca Rahatsizligi"),
    ("kopek", "sabahlari tutuk yuruyor sonra aciliyor topallama var", "Eklem/Kalca Rahatsizligi"),
    ("kedi", "kedim yuksege atlayamiyor ve arka ayagini basmiyor", "Eklem/Kalca Rahatsizligi"),

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
    ("kopek", "kopegim kuru kuru oksuruyor sanki bogazina bir sey takilmis", "Kennel Cough (Bulasici Trakeobronsit)"),
    ("kopek", "pansiyondan sonra oksuruk basladi ve hirilti var", "Kennel Cough (Bulasici Trakeobronsit)"),
    ("kopek", "sert oksuruk sonrasi ogurme var ates yok", "Kennel Cough (Bulasici Trakeobronsit)"),
    ("genel", "oksuruk ve hiriltili nefes alma var", "Kennel Cough (Bulasici Trakeobronsit)"),
    ("kopek", "parkta diger kopeklerle oynadiktan sonra oksurmeye basladi", "Kennel Cough (Bulasici Trakeobronsit)"),

    # --- Sicak carpmasi ---
    ("kopek", "sicakta yurudukten sonra dili morardi ve hizli nefes aliyor", "Sicak Carpmasi"),
    ("kopek", "arabada kaldi simdi asiri salya ve nefes darligi var", "Sicak Carpmasi"),
    ("genel", "asiri sicakta kaldi halsiz ve zor nefes aliyor", "Sicak Carpmasi"),
    ("kopek", "yazin kosuya ciktik sonra bayildi ve vucudu sicak", "Sicak Carpmasi"),
    ("kedi", "sicak odada kaldi agzi acik hizli nefes aliyor", "Sicak Carpmasi"),

    # --- Kabizlik ---
    ("kedi", "kedim uc gundur diskisini yapamiyor ve zorlaniyor", "Kabizlik"),
    ("genel", "kaka yapamiyor karni sert ve istahsiz", "Kabizlik"),
    ("kedi", "kum kabina giriyor cikiyor ama diski yapamiyor", "Kabizlik"),
    ("kopek", "iki gundur diski yapamadi ve karni sis", "Kabizlik"),
    ("kedi", "tuy yumagi kusuyor ve kabizlik cekiyor", "Kabizlik"),

    # --- Epilepsi ---
    ("kopek", "kopegim havale geciriyor ve agzindan kopuk geldi", "Epileptik Nobet"),
    ("genel", "yere yatip kasilma geciriyor ve bilincini kaybetti", "Epileptik Nobet"),
    ("kedi", "aniden titremeye basladi ve tepki vermiyor", "Epileptik Nobet"),
    ("kopek", "nobet sonrasi sersem gibi yuruyor ve dengesini kaybediyor", "Epileptik Nobet"),
    ("genel", "tekrarlayan kasilma nobetleri var", "Epileptik Nobet"),

    # --- Kene kaynakli ---
    ("kopek", "kene aldiktan sonra atesi cikti ve halsiz yatiyor", "Kene Kaynakli Enfeksiyon"),
    ("kopek", "kopegimde kene vardi simdi istahsiz ve idrari koyu", "Kene Kaynakli Enfeksiyon"),
    ("genel", "kene tutunmasi sonrasi ates halsizlik ve istahsizlik", "Kene Kaynakli Enfeksiyon"),
    ("kopek", "dis paraziti var ates ve dis eti solgunlugu goruluyor", "Kene Kaynakli Enfeksiyon"),
    ("kopek", "kene isirigi sonrasi eklem agrisi ve topallama basladi", "Kene Kaynakli Enfeksiyon"),
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
            print(f"[init_db] Zaten {mevcut} seed kayit var, ekleme yapilmadi.")
            print("[init_db] Sifirdan yuklemek icin: python init_db.py --reset")
            return

        eksik = {h for _, _, h in ORNEKLER} - set(ONERILER)
        if eksik:
            raise SystemExit(f"[init_db] HATA: oneri metni tanimsiz hastalik(lar): {eksik}")

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

        print(f"[init_db] {len(ORNEKLER)} egitim ornegi yuklendi.")
        print(f"[init_db] {len(ONERILER)} farkli hastalik sinifi tanimli.")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VetAI veritabani kurulumu")
    parser.add_argument("--reset", action="store_true", help="Tabloyu sifirla ve bastan yukle")
    args = parser.parse_args()
    seed(reset=args.reset)
