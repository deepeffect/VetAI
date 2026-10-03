# -*- coding: utf-8 -*-
"""
Gevşek (kök tabanlı) belirti tanıma — VetAI guardrail için.

esanlam_sozlugu.IFADE_KOD tam ifade eşlemesi yapar ve gerçek kullanıcı metninin ~%30'unu kaçırır
("hiçbir şey yiyemiyor" ≠ "hiçbir şey yemiyor"). Bu modül her belirti kodu için elle seçilmiş
KÖK/ALT DİZGİ listesi tutar; kökler Türkçe çekim eklerinden bağımsız çalışır ("kus" → kusuyor, kustu, kusma).

Kullanım:
    from kokler import belirti_bul_gevsek
    belirtiler, baglam = belirti_bul_gevsek("Kedim 2 gundur kusuyor ve hicbir sey yiyemiyor")
    # belirtiler -> ['KUSMA', 'ISTAHSIZLIK'], baglam -> []

Guardrail önerisi:
    - belirtiler boş DEĞİLse → modele gönder.
    - belirtiler boş, baglam dolu → "Belirtileri biraz daha açar mısınız?" diye sor (kapsam dışı deme).
    - ikisi de boş → kapsam dışı / genel yönlendirme.
Aciliyet için bu modül DEĞİL, acil_kaliplar.aciliyet_tespit kullanılmalı (bu modül bilerek geniş eşler).

VetAI eklemeleri (anlam ayrımı ve halk dili, Ekim 2026):
    - Kökler aranmadan önce anlam_ayrimi kalıpları uygulanır: "sıcak çarptı",
      "kusura bakmayın", "nöbetçi veteriner", "iştahı düştü" gibi ifadelerin
      aralığı maskelenir (yanlış kök tetiklenmez) ve kalıbın doğru kodu eklenir.
    - data/halk_dili_sozlugu.json içindeki "belirti_kokleri" bu tabloya eklenir
      ("kah kuh" -> OKSURUK, "kızak çekiyor" -> POPO_SURTME ...).
    - ASCII katlanmış eşleşme, kullanıcının Türkçe yazdığı farklı bir kelimeyi
      yakalamaz ("kaşık" kökü "kasık" değildir).
"""
import json
import os
import re

try:
    from . import anlam_ayrimi
except ImportError:  # modül tek başına çalıştırılırsa
    import anlam_ayrimi

BAGLAM_KODLARI = {"ASISIZ", "YENI_ALINDI", "DISARI_CIKAN", "KISIR_DEGIL_DISI", "ERKEK", "BUYUK_IRK", "YEMEK_SONRASI",
                  "COP_YEDI", "KILO_FAZLA", "STRES", "YASLI", "KENE_ILACI_YOK", "KURSAL_SEYAHAT", "ARI_SOKMA", "HAMILE",
                  "TEMAS_KOPEK", "ANI_HAREKET", "KUCUK_IRK", "KURU_MAMA", "IYILESMIYOR", "KIZGINLIK_SONRASI"}

