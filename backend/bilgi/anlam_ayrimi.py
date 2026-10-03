# -*- coding: utf-8 -*-
"""Deyim ve eş sesli ifade ayrımı (anlam ayrımı tablosu).

TF-IDF modeli ve kök tabanlı guardrail kelimeye bakar, anlama bakmaz:
"Köpeğime sıcak çarptı" ile "Köpeğime araba çarptı" aynı "çarp" kökünü taşır.
Eğitim verisinde "çarptı" yalnızca araç kazası cümlelerinde geçtiği için model
sıcak çarpmasını "Travma" diye etiketliyordu. Aynı sorun "kusura bakmayın"
(kusma), "nöbetçi veteriner" (nöbet), "iştahı düşmüş" (düşme travması),
"kazara" (kaza), "kalbi çarpıyor" (çarpma), "kurt köpeği" (bağırsak kurdu)
gibi ifadelerde de vardı.

Bu modül, kelimenin bağlam içindeki anlamını belirleyen kalıpları ML'den ve
guardrail'den ÖNCE çözer. Her kalıp:

    yerine   : ML'e giden metinde ifadenin yerine yazılacak kanonik karşılık
               (None -> ifade metinden silinir; ör. "kusura bakmayın")
    kodlar   : kök tabanlı guardrail'e (kokler) eklenecek belirti/bağlam kodları
    aciliyet : (kod, kanonik ad, seviye) — metindeki aciliyet bayrağı
    aciklama : insan okuyacak not; anlam katmanında Gemini istemine de verilir

Kullananlar:
    nlp_engine.tokenize            -> yeniden_yaz()
    kokler.belirti_bul_gevsek      -> eslesmeler() + maskele() + kodlar()
    acil_kaliplar.aciliyet_tespit  -> aciliyet_bayraklari()
    anlam_katmani (Gemini)         -> notlar()

Desenler ASCII'ye katlanmış, küçük harfli, noktalaması boşluğa çevrilmiş metin
üzerinde çalışır (ascii_hazirla). Dönüşüm karakter karakter yapıldığı için
bulunan aralıklar özgün metne de aynen uygulanabilir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Metin hazırlama (uzunluğu korur)
# --------------------------------------------------------------------------

_ASCII = str.maketrans("çğıöşüâîûÇĞİÖŞÜÂÎÛ", "cgiosuaiuCGIOSUAIU")


def ascii_hazirla(metin: str) -> str:
    """Metni 1:1 uzunlukta küçük harfli ASCII'ye çevirir.

    Türkçe karakterler katlanır, harf/rakam dışındaki her karakter boşluk olur.
    Uzunluk değişmediği için dönen metindeki bir aralık (bas, son) özgün
    metinde de aynı ifadeyi gösterir.
    """
    s = metin.replace("İ", "i").replace("I", "ı").lower().translate(_ASCII)
    return "".join(c if ("a" <= c <= "z" or "0" <= c <= "9") else " " for c in s)


# --------------------------------------------------------------------------
# Kalıp tanımı
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class AnlamKalibi:
    ad: str
    desen: "re.Pattern[str]"
    yerine: Optional[str]
    kodlar: Tuple[str, ...] = ()
    aciliyet: Optional[Tuple[str, str, str]] = None
    aciklama: str = ""
    olumsuz_kontrol: bool = True
    #: Verilirse kalıp yalnızca metnin herhangi bir yerinde bu desen de varsa uygulanır
    baglam: Optional["re.Pattern[str]"] = None


@dataclass(frozen=True)
class Eslesme:
    kalip: AnlamKalibi
    bas: int
    son: int
    ifade: str


def _k(ad, desen, yerine, kodlar=(), aciliyet=None, aciklama="", olumsuz_kontrol=True, baglam=None):
    return AnlamKalibi(
        ad=ad,
        desen=re.compile(desen),
        yerine=yerine,
        kodlar=tuple(kodlar),
        aciliyet=aciliyet,
        aciklama=aciklama,
        olumsuz_kontrol=olumsuz_kontrol,
        baglam=re.compile(baglam) if baglam else None,
    )


# Araya en fazla N kelime girebilir: "güneş fena çarptı", "araba köpeğime çarptı"
_ARA1 = r"(?:\w+\s+)?"
_ARA2 = r"(?:\w+\s+){0,2}"
_ARA3 = r"(?:\w+\s+){0,3}"

_ARACLAR = (
    r"(?:araba|arac|otomobil|oto|otobus|kamyon|kamyonet|minibus|motor|motosiklet|"
    r"motorsiklet|bisiklet|taksi|traktor|servis)\w*"
)
_DUSULEN_YER = (
    r"(?:balkon|pencere|cam|cati|merdiven|basamak|\d*\s*kat|ust\s+kat|masa|koltuk|"
    r"kanepe|yatak|agac|duvar|dolap|tezgah|kucag|kucak|elim|sandalye|teras|yuksek|"
    r"yukari|araba|kapi)\w*?(?:dan|den|tan|ten)"
)
# Sokma / ısırma fiilinin geçmiş ve ad biçimleri ("sokak", "arıyor" yanılmasın)
_ISIR_SOK = r"(?:isir(?:di|mis|masi|igi|iyor)|sok(?:tu|mus|masi|ugu))\w*"

# Sıra önemlidir: önce özel (benzetmeli, olumsuzlu) kalıplar, sonra genel olanlar.
# Bir metin aralığı yalnızca ilk eşleşen kalıba ait olur.
KALIPLAR: List[AnlamKalibi] = [
    # ------------------------------------------------------------ çarpmak
    _k(
        "elektrik_benzetmesi",
        rf"\belektrik\w*\s+{_ARA1}(?:carp|cek|vur)\w*\s+gibi\b",
        None,
        aciklama="'Elektrik çarpmış gibi' bir benzetmedir (ani sıçrama, nöbet ya da ani ağrı "
                 "anlatımı); gerçek elektrik çarpması değildir.",
        olumsuz_kontrol=False,
    ),
    # Olay anlatımı ("sıcak çarptı") acil bayrağı üretir; hastalık adı ("sıcak
    # çarpması belirtileri nelerdir?") tek başına üretmez. Bilgi sorusu acil kart açmasın.
    _k(
        "sicak_carpmasi",
        r"\b(?:sicak|gunes)\s+" + _ARA1 + r"(?:carp(?:ti|mis|ip|inca|abilir)\w*|vur(?:du|mus|unca)\w*)"
        r"|\bgunes\s+" + _ARA1 + r"gec(?:ti|mis)\w*\b"
        r"|\bisi\s+carp(?:ti|mis)\w*"
        r"|\bhararet\s+" + _ARA1 + r"(?:bas|vur|carp)(?:ti|di|mis)\w*"
        r"|\bsicak(?:tan)?\s+" + _ARA1 + r"(?:bayil|yigil|fenalas|carpil)\w*",
        "sicak_carpmasi",
        kodlar=("SICAK_TEMAS",),
        aciliyet=("SICAK_CARPMASI", "Sıcak çarpması şüphesi", "kirmizi"),
        aciklama="'Sıcak/güneş çarptı', 'güneş geçti', 'hararet bastı' ifadeleri sıcak "
                 "çarpmasıdır; araç çarpması ya da travma değildir.",
    ),
    _k(
        "sicak_carpmasi_adi_hayvanli",
        r"\b(?:sicak|gunes|isi)\s+carpma(?:s\w*)?\b|\bgunes\s+gecmesi\w*",
        "sicak_carpmasi",
        kodlar=("SICAK_TEMAS",),
        aciklama="'Sıcak çarpması' bir hastalık adıdır; araç çarpması değildir.",
        olumsuz_kontrol=False,
        baglam=r"\b(?:kedi|kopek|kopeg|hayvan|yavru|pati)",
    ),
    _k(
        "sicak_carpmasi_adi",
        r"\b(?:sicak|gunes|isi)\s+carpma(?:s\w*)?\b|\bgunes\s+gecmesi\w*",
        "sicak_carpmasi",
        aciklama="'Sıcak çarpması' bir hastalık adıdır; araç çarpması değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "arac_carpmasi",
        rf"\b{_ARACLAR}\s+{_ARA2}(?:carp|ez|vur|cign)(?:ti|di|mis|ip|ildi|ilmis|ince|inca|edi|emis)\w*"
        rf"|\b{_ARACLAR}\s+altinda\s+kal\w*"
        r"|\btrafik\s+kazasi\s+gecir\w*",
        "travma_oykusu",
        kodlar=("TRAVMA",),
        aciliyet=("TRAVMA", "Travma öyküsü", "kirmizi"),
        aciklama="Araç çarpması / trafik kazası travma öyküsüdür.",
    ),
    _k(
        "arac_carpmasi_adi_hayvanli",
        rf"\b{_ARACLAR}\s+(?:carpma|ezil?me)(?:s\w*)?\b|\btrafik\s+kaza\w*",
        "travma_oykusu",
        kodlar=("TRAVMA",),
        aciklama="Araç çarpması / trafik kazası travma öyküsüdür.",
        olumsuz_kontrol=False,
        baglam=r"\b(?:kedi|kopek|kopeg|hayvan|yavru|pati)",
    ),
    _k(
        "arac_carpmasi_adi",
        rf"\b{_ARACLAR}\s+(?:carpma|ezil?me)(?:s\w*)?\b|\btrafik\s+kaza\w*",
        "travma_oykusu",
        aciklama="Araç çarpması / trafik kazası travma öyküsüdür.",
        olumsuz_kontrol=False,
    ),
    _k(
        "elektrik_carpmasi",
        rf"\belektrik\w*\s+{_ARA1}(?:carp(?:ti|mis|ip)|cek(?:ti|mis)|vur(?:du|mus))\w*",
        "elektrik_carpmasi",
        kodlar=("TRAVMA",),
        aciliyet=("ELEKTRIK", "Elektrik çarpması", "kirmizi"),
        aciklama="Elektrik çarpması acil bir yaralanmadır (ağız yanığı, akciğer ödemi riski).",
    ),
    _k(
        "elektrik_carpmasi_adi",
        r"\belektrik\s+carpma(?:s\w*)?\b",
        "elektrik_carpmasi",
        aciklama="'Elektrik çarpması' bir yaralanma adıdır.",
        olumsuz_kontrol=False,
    ),
    _k(
        "kablo_kemirme",
        rf"\b(?:kablo|priz)\w*\s+{_ARA1}(?:isir|kemir|cign|yala)\w*",
        "kablo_kemirme",
        kodlar=("TRAVMA",),
        aciklama="Kablo/priz ısırma elektrik çarpması riski taşır.",
    ),
    _k(
        "kalp_carpintisi",
        rf"\b(?:kalb|kalp)\w*\s+{_ARA2}(?:carp\w*|atiyor|atisi\w*|atislari\w*|tekliyor)"
        r"|\bcarpinti\w*",
        "kalp_carpintisi",
        kodlar=("KALP_CARPINTI",),
        aciklama="'Kalbi hızlı çarpıyor' kalp çarpıntısıdır; çarpma travması değildir.",
    ),
    _k(
        "duvarlara_carpma",
        r"\b(?:duvar|esya|kapi|mobilya|kose)\w*lar\w*\s+" + _ARA1 + r"(?:carp|tosl)\w*"
        r"|\b(?:duvar|esya|mobilya|kose)\w*\s+" + _ARA1 + r"(?:carpiyor|carpip|tosluyor)\w*",
        "denge_kaybi",
        kodlar=("DENGE",),
        aciklama="Duvarlara/eşyalara çarpıp durmak yön bulma ya da denge sorunudur; "
                 "tek seferlik bir darbe değildir.",
    ),
    # ------------------------------------------------------------ düşmek
    _k(
        "istah_dustu",
        rf"\bistah\w*\s+{_ARA1}dus\w*",
        "istahsizlik",
        kodlar=("ISTAHSIZLIK",),
        aciklama="'İştahı düştü' iştahsızlıktır; düşme travması değildir.",
    ),
    _k(
        "kilo_dustu",
        rf"\bkilo\w*\s+{_ARA1}dus\w*",
        "kilo_kaybi",
        kodlar=("KILO_KAYBI",),
        aciklama="'Kilosu düştü' kilo kaybıdır; düşme travması değildir.",
    ),
    _k(
        "ates_dustu",
        rf"\bates\w*\s+{_ARA1}dus(?:tu|mus|du)\w*",
        "ates_dustu",
        aciklama="'Ateşi düştü' ateşin geçtiğini anlatır; ateş belirtisi ya da düşme değildir.",
    ),
    _k(
        "tuy_dusuyor",
        rf"\b(?:tuy|kil)\w*\s+{_ARA1}dus\w*",
        "tuy_dokulmesi",
        kodlar=("TUY_DOKULMESI",),
        aciklama="'Tüyleri düşüyor' tüy dökülmesidir.",
    ),
    _k(
        "dis_dustu",
        r"\bdis(?:i|leri)\s+dus\w*",
        "dis_eti_iltihabi",
        kodlar=("DIS_ETI",),
        aciklama="'Dişi düştü' diş hastalığı belirtisidir; düşme travması değildir.",
    ),
    _k(
        "enerji_dustu",
        rf"\b(?:enerji|keyf|moral)\w*\s+{_ARA1}dus(?:tu|mus|uk)\w*",
        "halsizlik",
        kodlar=("HALSIZLIK",),
        aciklama="'Enerjisi/keyfi düştü' halsizliktir; düşme travması değildir.",
    ),
    _k(
        "yuksekten_dusme",
        rf"\b{_DUSULEN_YER}\s+(?:asagi\s+)?(?:dus|yuvarlan|uc)\w*",
        "travma_oykusu",
        kodlar=("TRAVMA",),
        aciklama="Bir yerden düşme travma öyküsüdür.",
    ),
    _k(
        "nobette_yere_dusme",
        r"\byere\s+(?:dus|kapaklan)\w*",
        None,
        aciklama="Nöbet ya da bayılma sırasında yere düşmek bir belirtidir; düşme travması değildir.",
        baglam=r"kasil|titre|cirpin|kaskati|nobet|havale|kriz|bayil|bilinc|kendinden\s+gec|sara\b|"
               r"epilep|kopuk|segir",
    ),
    # ------------------------------------------------------------ eş sesli / deyim
    _k(
        "kusura_bakma",
        r"\bkusur\w*",
        None,
        aciklama="'Kusura bakmayın' bir nezaket ifadesidir; kusma değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "kazara",
        r"\bkazara\b|\bkaza\s+ile\b|\bkazayla\b|\bkaza\s+eseri\b|\bkazaen\b",
        None,
        aciklama="'Kazara' istemeden anlamındadır; kaza/travma öyküsü değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "nobetci",
        r"\bnobetci\w*",
        None,
        aciklama="'Nöbetçi veteriner/eczane' nöbet geçirme değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "dogum_gunu",
        r"\bdogum\s+gun\w*|\bdogustan\b",
        None,
        aciklama="'Doğum günü' / 'doğuştan' doğum yapma (distosi) anlamına gelmez.",
        olumsuz_kontrol=False,
    ),
    _k(
        "kurt_irki",
        r"\b(?:kurt|alman\s+kurd\w*|sibirya\s+kurd\w*|kafkas\s+kurd\w*)\s+(kopek|kopeg)\w*"
        r"|\b(?:alman|sibirya|kafkas)\s+kurd\w*",
        r"kurt_irki kopek",
        kodlar=("BUYUK_IRK",),
        aciklama="'Kurt köpeği', 'Sibirya/Alman kurdu' ırk adıdır; bağırsak kurdu değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "kus_avi",
        r"\bkus(?:u|a|lari|lar)?\s+" + _ARA1 + r"(?:yedi|yakala|kovala|getir|avla)\w*",
        "kus_avi",
        kodlar=("DISARI_CIKAN",),
        aciklama="'Kuş yakaladı/yedi' kuş avıdır; kusma değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "zehir_gibi_deyim",
        r"\bzehir\s+gibi\s+(?:zeki|akilli|soguk|aci|sicak|keskin)\w*",
        None,
        aciklama="'Zehir gibi zeki/soğuk' bir deyimdir; zehirlenme değildir.",
        olumsuz_kontrol=False,
    ),
    _k(
        "kulak_uyuzu",
        r"\bkulak\s+uyuz\w*",
        "kulak_uyuzu",
        kodlar=("KULAK_KASINMA",),
        aciklama="'Kulak uyuzu' (Otodectes) deri uyuzundan ayrı bir tablodur.",
    ),
    _k(
        "oksuruk_krizi",
        rf"\boksuruk\w*\s+{_ARA1}(?:kriz|atak|nobet)\w*",
        "oksuruk",
        kodlar=("OKSURUK",),
        aciklama="'Öksürük nöbeti/krizi' öksürük atağıdır; epilepsi nöbeti değildir.",
    ),
    _k(
        "astim_krizi",
        rf"\b(?:astim|nefes)\w*\s+{_ARA1}(?:kriz|atak|nobet)\w*",
        "nefes_darligi oksuruk",
        kodlar=("OKSURUK_ATAK", "NEFES_DARLIGI"),
        aciklama="'Astım krizi/nefes krizi' solunum atağıdır; epilepsi nöbeti değildir.",
    ),
    # ------------------------------------------------------------ belirti karışıklıkları
    _k(
        "ilac_yutma",
        r"\b(?:ilac|hap|agri\s+kesici|parol|parasetamol|vitamin|zehir|fare\s+zehr)\w*\s+" + _ARA1
        + r"(?:yuttu|yutmus|yedi|yemis|yaladi|yalamis|icti|icmis|kemirdi|kemirmis)\w*",
        "ilac_zehir_yutma",
        kodlar=("ZEHIR_TEMAS",),
        aciliyet=("ZEHIR_TEMAS", "Zehirli madde teması", "kirmizi"),
        aciklama="İlaç ya da zehir yutmak zehirlenme riskidir; oyuncak gibi yabancı cisim "
                 "yutmakla aynı şey değildir.",
    ),
    _k(
        "kahve_yedi",
        rf"\bkahve\w*\s+(?:telve\w*\s+)?{_ARA1}(?:yedi|yemis|icti|icmis|yaladi|yalamis)\w*",
        "kahve_yedi",
        kodlar=("ZEHIR_TEMAS",),
        aciklama="Kahve / kahve telvesi yemek kafein zehirlenmesi riskidir; kulak kiri değildir.",
    ),
    _k(
        "kahve_telvesi_kusmuk",
        rf"\bkahve\s+telve\w*\s+{_ARA2}(?:kus|kustu|kusmu)\w*"
        rf"|\bkus\w*\s+{_ARA3}kahve\s+telve\w*",
        "kanli kusma",
        kodlar=("KAN_KUSMA", "KUSMA"),
        aciliyet=("KAN_KUSMA", "Kanlı kusma", "turuncu"),
        aciklama="Kahve telvesi gibi kusmuk sindirilmiş kandır (kanlı kusma); kulak kiri değildir.",
    ),
    _k(
        "kahve_telvesi_diski",
        rf"\bkahve\s+telve\w*\s+{_ARA2}(?:kaka|diski|disk|pislik)\w*"
        rf"|\b(?:kaka|diski|disk|pislig)\w*\s+{_ARA3}kahve\s+telve\w*",
        "siyah kaka",
        kodlar=("DISKI_SIYAH",),
        aciklama="Kahve telvesi gibi dışkı sindirilmiş kandır (siyah dışkı); kulak kiri değildir.",
    ),
    _k(
        "nefes_kokusu",
        rf"\bnefes\w*\s+{_ARA2}kok\w*",
        "agiz_kokusu",
        kodlar=("AGIZ_KOKUSU",),
        aciklama="'Nefesi kokuyor' ağız kokusudur; nefes darlığı değildir.",
    ),
    _k(
        "soguk_alginligi",
        r"\bsoguk\s+algin\w*|\busut(?:tu|mus|mus\w*|ugu)\b",
        "nezle",
        kodlar=("NEZLE",),
        aciklama="'Soğuk algınlığı/üşüttü' nezle (üst solunum yolu) anlatımıdır; sıcak "
                 "çarpmasıyla ya da üşüme davranışıyla ilgisi yoktur.",
    ),
    _k(
        "araba_tutmasi",
        r"\b(?:araba|yol)\s+tut(?:tu|uyor|masi|ar|mus)\w*",
        "kusma",
        kodlar=("KUSMA",),
        aciklama="'Araba tuttu' yolculuk bulantısıdır; araç kazası değildir.",
    ),
    _k(
        "arabada_kaldi",
        r"\b(?:araba|arac|oto)\w*(?:da|de|ta|te)\s+" + _ARA2 + r"(?:kal|unut|birak|bekle|kapali)\w*"
        r"|\b(?:araba|arac)\w*\s+icinde\s+" + _ARA2 + r"(?:kal|unut|birak|bekle)\w*",
        "arabada_kaldi",
        kodlar=("SICAK_TEMAS",),
        aciklama="Kapalı arabada kalmak sıcak çarpması öyküsüdür.",
    ),
    _k(
        "bocek_sokmasi",
        r"\b(?:ari(?:si|lar|lari)?|esek\s+arisi|sivrisinek\w*|bocek\w*|karinca\w*|orumcek\w*)\s+"
        + _ARA1 + _ISIR_SOK,
        "ari_sokmasi",
        kodlar=("ARI_SOKMA",),
        aciklama="Arı/böcek sokması alerjik reaksiyon öyküsüdür; kavga ısırığı değildir.",
    ),
    _k(
        "pire_isirigi",
        rf"\bpire\w*\s+{_ARA1}{_ISIR_SOK}",
        "pire",
        kodlar=("PIRE_GORUNTU",),
        aciklama="Pire ısırığı paraziter bir durumdur; kavga ısırığı değildir.",
    ),
    _k(
        "kene_isirigi",
        rf"\bkene\w*\s+{_ARA1}{_ISIR_SOK}",
        "kene",
        kodlar=("KENE_GORUNTU",),
        aciklama="Kene ısırığı paraziter bir durumdur; kavga ısırığı değildir.",
    ),
    _k(
        "goz_agliyor",
        rf"\bgoz\w*\s+{_ARA1}(?:agl|yasar|yas\s+(?:gel|ak))\w*",
        "goz_akintisi",
        kodlar=("GOZ_AKINTISI",),
        aciklama="'Gözü ağlıyor/yaşarıyor' göz akıntısıdır; ağrı belirtisi değildir.",
    ),
    _k(
        "agzi_sulaniyor",
        r"\bag(?:iz|z)\w*\s+sulan\w*",
        "asiri_salya",
        kodlar=("SALYA",),
        aciklama="'Ağzı sulanıyor' salya artışıdır; göz sulanması değildir.",
    ),
    _k(
        "oksurup_ogurme",
        rf"\boksur\w*\s+{_ARA3}ogur\w*|\bogur\w*\s+gibi\s+{_ARA1}oksur\w*",
        "oksuruk",
        kodlar=("OKSURUK",),
        aciklama="Öksürüğün sonunda öğürmek (kulübe öksürüğünde tipik) kusma değildir.",
    ),
    _k(
        "tuy_yumagi_kusma",
        r"\btuy\s+yumag\w*\s+(?:kus\w*|cikardi|cikarti|cikarmis)\b(?!\s+gibi)",
        "tuy yumagi kusma",
        kodlar=("KUSMA",),
        aciklama="Tüy yumağı kusmak/çıkarmak kusmadır; 'tüy yumağı çıkarır gibi öksürmek' "
                 "ise astım belirtisidir.",
    ),
    _k(
        "karin_tas_gibi",
        rf"\bkarn\w*\s+{_ARA1}tas\s+gibi",
        "karni sis karin_agrisi",
        kodlar=("KARIN_SIS", "KARIN_AGRISI"),
        aciklama="'Karnı taş gibi' karın gerginliği/ağrısıdır; kabızlık değildir.",
    ),
    _k(
        "bogaza_takildi",
        rf"\bbogaz\w*\s+{_ARA2}(?:sikis|takil)(?:ti|di|mis)\w*\b(?!\s+gibi)",
        "yabanci cisim yuttu",
        kodlar=("YABANCI_CISIM", "YUTMA_ZOR"),
        aciklama="Boğaza bir şey takılması yabancı cisim şüphesidir; sıkışma travması değildir.",
    ),
]


# --------------------------------------------------------------------------
# Olumsuzluk kontrolü ("sıcak çarpmadı", "iştahı düşmüyor")
# --------------------------------------------------------------------------

_OLUMSUZ_FIIL = re.compile(r"m[ae](?:d[iu]|z|m[iu]s|y)|m[iu]yor")


def _olumsuz_mu(ifade: str) -> bool:
    """Kalıbın son kelimesi olumsuz fiil çekimi taşıyor mu?

    "carpmadi", "dusmuyor", "gecmedi" -> True; "carpti", "carpmasi" -> False.
    Kökün ilk 3 harfi atlanır ki "mama", "meme" gibi gövdeler yanılmasın.
    """
    son_kelime = ifade.split()[-1] if ifade.split() else ""
    return bool(_OLUMSUZ_FIIL.search(son_kelime[3:]))


# --------------------------------------------------------------------------
# Genel API
# --------------------------------------------------------------------------

def eslesmeler(metin: str) -> List[Eslesme]:
    """Metindeki anlam kalıplarını sırayla bulur (çakışan aralıkta ilk kalıp kazanır)."""
    temiz = ascii_hazirla(metin)
    dolu = [False] * len(temiz)
    bulunan: List[Eslesme] = []
    for kalip in KALIPLAR:
        if kalip.baglam is not None and not kalip.baglam.search(temiz):
            continue
        for m in kalip.desen.finditer(temiz):
            bas, son = m.start(), m.end()
            if bas == son or any(dolu[bas:son]):
                continue
            ifade = temiz[bas:son]
            if kalip.olumsuz_kontrol and _olumsuz_mu(ifade):
                continue
            for i in range(bas, son):
                dolu[i] = True
            bulunan.append(Eslesme(kalip, bas, son, m.group(0)))
    bulunan.sort(key=lambda e: e.bas)
    return bulunan


def yeniden_yaz(metin: str) -> str:
    """ML'e giden metin: eşleşen ifadeleri kanonik karşılıklarıyla değiştirir.

    Çıktı küçük harfli ASCII'dir (nlp_engine.normalize ile aynı biçim).
    """
    temiz = ascii_hazirla(metin)
    parcalar: List[str] = []
    imlec = 0
    for e in eslesmeler(metin):
        parcalar.append(temiz[imlec:e.bas])
        parcalar.append(f" {e.kalip.yerine} " if e.kalip.yerine else " ")
        imlec = e.son
    parcalar.append(temiz[imlec:])
    return re.sub(r"\s+", " ", "".join(parcalar)).strip()


def maskele(metin: str, bulunan: Sequence[Eslesme]) -> str:
    """Eşleşen aralıkları boşlukla örter (uzunluk korunur).

    kokler bu sayede "sıcak çarptı" içindeki "çarptı" kökünden TRAVMA,
    "kusura" içindeki "kus" kökünden KUSMA üretmez.
    """
    if not bulunan:
        return metin
    karakterler = list(metin)
    for e in bulunan:
        for i in range(e.bas, min(e.son, len(karakterler))):
            karakterler[i] = " "
    return "".join(karakterler)


def kodlar(bulunan: Iterable[Eslesme]) -> List[str]:
    """Eşleşen kalıpların kodları (sıralı, tekrarsız)."""
    sonuc: List[str] = []
    for e in bulunan:
        for kod in e.kalip.kodlar:
            if kod not in sonuc:
                sonuc.append(kod)
    return sonuc


def aciliyet_bayraklari(bulunan: Iterable[Eslesme]) -> List[Tuple[str, str, str]]:
    """(kod, kanonik ad, seviye) listesi; seviye 'kirmizi' | 'turuncu'."""
    sonuc: List[Tuple[str, str, str]] = []
    for e in bulunan:
        if e.kalip.aciliyet and e.kalip.aciliyet not in sonuc:
            sonuc.append(e.kalip.aciliyet)
    return sonuc


def notlar(metin: str) -> List[str]:
    """Metinde geçen yanıltıcı ifadeler için açıklamalar (Gemini istemine eklenir)."""
    sonuc: List[str] = []
    for e in eslesmeler(metin):
        if e.kalip.aciklama and e.kalip.aciklama not in sonuc:
            sonuc.append(e.kalip.aciklama)
    return sonuc


if __name__ == "__main__":  # python -m bilgi.anlam_ayrimi
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ornek in [
        "Köpeğime sıcak çarptı",
        "Köpeğime araba çarptı",
        "Kusura bakmayın, kedim topallıyor",
        "Kedimin iştahı düşmüş, kalbi de hızlı çarpıyor",
        "Köpeğime sıcak çarpmadı ama halsiz",
    ]:
        print(f"{ornek}\n  -> {yeniden_yaz(ornek)!r}  kodlar={kodlar(eslesmeler(ornek))}")