# kod -> alt dizgiler (Türkçe küçük harf; eşleme hem Türkçe hem ASCII-katlanmış metinde yapılır)
KOKLER = {
    # sindirim
    "KUSMA": ["kus", "öğür", "yediğini hemen çıkar", "yediğini çıkar", "mide bulantı"],
    "KAN_KUSMA": ["kanlı kus", "kan kus", "kusmuğunda kan", "kusmukta kan", "kusmuğu kanlı"],
    "OGURME_BOS": ["öğürüyor ama", "kusamıyor", "boş boş öğür", "öğürüyor bir şey çıkm", "kusmaya çalışıyor ama"],
    "ISHAL": ["ishal", "dışkısı düzgün", "düzgün olmadı", "düzgün olma", "sulu kaka", "sulu dışkı", "cıvık", "yumuşak kaka", "sürgün", "sulu dışkılı", "kakası sulu", "dışkısı sulu"],
    "ISHAL_MUKUS": ["sümüklü", "mukus", "jöle", "sümük gibi"],
    "KANLI_ISHAL": ["kanlı ishal", "kanlı kaka", "dışkıda kan", "dışkısında kan", "kakasında kan", "kakası kanlı", "ishali kan", "kan gibi kırmızı", "kan çizgi"],
    "DISKI_SIYAH": ["katran", "simsiyah", "siyah kaka", "siyah dışkı"],
    "KABIZLIK": ["kabız", "kaka yapmak için", "çok zorlan", "çok sert", "kaka yapam", "kaka yapmıyor", "kaka yapmadı", "dışkı yapam", "sert kaka", "sert dışkı", "taş gibi", "kakası sert", "dışkısı sert"],
    "IKINMA_KUM": ["ıkın", "kum kabına girip", "kuma girip", "kuma gidiyor", "kum kabına giriyor", "kuma sık"],
    "ISTAHSIZLIK": ["iştahsız", "iştahı yok", "iştahı kesil", "iştahı azal", "yemiyor", "yemedi", "yemez oldu", "lokma", "yemeğe yaklaş", "koklayıp", "kokluyor gidiyor", "mamaya bakm", "yiyemiyor", "iştahı düş"],
    "ISTAH_ARTISI": ["iştahı art", "iştahı çok art", "iştahı arttı", "sürekli aç", "çok yiyor", "iki katı yiyor", "mama dilen", "doymuyor", "doymak bilm", "iştahı iyi ama", "iyi yiyor ama", "çok yemesine rağmen"],
    "SU_ICMEME": ["su içmiyor", "su içmez", "su içmedi", "su bile içm", "içmiyor"],
    "COK_SU_ICME": ["çok su iç", "fazla su iç", "su kabının başında", "sürekli su iç", "su tüketimi art", "her yerden su", "su kabını", "inanılmaz su", "litre"],
    "KILO_KAYBI": ["zayıfla", "kilo ver", "kilo kayb", "kemikleri çıktı", "kemik gibi", "bıçak gibi", "eridi", "bir deri bir kemik", "kilo kaybed", "zayıf", "kiloya düş", "kilo almıyor", "kilo alamıyor", "kilo alm"],
    "KILO_ALMA": ["kilo aldı", "kilo alıyor", "kilo alma", "kilo alıp", "şişmanla"],
    "KARIN_SIS": ["karnı şiş", "karnı davul", "karnı gergin", "karnı balon", "karnı büyü", "karnı çok büyü", "karnı bir anda", "karnı biraz büyü", "karnı büyümeye", "karın şiş", "göbeği şiş", "karnı sert", "karnı gözle görülür"],
    "KARIN_SIS_ZAYIF": ["karnı şişti ama", "karnı balon gibi ama", "karnı büyüyor", "karnı şişiyor ama", "karnı gittikçe şiş"],
    "KARIN_AGRISI": ["karnına dokun", "karnı ağrı", "karın ağrı", "namaz pozisyon", "kalçasını havaya", "poposunu havada", "karnını sakın", "karnına dokund", "karnını elled"],
    "GAZ": [" gaz ", " gazı", "gaz çıkar", "gazlı", "gurul"],
    "YABANCI_CISIM": ["yuttu", "yutmuş", "ip yut", "çorap", "oyuncağının parça", "oyuncağını parçala", "kemik yedi", "iğne", "iplik", "mısır koçan", "saç lastiği", "yabancı cisim", "pamuk", "ip parçası", "ipin ucu", "kemirir"],
    "KURT_GORUNTU": [" kurt ", "kurtlar", "kurt çık", "kurt gör", "kurt var", "beyaz kurt", "pirinç tanesi", "pirinç gibi", "spagetti", "solucan", "parazit gördü"],
    "KARIN_SIS_YAVRU": ["balon gibi şiş", "göbeği şiş", "karnı davul gibi şiş"],
    "YUTMA_ZOR": ["yutkun", "yutmakta zorlan", "yutamıyor", "boğazında bir şey takılı"],
    "DEHIDRASYON": ["susuz", "çukura kaçtı", "gözleri çökmüş", "ağzı kuru", "deri geri inmiyor", "gözleri çukur"],
    # genel
    "HALSIZLIK": ["halsiz", "oynamıyor", "sürekli yatıyor", "hep uyuyor", "keyifsiz", "durgun", "bitkin", "hareket etmiyor", "oyun oynamıyor", "köşeye çekil", "kendinde değil", "eskisi gibi değil", "uyuşuk", "yatıyor kalkm", "kalkmıyor", "çağırınca gelm", "hiçbir şey yapmadan yat", "bir köşede yat", "kanepenin altında yat", "yatıyor"],
    "SAKLANMA": ["saklan", "dolabın altı", "yatağın altı", "ortalıkta görünm"],
    "ATES": ["ateş", "vücudu sıcak", "kulakları sıcak", "ateşi var"],
    "ATES_DIRENCLI": ["ateşi düşm", "antibiyotik işe yarama", "ateşi inip çık", "ateşi gidip gel", "düşmeyen ateş", "ateşi bir türlü"],
    "TITREME": ["titr"],
    "USUME": [" üşü", " üşüyor", " üşür", "kalorifer", "sıcak yer ar", "battaniye"],
    "AGRI": ["ağrı", "acı çek", "acıyor", "acıyla", "inliyor", "inleme", "inledi", "canı yan", "ağlıyor", "acı içinde"],
    "SESLENME": ["miyavl", "bağırıyor", "bağırıp", "havlıyor", "uluyor", "acı acı", "durmadan inl"],
    "HUZURSUZ": ["huzursuz", "yerinde duram", "rahat edem", "dolanıyor", "yatıp kalk", "yer değiştir", "yerleşem"],
    "DAVRANIS_DEGISIM": ["saldırgan", "hırl", "huyu değiş", "tuhaf davran", "sevilmek istem", "huysuz", "huyu değişti"],
    "GECE_DOLANMA": ["gece dolan", "geceleri uyum", "köşeye sıkış", "köşelere sıkış", "tanımıyor", "duvara bak", "kayboluyor", "menteşe", "amaçsız", "gece uyumuyor", "gece dolaş", "geceleri dolan"],
    "TUVALET_UNUTMA": ["tuvaletini unut", "içeriye yap", "içeri yap", "evde tuvalet", "tuvaletini içeri"],
    "SOLUK_DISETI": ["dişetleri soluk", "dişetleri beyaz", "dişetleri bembeyaz", "dişeti soluk", "soluk dişeti", "diş etleri beyaz", "solgun", "dişetleri çok soluk", "beyaza yakın", "dişetleri kuru"],
    "SARILIK": ["sarılık", "sarardı", "sararma", "gözleri sarı", "sarımsı", "sarımtırak", "sarı geldi", "dişetleri hafif sarı"],
    "DERI_KANAMA_NOKTA": ["kırmızı nokta", "morluk", "kanama noktal", "peteşi"],
    "BURUN_KANAMA": ["burnu kan", "burnundan kan", "burun kanam"],
    "LENF": ["bezeleri", "bezeler", "lenf", "bezesi şiş", "çenesinin altında şiş", "çenesinin altındaki bez", "boynundaki bez", "bezleri"],
    "BILINC": ["bilinci", "bilinç", "tepki vermiyor", "kendinden geç", "kaldıramıyor", "uyanmıyor", "kendine gelm", "yerde yatıyor"],
    "BAYILMA": ["bayıl", "yığıl", "düşüp kalk", "düşüp bay"],
    # idrar
    "COK_ISEME": ["sık idrar", "kumu çok çabuk", "çabuk ıslan", "sık ama az", "sık işiyor", "sık çiş", "çok işiyor", "çok çiş", "kumu çabuk ısla", "kumu iki kat", "evin içine işe", "işemek için kalk", "fazla çiş", "sık sık idrar", "sık sık işiyor", "sık sık az az", "çiş için kaldır", "kumu bataklık", "kumu sürekli ıslak", "kumu daha sık"],
    "ZOR_ISEME": ["işerken", "az idrar", "idrar yapıyor ama", "işemeye çalış", "damla damla", "az az işiyor", "çişini yaparken", "zor işiyor", "idrar yaparken", "az az idrar", "az geliyor", "çok az geliyor", "işiyor ama az"],
    "IDRAR_YAPAMAMA": ["işeyemiyor", "işeyemedi", "çiş yapam", "idrar yapam", "hiç çiş yap", "hiç işeme", "çiş gelmiyor", "idrar gelmiyor", "hiç idrar", "çiş yapmadı", "işemiyor", "hiç gelmiyor", "kum kupkuru", "hiçbir şey çıkmıyor", "hiç çiş yok"],
    "KANLI_IDRAR": ["idrarı kanlı", "kanlı idrar", "çişinde kan", "kanlı çiş", "pembe işiyor", "pembe renkli", "kumda kan", "idrarda kan", "idrarında kan", "kan işiyor", "kanlı işiyor", "çişi pembe", "çişi kanlı", "pembe leke", "idrarı koyu kırmızı", "idrarı kırmızı"],
    "TUVALET_DISI": ["kum dışına", "kumu kullanm", "kum kabı dışına", "her yerine çiş", "paspas", "küvet", "kumunu kullanmıyor", "dışına işiyor", "köşelerine çiş", "köşelere çiş", "kum dışı"],
    "IDRAR_KACIRMA": ["çişini kaçır", "altına kaçır", "idrar kaçır", "kaçırmaya başla", "kaçırıyor", "çişini tutam", "yattığı yeri ısla", "altına işe", "altını ısla"],
    "GENITAL_YALAMA": ["cinsel organ", "pipisini", "arka tarafını yal", "arkasını yal", "genital", "arka tarafını durmadan"],
    "IDRAR_KOKU": ["idrarı kok", "çişi kok", "idrar kokusu", "ağır kok", "idrarı çok kötü kok", "kokan idrar", "idrarı bulanık"],
    # solunum
    "OKSURUK": ["öksür"],
    "OKSURUK_KAZ": ["kaz sesi", "kaz gibi", "korna"],
    "OKSURUK_ATAK": ["boynunu uzat", "tüy yumağı çıkar", "çömel"],
    "HIRILTI": ["hırıl", "ıslık", "hışır"],
    "NEFES_DARLIGI": ["nefes al", "zor nefes", "nefes darl", "nefes nefese", "soluk soluğa", "ağzı açık", "karnından nefes", "hızlı soluy", "hızlı nefes", "nefes alam", "nefesi hızl", "nefes almak için", "güç nefes", "nefes almakta"],
    "SOLUNUM_HIZLI_DINLENIRKEN": ["dinlenirken", "uyurken bile", "göğsü hızlı", "uyurken hızlı", "uyurken nefes", "dakikada"],
    "DIL_MOR": ["morar", "mosmor", "dili mor", "dişetleri mor", "morumsu", "dili mavi", "dişetleri mavi"],
    "HAPSIRMA": ["hapşır", "hapşur", "hapşırık"],
    "BURUN_AKINTISI": ["burnu ak", "burun ak", "burnundan ak", "burnu tıkalı", "sümük", "burun tıkan", "burnundan sarı", "burnundan yeşil", "burnundan kalın", "burnu sürekli ıslak", "burnundan ve gözünden"],
    "SES_KISIKLIK": ["sesi kısıl", "ses kısık", "miyavlaması çıkm", "sesi çıkm", "sesi çatal", "kısık ses"],
    "EGZERSIZ_INTOLERANS": ["çabuk yorul", "hemen yorul", "yürüyüşe dayanam", "koşamıyor", "yoruluyor", "oturup kal", "hızla yorul", "yürüyüşte otur"],
    "SALYA": ["salya", "köpük geliyor", "ağzından köpük", "ağzı ıslak", "salyası"],
    # ağız
    "AGIZ_KOKUSU": ["ağzı kok", "ağız kok", "nefesi kok", "leş gibi", "ağzı çok kötü", "ağız kokusu", "nefesi ekşi", "kokuyor ki yanına"],
    "DIS_ETI": ["diş eti", "dişeti", "diş taşı", "dişleri sallan", "dişi düştü", "dişi sallan", "dişleri kahverengi", "tartar", "dişleri sarı", "diş etleri", "dişleri taş", "dişleri kırık", "dişi eksik", "dişleri kalın taş"],
    "YEME_ZORLUGU": ["tek taraflı çiğn", "ağzından düşür", "sert mamayı yiyem", "yerken bağır", "yerken ağl", "çiğneyem", "ağzına alıp bırak", "kuru mamayı yemez", "bir tarafıyla çiğn", "yemeği düşür", "yumuşağı yiyor"],
    "AGIZ_PENCELEME": ["ağzını pençe", "ağzını pati", "ağzını ovuştur", "ağzını sürekli"],
    "AGIZ_YARA": ["ağzında yara", "dilinde yara", "ağız içi yara", "dudağının içi", "ağzında yaralar", "dilinin ucunda", "ağzında iyileşmeyen", "dilinde küçük bir yara"],
    # göz
    "GOZ_AKINTISI": ["gözleri ak", "gözü ak", "gözünden ak", "çapak", "gözleri sulan", "gözü sulan", "göz akıntı", "gözünden yeşil", "gözünden sarı", "gözlerinden", "gözünden ye", "sulanıyor", "gözü sulanı"],
    "GOZ_KIZARIKLIK": ["gözü kızar", "gözleri kızar", "gözü kırmızı", "gözleri kırmızı", "gözünün beyazı kırmızı", "gözü kanlan", "göz kapağı şiş", "gözünün içi kırmızı", "gözleri kıpkırmızı", "gözünün beyazı kızar", "gözleri kızarık", "gözü kızarık", "gözleri de kırmızı", "gözü kırmızı ve"],
    "GOZ_KISMA": ["gözünü kıs", "gözü kısık", "gözünü açam", "gözünü kapalı", "gözü kapalı", "gözünü kapat", "ışıktan kaç", "gözünü ovuştur", "yarı kapalı", "gözünü açmıyor", "gözünü hiç açm", "pençesiyle ovuştur", "gözünü pençe", "patisiyle ovuştur", "gözü sabahtan beri kapalı", "gözü kısık", "ışığa bakınca", "gözünü hiç açmıyor", "gözünü pençel"],
    "GOZ_BULANIK": ["bulanık", "buğulu", "bir tabaka", "mavi beyaz", "gözünde beyaz", "gözünde leke", "gözünde mavi", "gözü beyaz", "beyaz tabaka", "gri leke", "katarakt", "gri bir leke", "bulanıklık", "beyaz bir bulanık"],
    "GOZ_UCUNCU_KAPAK": ["beyaz perde", "beyaz zar", "üçüncü göz kapağı", "iç köşesinden beyaz", "beyaz bir zar"],
    "GOZ_TITREME": ["gözleri titr", "gözleri sağa sola", "göz bebekleri kay", "gözleri kayıyor", "gözleri hareket ed", "gözleri sürekli kay", "gözleri sürekli sağa"],
    "GOZ_CEVRE_TUYSUZ": ["gözlük gibi", "göz çevresi tüysüz", "gözlerinin etrafı kepek", "gözlerinin etrafı tüysüz", "gözlerinin etrafında gözlük", "gözlerinin etrafında tüysüz"],
    # deri
    "KASINMA": ["kaşın", "kaşıyor", "kendini ısır", "yalanıyor", "kaşıntı", "kaşımaktan", "kaşıyıp", "yalıyor ve ısır"],
    "PATI_YALAMA": ["patilerini yal", "patisini yal", "ayaklarını yal", "patilerinin arası", "pati yal", "patilerini kanat"],
    "KOLTUK_ALTI_KIZARIK": ["koltuk alt", "kasık", "bacak aralar"],
    "TUY_DOKULMESI": ["tüyleri dökül", "tüy dökül", "tüysüz", " kel ", " kel,", "kel oldu", "kel leke", "kel bölge", "kel yer", "kel alan", "kel kaldı", "tüyleri seyrel", "tüyleri geliyor", "avuç avuç", "tüyler döküldü", "tüyleri döküldü", "tüy kayb", "kelleş"],
    "KEL_YUVARLAK": ["yuvarlak", "para büyüklüğünde", "pullu", "halka"],
    "SIMETRIK_TUY_DOKULME": ["simetrik", "fare kuyruğu", "iki yanı", "iki yanında"],
    "KUYRUK_DIBI": ["kuyruk dibi", "kuyruğunun üstü", "kuyruk dibinde", "sırtının arkası", "sırtının arkasında"],
    "KIZARIKLIK_DERI": ["derisi kızar", "kırmızı leke", "kızarık", "kıpkırmızı", "kabarcık", "kızarıklık", "kabartı", "kırmızı kabar"],
    "KABUK_YARA": ["kabuk", " yara ", " yara.", " yara,", " yarası", " yaraları", " yaralar", "yara bere", "açık yara", "kabuklu yara", "yaralı", " yara var", " yara ol", " yara çık"],
    "SIVILCE_DERI": ["sivilce", "irinli", "sarı başlı", "püstül", "sivilcik"],
    "HOT_SPOT": ["sızıntılı", "ıslak yara", "yapışkan yara", "bir gecede", "sızan", "hot spot", "ıslak, kıpkırmızı", "ıslak kıpkırmızı", "sızıntı"],
    "KALIN_DERI": ["kalınlaş", "kabuklu", "kalın kabuk", "dirsek", "kulak kenar", "kalın gri kabuk", "gri kalın kabuk"],
    "KOYU_DERI": ["koyulaş", "derisi karar", "kararmış", "kararma", "siyahlaş", "derisi koyu"],
    "KEPEK": ["kepek"],
    "YAG_DERI": ["yağlı", "ekşi kok", "derisi kok", "tüyleri kok", "derisinden koku"],
    "TUY_KOTU": ["matlaş", "keçeleş", "bakımsız", "tüyleri mat", "parlaklığı", "kendine bakm", "kendini yalam", "tüyleri kabarık", "tüyleri karışık"],
    "PIRE_GORUNTU": ["pire", "siyah nokta", "pire pisliği", "kum gibi kabuk", "siyah noktalar"],
    "KENE_GORUNTU": ["kene"],
    "KITLE": ["kitle", "yumru", "şişlik", "top gibi", "sert bir şey", "ele geliyor", "memesinde", "tümör", "sertlik", "nohut kadar", "ceviz kadar", "fındık gibi", "ceviz gibi", "yumrusu"],
    "APSE": ["apse", " irin", "irinli", "irin akt", "irin geldi", "patladı", "sıcak şiş", "şişlik patla", "delik var", "sıcak, şiş", "sıcak ve şiş", "yumuşak şiş", "sıcak, yumuşak", "yumruk gibi", "sıcak bir şiş", "şiş bir yer", "şişti ve dokun"],
    "ISIRIK_YARASI": ["kavga", "ısırık", "ısırdı", "tırmık", "ısırıldı", "ısırmış"],
    "YUZ_SIS": ["yüzü şiş", "ağzı şiş", "gözleri ve ağzı", "yüzü bir anda", "dudakları şiş", "gözleri şiş", "kafası şiş", "yüzünde kabartı", "kafası balon", "suratı şiş", "yüzü şişti", "yüzü ve gözleri şiş", "gözleri, dudakları ve yüzü", "ağzı ve dudakları şiş"],
    "YARA_KANAMA": ["kanıyor", "kanama", "kanaması durm", "derin yara", "açık yara", "kan geliyor", "kanayan"],
    "BURUN_KABUK": ["burnunda kabuk", "burnunun üstü kabuk", "burnunda yara", "burnu kabuk", "kulak kenarları kepek", "kulak kenarları yara", "burnunun üstü ve kulak", "burnunda ve kulak"],
    "TIRNAK_UZAMA": ["tırnakları uzu", "tırnakları anormal", "tırnakları kıvrık", "tırnak uzam", "tırnakları hızlı", "tırnakları hızla", "tırnakları anormal uzun", "tırnakları uzun ve"],
    # kulak
    "KULAK_KASINMA": ["kulağını kaş", "kulaklarını kaş", "kafasını sall", "başını sall", "başını sürekli sall", "kafasını sürekli sall", "sallıyor", "kulağını yere", "kulak kaşı", "kulağını sürekli kaş", "kulaklarını durmadan"],
    "KULAK_AKINTI": ["kulağından ak", "kulağı kok", "kulağının içi", "kulak akıntı", "kulağı kızar", "kulağından kötü", "kulağı sıcak", "kulakları kirli", "kulak kanalı", "kulağından kahverengi", "kulağından sarı", "kulağı çok kötü", "mayalı"],
    "KULAK_SIYAH_KIR": ["kahve telvesi", "siyah kir", "siyah kırıntı", "kulakları siyah", "kuru siyah", "siyah kuru", "siyah kirle"],
    "KULAK_AGRI": ["kulağına dokun", "kulağını ellet", "kulağına yaklaş", "kulağı ağrı", "dokununca inl", "dokunmama izin"],
    "BAS_EGIK": ["başı eğik", "başı yan", "kafası yan", "başı bir yana", "kafasını yana eğ", "başı yatık", "kafası eğik", "başı sağa eğik", "başı sola eğik", "başı 2 gündür bir yana"],
    "DENGE": ["denge", "sarhoş gibi", "yana düş", "dönerek yür", "ayakta duram", "sendel", "dengesiz", "yalpal", "yürürken düş", "yıkılıyor", "yana devril", "yana doğru yık", "ayakları birbirine dolan"],
    "NOBET": ["nöbet", "kasıl", "çırpın", "sara nöbet", "sara gibi", "sara mı", "epilepsi", "pedal", "bilinci gitti", "kaskatı", "çenesi kilitlen"],
    # hareket
    "TOPALLIK": ["topall", "topal", "aksıyor", "aksa", "basmıyor", "basamıyor", "bacağını sakın", "üç ayak", "bacağını kaldır", "yere basm", "bastıramıyor", "basmaz", "bacağına hiç bas", "yerden kesik", "yerden kesti", "yerden kes", "basmaz oldu", "hiç basmıyor", "bacağını yana uzat", "bacağını yerden"],
    "TOPALLIK_ARALIKLI": ["sekiyor", "kilitlen", "birkaç adım", "zıplayıp", "havada tut", "tek ayak üstünde", "3-4 adım", "bacağını havaya kaldır", "arada bir arka bacağını"],
    "ZOR_KALKMA": ["zor kalk", "yüksek yerlere çıkm", "yüksek yere çıkm", "kalkarken zorlan", "merdiven", "zıplayam", "tutuk", "yatıp kalkarken", "kalkamıyor", "zıplamıyor", "kalkması", "kalkmakta", "yerden kalk", "atlayamıyor", "atlayam", "koltuğa zıpl", "pencere kenarına zıpl", "zıplayamaz", "zıplamıyor"],
    "ARKA_BACAK_GUCSUZ": ["arka bacakları tutm", "arka ayakları tutm", "arka bacakları sür", "arka ayakları kay", "arka tarafı sallan", "arka bacakları güçsüz", "arka bacaklarında güçs", "arka bacakları zayıf", "arka ayaklarının üstüne", "topuklarına bas", "üzerinde duram", "arka bacaklarını sürü", "arka bacakları sallan", "arka bacaklarında hep hafif", "arka bacaklarını sürükl", "arka bacakları yana açıl", "arka tarafı iki yana", "arka tarafını zor", "sürükleniyor", "arka bacakları giderek"],
    "FELC": ["felç", "tutmuyor", "hareket ettirem", "kımıldatam", "tutmadı", "kullanamaz oldu", "tamamen tutm"],
    "ARKA_BACAK_SOGUK_FELC": ["patileri soğuk", "patileri buz", "çığlık", "ayakları soğuk", "patileri buz gibi", "tırnak yatakları soluk"],
    "SIRT_AGRISI": ["sırtına dokun", "sırtı ağrı", "kambur", "boynunu oynat", "sırtı kambur", "bel ağrı", "boynunu oynatm", "kucağa alınca bağır", "boynu tutul", "boynunu hiç oynat", "sırtına dokunduğumda", "başı aşağıda", "kucağa alınca acıyla"],
    "EKLEM_SIS": ["dizi şiş", "eklem şiş", "eklemleri şiş", "bacağı şiş", "dizi sıcak", "dizinde şiş", "dizi şiş ve sıcak"],
    "SIMETRIK_EKLEM": ["bir gün bir bacağı", "bütün eklem", "eklemleri ağrı", "bir bacağını bir gün öbür"],
    "HIPERAKTIF": ["hiperaktif", "deli gibi dolan", "çok hareketli", "hiç durmuyor", "yerinde durm", "fazla hareketli", "sürekli dolan"],
    "GOBEK_SARKIK": ["göbeği sark", "karnı sark", "göbekli", "karnı yere değ", "sarkık", "sarktı", "göbeği balon"],
    "SOLUK_HIZLI_PANTING": ["dili dışarıda", "soluyor", "dilini çıkar"],
    "POPO_SURTME": ["poposunu", "popo", "kuyruk altı", "sürtüyor", "anüs", "makat", "sürtüp", "sürükleyip"],
    "AKINTI_VAJINAL": ["vajina", "akıntı geliyor", "arka tarafından ak", "arkasından ak", "kanlı irinli", "kötü kokulu akıntı", "vulva", "kokulu bir leke", "kokulu leke", "akıntı var", "irinli akıntı", "kokulu akıntı", "arkasından sarı", "arkasından kötü"],
    "KIZGINLIK_SONRASI": ["kızgınlık", "kızgınlığı", "kızgınlıktan"],
    # VetAI: tek başına "sancı" kökü çıkarıldı; "sancılanıyor" (karın/idrar sancısı)
    # erkek kedide bile güç doğum kodu üretiyordu. Doğum sancısı aşağıdaki
    # özel köklerle ve halk dili sözlüğüyle yakalanır.
    "DOGUM_UZUN": ["doğum", "ıkınıyor ama yavru", "yavru gelmiyor", "doğum sancı", "doğuram", "yavrular arasında", "doğuruyor", "yavru doğ", "ıkınıyor ama hiçbir şey gelm", "doğurdu"],
    "ZEHIR_TEMAS": ["zehir", "zehri", "çikolata", "ilaç kutusu", "hapımı", "hap yut", "üzüm", "antifriz", "temizlik malzeme", "ilaçlanmış", "ksilitol", "sakız", "soğan", "ağrı kesici verdi", "ağrı kesici yut", "ilaç yut", "deterjan", "çamaşır suyu", "fare zehr", "fare ilac", "ilacımı", "ilaç içmiş", "yemiş olabilir", "kemirdi", "kemirmiş", "içmiş olabilir"],
    "ZEHIR_TEMAS_KEDI": ["zambak", "parasetamol", "köpek pire", "lilyum", "parol", "köpek ilacı"],
    "SICAK_TEMAS": ["sıcakta", "güneş", "arabada kaldı", "sıcak hava", "öğle sıcağı", "sahilde", "sıcaktan", "35 derece", "derece vardı", "güneşin altında", "arabada 20 dakika", "balkonda kapalı kal"],
    # VetAI: "düşmüş" / "düşerek" kökleri çıkarıldı ("iştahı düşmüş", "ateşi düşmüş"
    # travma sayılıyordu). Bir yerden düşme anlam_ayrimi.yuksekten_dusme kalıbıyla,
    # "sıcak çarptı" / "kazara" gibi yanıltıcı ifadeler maskelemeyle çözülür.
    "TRAVMA": ["araba çarp", "çarptı", "balkondan", "yüksekten", "kapıya sıkış", "üstüne bir şey düş", "üstüne düş", "ezildi", "kaza", "motosiklet", "vurdu", "sıkıştı", "kattan düş", "merdivenden düş", "yere düş", "aşağı düş"],
    # bağlam
    "ASISIZ": ["aşısız", "aşısı yok", "aşıları eksik", "aşı olmadı", "aşıları tamamlan", "aşıları yapılm", "asisiz", "aşı yapılmadı", "aşısı yapılm", "sadece ilk aşı", "ilk karma aşı", "aşıları hiç", "henüz aşı", "aşı olmamış"],
    "YENI_ALINDI": ["yeni aldık", "sahiplendik", "petshoptan", "barınaktan", "sokaktan aldı", "yeni geldi", "sahiplendiğimiz", "aldığımız", "önce geldi", "önce aldık", "getirdik", "üreticiden"],
    "DISARI_CIKAN": ["dışarı çık", "bahçeye çık", "sokakta gez", "bahçeli ev", "dışarıda", "sokak", "bahçeye çıkar", "dışarı çıkan"],
    "KISIR_DEGIL_DISI": ["kısırlaştırılmamış", "kısır değil", "kısırlaştırmadık", "kısır olmayan", "kısırlaştırılmadı"],
    "ERKEK": ["erkek"],
    "BUYUK_IRK": ["büyük ırk", "iri bir", "40 kilo", "55 kilo", "50 kilo"],
    "YEMEK_SONRASI": ["yemekten sonra", "yemeğini yedikten", "yemekten hemen sonra", "yemeğinden sonra", "yemeğini yedi, ardından", "yedi, ardından"],
    "COP_YEDI": ["çöp", "sofradan", "masadan", "misafir", "kurban", "mamasını değiştir", "mama değiştir", "yağlı", "sokakta bir şey ye", "bayram", "kavurma", "pilav", "başka marka", "bir şeyler yedir"],
    "KILO_FAZLA": ["kilolu", "fazla kilo", "şişman", "obez", "biraz kilolu"],
    "STRES": ["taşındık", "yeni kedi", "yeni bir kedi", "tatile", "tadilat", "stres", "yeni ev", "yeni kedi aldık"],
    "YASLI": ["yaşlı", "yaşlandı", "ihtiyar"],
    "KENE_ILACI_YOK": ["parazit ilacı", "pire kene ilacı", "ilaç yapılmadı", "iç dış parazit", "damla yapılmadı", "ilaçlama yapılmadı", "ilaç kullanmadık", "koruma yapmadık", "ilaç yapmadık", "koruyucu ilaç", "hiç ilaç yapılmamış", "ilaçlar yapılmamış"],
    "KURSAL_SEYAHAT": [" köyde", " köyden", " köye", "antalya", "bodrum", " ege'", " ege ", "egede", "akdeniz", "çiftlik", "yazlık", "izmir", "muğla", "fethiye", "kırsal"],
    "ARI_SOKMA": ["arı sok", "böcek sok", "aşı old", "aşıdan sonra", "yeni ilaç", "yeni mama", "aşı yapıldı", "aşıya götür", "aşısı yapıldı", "arı sokması"],
    "HAMILE": ["hamile", "gebe", "doğumu yaklaş", "çiftleş", "ilk doğumu"],
    "TEMAS_KOPEK": ["pansiyon", "parkta", "köpek parkı", "kuaför", "yeni bir köpek", "başka köpekler", "eve yeni bir köpek", "köpek parkına"],
    "TAVSAN_KOSU": ["tavşan gibi", "iki arka bacağını birden", "arka bacaklarını aynı anda", "tavşan"],
    "ANI_HAREKET": ["koşarken", "oynarken", "atladı", "atladıktan", "top oyn", "koştuktan", "zıpladı", "topun peşinden", "dönerken"],
    "KUCUK_IRK": ["küçük ırk", "minik", "3 kilo", "küçük bir köpek"],
    "INCE_DERI": ["derisi ince", "kağıt gibi", "damarlar görün", "kolay yaralan", "derisi kağıt"],
    "DISKI_AGRILI": ["kaka yaparken", "dışkılarken", "kaka yapmaya çekin", "kakasını yaparken", "kaka yaparken bağır"],
    "TEKRARLAYAN_ENF": ["sık sık hastalan", "sürekli hastalan", "iyileşmiyor", "her ay bir", "bir hastalığı bitiyor", "tekrar tekrar", "yaraları iyileşm", "bir apse bitiyor", "tekrarlayan", "tekrar ediyor"],
    "KURU_MAMA": ["kuru mama", "yaş mama yem", "sadece kuru"],
    "IYILESMIYOR": ["düzelmedi", "geçmedi", "işe yaramadı", "iyileşmedi", "değişmedi", "fayda etmedi", "geçmiyor", "düzelmiyor", "işe yaramıyor", "geçici düzel", "yaramadı"],
    # kronik varyantlar: ayrı kök taşımaz; süre bilgisiyle birlikte temel kod üzerinden yorumlanır
    "KUSMA_KRONIK": [],
    "ISHAL_KRONIK": [],
}

_ASCII = str.maketrans("şçğıöüŞÇĞİÖÜ", "scgiouSCGIOU")


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


def _katla(s):
    return s.translate(_ASCII)


# VetAI eklemesi: halk dili sözlüğündeki ek kökler (data/halk_dili_sozlugu.json).
HALK_DILI_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "halk_dili_sozlugu.json"
)


def _halk_dili_koklerini_ekle(tablo):
    """Sözlükteki belirti köklerini KOKLER tablosuna ekler; yeni kodları döndürür."""
    try:
        with open(HALK_DILI_JSON, encoding="utf-8") as f:
            sozluk = json.load(f)
    except (OSError, ValueError):
        return {}
    for kod, kokler_ in sozluk.get("belirti_kokleri", {}).items():
        mevcut = tablo.setdefault(kod, [])
        for kok in kokler_:
            if kok not in mevcut:
                mevcut.append(kok)
    return dict(sozluk.get("yeni_kodlar", {}))


#: Bilgi tabanında olmayan, halk dili sözlüğüyle gelen kodlar -> kanonik ad
YENI_KODLAR = _halk_dili_koklerini_ekle(KOKLER)

_KOK_TABLO = []  # (kod, kök_tr, kök_ascii)
for _kod, _ks in KOKLER.items():
    for _k in _ks:
        _KOK_TABLO.append((_kod, tr_lower(_k), _katla(tr_lower(_k))))


# VetAI eklemesi: kısa kökler yalnızca kelime başında eşleşir ("ıkın" kökü
# "İkinci" içinde, "ağrı" kökü "ağrıyor" dışında "bağrı" içinde tetiklenmesin).
KISA_KOK = 4

# VetAI eklemesi: eşleşen belirtiden sonra aynı cümlecikte olumsuzlama varsa
# ("ateşi yok", "kusması olmadı") kod düşürülür. Paket negasyonu bilerek
# ele almıyordu; burada yalnızca guardrail/rozet için basit bir kural var.
_OLUMSUZ = re.compile(
    r"\b(yok|değil|degil|olmadı|olmadi|yapmadı|yapmadi|görmedim|gormedim|kalmadı|kalmadi|"
    r"geçti|gecti|düzeldi|duzeldi|iyileşti|iyilesti)\b"
)
_CUMLECIK_SONU = re.compile(r"[.,;!?]| ama | fakat | ancak | ve ")


def _olumsuz_mu(m, idx):
    kalan = m[idx: idx + 40]
    son = _CUMLECIK_SONU.search(kalan)
    if son:
        kalan = kalan[: son.start() + 1]
    return bool(_OLUMSUZ.search(kalan))


def _bul(m, kok):
    """Kökün metindeki konumu; kısa kökler için kelime başı zorunlu. -1 = yok."""
    if len(kok) <= KISA_KOK:
        idx = m.find(" " + kok)
        return -1 if idx < 0 else idx + 1
    return m.find(kok)


_TR_OZEL = set("çğıöşü")


def _yazim_celisir(parca, k_tr):
    """Kullanıcı bu aralıkta kökten FARKLI bir Türkçe harf yazmış mı?

    "kaşık" metni "kasık" kökünün ASCII biçimine ("kasik") uyar ama kullanıcı
    açıkça "ş" yazmıştır; bu başka bir kelimedir. Buna karşılık "kasıntı"
    (ş harfi eksik yazılmış) "kaşıntı" kökü için geçerlidir.
    """
    return any(u != k and u in _TR_OZEL for u, k in zip(parca, k_tr))


def _bul_iki(m, ma, k_tr, k_as):
    """Önce Türkçe yazım, sonra ASCII katlanmış yazım.

    Kısa kökler ASCII biçimde yalnızca kullanıcı metni zaten Türkçe karaktersizse
    aranır; aksi halde "ıkın" kökü "İkinci" içinde, "sıçra" "sicak" içinde eşleşir.
    """
    idx = _bul(m, k_tr)
    if idx >= 0:
        return idx
    if len(k_as) <= KISA_KOK and m != ma:
        return -1
    idx = _bul(ma, k_as)
    if idx >= 0 and _yazim_celisir(m[idx: idx + len(k_tr)], k_tr):
        return -1
    return idx


def belirti_bul_gevsek(metin, *, olumsuzlama=True):
    """Metindeki belirti kodlarını geniş eşlemeyle bulur.
    Döndürür: (belirti_kodlari, baglam_kodlari)  — her ikisi de liste, sıralı, tekrarsız."""
    m = " " + re.sub(r"\s+", " ", tr_lower(metin)) + " "
    # VetAI: deyim / eş sesli ifadeler önce çözülür; aralıkları maskelenir ki
    # "sıcak çarptı" içindeki "çarptı" TRAVMA, "kusura" içindeki "kus" KUSMA üretmesin.
    anlam = anlam_ayrimi.eslesmeler(m)
    m = anlam_ayrimi.maskele(m, anlam)
    ma = _katla(m)
    bulunan = list(anlam_ayrimi.kodlar(anlam))
    dusurulen = set()
    for kod, k_tr, k_as in _KOK_TABLO:
        if kod in bulunan or kod in dusurulen:
            continue
        idx = _bul_iki(m, ma, k_tr, k_as)
        if idx < 0:
            continue
        if olumsuzlama and kod not in BAGLAM_KODLARI and _olumsuz_mu(ma, idx):
            dusurulen.add(kod)
            continue
        bulunan.append(kod)
    belirti = [k for k in bulunan if k not in BAGLAM_KODLARI]
    baglam = [k for k in bulunan if k in BAGLAM_KODLARI]
    return belirti, baglam


def guardrail(metin):
    """'devam' | 'belirti_sor' | 'kapsam_disi' ve bulunan kodlar."""
    b, c = belirti_bul_gevsek(metin)
    if b:
        return "devam", b, c
    if c:
        return "belirti_sor", b, c
    return "kapsam_disi", b, c
