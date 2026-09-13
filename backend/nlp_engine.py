"""VetAI Turkce NLP motoru (kural tabanli).

Hazir bir Turkce NLP kutuphanesi yerine, veteriner alanina ozel uc katmanli
kendi pipeline'imiz var:

    1) Normalizasyon        : Turkce'ye duyarli kucuk harf + ASCII katlama
    2) Es anlamli haritalama : "istifra ediyor" -> "kusma"
    3) Stop-word ayiklama + kural tabanli govdeleme (suffix stripping)

Ayrica basit bir olumsuzluk isaretleyici vardir: "atesi yok" -> "yok_ates".
Tibbi metinde olumsuzluk anlami tersine cevirdigi icin bu kritik.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List

# --------------------------------------------------------------------------
# 1) NORMALIZASYON
# --------------------------------------------------------------------------

# Turkce'ye ozgu kucuk harf donusumu: "I" harfi "i" degil "i-siz" olmali.
_LOWER_MAP = str.maketrans(
    {"I": "ı", "İ": "i", "Ş": "ş", "Ğ": "ğ",
     "Ü": "ü", "Ö": "ö", "Ç": "ç"}
)

# TF-IDF tutarliligi icin tum metni ASCII'ye katliyoruz; boylece Turkce karakter
# kullanan da kullanmayan da ayni tokeni uretir (kasinti == kasinti).
_ASCII_MAP = str.maketrans(
    "çğıöşüâîû", "cgiosuaiu"
)


def turkish_lower(text: str) -> str:
    return text.translate(_LOWER_MAP).lower()


def ascii_fold(text: str) -> str:
    text = text.translate(_ASCII_MAP)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize(text: str) -> str:
    """Ham kullanici metnini tekil, karsilastirilabilir bir forma indirger."""
    text = turkish_lower(text or "")
    text = ascii_fold(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # noktalama -> bosluk
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --------------------------------------------------------------------------
# 2) ES ANLAMLI SOZLUK (veteriner alani)
# --------------------------------------------------------------------------
# Anahtarlar normalize edilmis (ASCII, kucuk harf) halde yazilir.
# Once cok kelimeli kaliplar uygulanir, ardindan tek kelimeler.

PHRASE_SYNONYMS: dict[str, str] = {
    # --- sindirim ---
    "istifra ediyor": "kusma",
    "istifra etti": "kusma",
    "sulu diski": "ishal",
    "civik diski": "ishal",
    "yumusak diski": "ishal",
    "kanli diski": "kanli_ishal",
    "kanli ishal": "kanli_ishal",
    "diskisini yapamiyor": "kabizlik",
    "kaka yapamiyor": "kabizlik",
    "yemek yemiyor": "istahsizlik",
    "mama yemiyor": "istahsizlik",
    "yem yemiyor": "istahsizlik",
    "bir sey yemiyor": "istahsizlik",
    "cok su iciyor": "asiri_susama",
    "surekli su iciyor": "asiri_susama",
    "kilo kaybi": "kilo_kaybi",
    "kilo veriyor": "kilo_kaybi",
    "karni sis": "karin_sisligi",
    "karni sisti": "karin_sisligi",
    "karin agrisi": "karin_agrisi",
    # --- solunum ---
    "nefes darligi": "nefes_darligi",
    "nefes almakta zorlaniyor": "nefes_darligi",
    "zor nefes aliyor": "nefes_darligi",
    "hizli nefes": "nefes_darligi",
    "burun akintisi": "burun_akintisi",
    "burnu akiyor": "burun_akintisi",
    "goz akintisi": "goz_akintisi",
    "gozu akiyor": "goz_akintisi",
    "gozleri sulaniyor": "goz_akintisi",
    "gozu kizarik": "goz_kizarikligi",
    # --- deri ---
    "tuy dokulmesi": "tuy_dokulmesi",
    "tuy dokuyor": "tuy_dokulmesi",
    "tuyleri dokuluyor": "tuy_dokulmesi",
    "kil dokuyor": "tuy_dokulmesi",
    "deri dokuntusu": "deri_dokuntusu",
    "kizarik deri": "deri_dokuntusu",
    "kepek var": "kepeklenme",
    # --- hareket / norolojik ---
    "yurumekte zorlaniyor": "topallama",
    "ayagini basmiyor": "topallama",
    "bacagini surukluyor": "topallama",
    "dengesini kaybediyor": "denge_kaybi",
    "yalpalayarak yuruyor": "denge_kaybi",
    "kasilma geciriyor": "nobet",
    "havale geciriyor": "nobet",
    "bilincini kaybetti": "bilinc_kaybi",
    "tepki vermiyor": "bilinc_kaybi",
    # --- idrar ---
    "idrar yapamiyor": "idrar_tikanikligi",
    "cis yapamiyor": "idrar_tikanikligi",
    "kanli idrar": "kanli_idrar",
    "idrarinda kan": "kanli_idrar",
    "sik sik idrar": "sik_idrar",
    # --- genel ---
    "atesi var": "ates",
    "atesi yuksek": "ates",
    "vucudu sicak": "ates",
    "burnu kuru": "burun_kurulugu",
    "halsiz yatiyor": "halsizlik",
    "hic hareket etmiyor": "halsizlik",
    "agzi kokuyor": "agiz_kokusu",
    "dis eti kanamasi": "dis_eti_iltihabi",
    "kulagini kasiyor": "kulak_kasintisi",
    "kulagindan koku": "kulak_iltihabi",
    "kafasini salliyor": "kulak_iltihabi",
    # --- zehirlenme / travma ---
    "cikolata yedi": "cikolata_zehirlenmesi",
    "zehirli madde": "zehirlenme",
    "fare zehiri": "zehirlenme",
    "deterjan icti": "zehirlenme",
    "araba carpti": "travma",
    "yuksekten dustu": "travma",
}

WORD_SYNONYMS: dict[str, str] = {
    # kusma
    "kusuyor": "kusma", "kusma": "kusma", "kustu": "kusma", "kusmuk": "kusma",
    "istifra": "kusma", "oguruyor": "kusma", "ogurme": "kusma",
    # ishal
    "ishal": "ishal", "surgun": "ishal", "diyare": "ishal",
    # halsizlik
    "halsiz": "halsizlik", "halsizlik": "halsizlik", "yorgun": "halsizlik",
    "bitkin": "halsizlik", "uyusuk": "halsizlik", "durgun": "halsizlik",
    "enerjisiz": "halsizlik", "letarji": "halsizlik", "gucsuz": "halsizlik",
    # istahsizlik
    "istahsiz": "istahsizlik", "istahsizlik": "istahsizlik",
    "anoreksi": "istahsizlik", "acikmiyor": "istahsizlik",
    # ates
    "ates": "ates", "atesli": "ates", "sicaklik": "ates", "hipertermi": "ates",
    # kasinti
    "kasiniyor": "kasinti", "kasinti": "kasinti", "kasima": "kasinti",
    "kasiyor": "kasinti", "pruritus": "kasinti",
    # solunum
    "oksuruk": "oksuruk", "oksuruyor": "oksuruk",
    "hapsirik": "hapsirma", "hapsiriyor": "hapsirma", "hapsirma": "hapsirma",
    "hirilti": "hirilti", "hiriltili": "hirilti", "nefes": "nefes_darligi",
    # hareket
    "topal": "topallama", "topalliyor": "topallama", "topallama": "topallama",
    "aksiyor": "topallama", "aksama": "topallama",
    "nobet": "nobet", "havale": "nobet", "kasilma": "nobet",
    "konvulsiyon": "nobet", "epilepsi": "nobet",
    "titriyor": "titreme", "titreme": "titreme",
    # parazit
    "pire": "parazit", "kene": "parazit", "parazit": "parazit",
    "solucan": "ic_parazit", "tenya": "ic_parazit",
    # deri
    "mantar": "mantar", "egzama": "deri_dokuntusu", "sivilce": "deri_dokuntusu",
    "yara": "yara", "sislik": "sislik", "odem": "sislik", "apse": "apse",
    "kepek": "kepeklenme", "uyuz": "uyuz",
    # agiz-dis
    "salya": "asiri_salya", "tukuruk": "asiri_salya", "tartar": "dis_tasi",
    "kanama": "kanama",
    # goz-kulak
    "sulanma": "goz_akintisi", "cipak": "goz_akintisi",
    # idrar
    "idrar": "idrar_sikayeti", "cis": "idrar_sikayeti", "sistit": "sistit",
    # davranis
    "saldirgan": "davranis_degisikligi", "sinirli": "davranis_degisikligi",
    "saklaniyor": "davranis_degisikligi", "miyavliyor": "asiri_seslenme",
    "uluyor": "asiri_seslenme", "havliyor": "asiri_seslenme",
    # tur adlari
    "kedi": "kedi", "pisi": "kedi", "kedicik": "kedi", "tekir": "kedi",
    "kopek": "kopek", "kopeg": "kopek", "enik": "kopek", "kancik": "kopek",
}

# Cok kelimeli kaliplari uzun -> kisa sirala ki en spesifik kalip once eslessin.
_PHRASE_PATTERN = re.compile(
    r"\b("
    + "|".join(sorted((re.escape(k) for k in PHRASE_SYNONYMS), key=len, reverse=True))
    + r")\b"
)


def apply_phrase_synonyms(text: str) -> str:
    return _PHRASE_PATTERN.sub(lambda m: PHRASE_SYNONYMS[m.group(0)], text)


# --------------------------------------------------------------------------
# 3) STOP WORDS
# --------------------------------------------------------------------------
STOP_WORDS: set[str] = {
    "acaba", "ama", "ancak", "artik", "asla", "ayrica", "bana", "baska",
    "belki", "ben", "benim", "beri", "bile", "bir", "biraz", "birkac", "biz",
    "bizim", "bu", "buna", "bunda", "bundan", "bunu", "bunun", "burada",
    "cok", "cunku", "da", "daha", "de", "defa", "diger", "diye", "eder",
    "ederim", "eger", "en", "evet", "falan", "filan", "galiba", "gibi",
    "gunler", "hala", "hayir", "hem", "henuz", "hep", "hepsi", "her",
    "herhalde", "hic", "hicbir", "icin", "ile", "ise", "iyi", "kadar", "kez", "ki",
    "kim", "lutfen", "merhaba", "mi", "mu", "nasil", "ne", "neden", "nerede",
    "nereye", "niye", "olarak", "onlar", "onu", "oyle", "peki", "rica",
    "sanki", "sanirim", "selam", "sen", "senin", "sey", "seyler", "simdi",
    "siz", "sonra", "su", "tamam", "tesekkur", "tesekkurler", "tum", "ve",
    "veya", "var", "vardir", "ya", "yaklasik", "yani", "yine", "zaten",
    "gun", "gundur", "gunluk", "haftadir", "aydir", "surekli", "sik",
    "biraz", "olmus", "oldu", "oluyor", "yapiyor", "ediyor",
}

# Olumsuzluk belirteci: kendinden onceki anlamli tokeni tersine cevirir.
NEGATION_WORDS = {"yok", "yoktur", "degil", "olmuyor"}


# --------------------------------------------------------------------------
# 4) KURAL TABANLI TURKCE GOVDELEME (suffix stripping)
# --------------------------------------------------------------------------
# Ekler uzundan kisaya denenir; govde MIN_STEM_LEN'in altina duserse ek atilmaz.
MIN_STEM_LEN = 4

SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {
            # fiil cekimleri
            "iyorlar", "uyorlar", "iyordu", "uyordu", "iyorum", "uyorum",
            "iyorsun", "uyorsun", "maktadir", "mektedir", "acagim", "ecegim",
            "mislar", "muslar", "iyor", "uyor", "yor", "acak", "ecek",
            "mis", "mus", "mak", "mek", "maya", "meye", "ma", "me",
            "di", "du", "ti", "tu",
            # cogul
            "lar", "ler",
            # iyelik
            "lari", "leri", "imiz", "umuz", "iniz", "unuz", "sinin",
            "nin", "nun", "in", "un", "im", "um", "si", "su",
            # hal ekleri
            "dan", "den", "tan", "ten", "da", "de", "ta", "te",
            "ya", "ye", "na", "ne", "yi", "yu", "ni", "nu",
            "m", "n", "i", "u",
            # yapim ekleri
            "sizlik", "suzluk", "lilik", "cilik", "lik", "luk",
            "siz", "suz", "li", "lu", "ci", "cu", "ce", "ca", "ki",
        },
        key=len,
        reverse=True,
    )
)


def stem(token: str) -> str:
    """Tek bir tokenin govdesini dondurur (tek gecisli, agresif olmayan soyma)."""
    if "_" in token:  # es anlamli haritalamadan gelen bilesik etiket
        return token
    if len(token) <= MIN_STEM_LEN:
        return token
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= MIN_STEM_LEN:
            return token[: -len(suffix)]
    return token


# --------------------------------------------------------------------------
# 5) ANA PIPELINE
# --------------------------------------------------------------------------


def tokenize(text: str, *, use_negation: bool = True) -> List[str]:
    """Ham metin -> temiz, govdelenmis, es anlamli eslenmis token listesi."""
    text = normalize(text)
    text = apply_phrase_synonyms(text)

    tokens: List[str] = []
    for raw in text.split():
        if raw.isdigit():
            continue
        if use_negation and raw in NEGATION_WORDS:
            if tokens:  # onceki bulguyu olumsuzla: "ates yok" -> "yok_ates"
                tokens[-1] = f"yok_{tokens[-1]}"
            continue
        if raw in STOP_WORDS:
            continue

        word = WORD_SYNONYMS.get(raw)
        if word is None:
            word = stem(raw)
            word = WORD_SYNONYMS.get(word, word)
        if len(word) < 3 or word in STOP_WORDS:
            continue
        tokens.append(word)

    return tokens


def preprocess(text: str) -> str:
    """TF-IDF vektorlestiricisine verilecek bosluklu string."""
    return " ".join(tokenize(text))


# Sozlukteki tum kanonik bulgu etiketleri (tur adlari haric).
KANONIK_BULGULAR: set[str] = (
    set(PHRASE_SYNONYMS.values()) | set(WORD_SYNONYMS.values())
) - {"kedi", "kopek", "yavru"}


def extract_keywords(text: str, limit: int = 8) -> List[str]:
    """Arayuzdeki 'tespit edilen bulgular' rozetleri.

    Yalnizca sozlukte tanimli kanonik bulgular dondurulur; "iki", "olabilir"
    gibi govdelenmis ama anlam tasimayan tokenler rozet olarak gosterilmez.
    """
    seen: List[str] = []
    for token in tokenize(text):
        olumsuz = token.startswith("yok_")
        kok = token[4:] if olumsuz else token
        if kok not in KANONIK_BULGULAR:
            continue
        etiket = kok.replace("_", " ")
        if olumsuz:
            etiket += " (yok)"
        if etiket not in seen:
            seen.append(etiket)
    return seen[:limit]


# --------------------------------------------------------------------------
# 6) TUR TESPITI
# --------------------------------------------------------------------------
KEDI_IPUCLARI = {"kedi", "pisi", "kedicik", "tekir"}
KOPEK_IPUCLARI = {"kopek", "enik", "golden", "terrier", "coban", "pitbull", "kangal"}


def detect_tur(text: str) -> str:
    """Metinden hayvan turunu tahmin eder: 'kedi' | 'kopek' | 'genel'."""
    normalized = normalize(text)
    tokens = set(tokenize(text, use_negation=False))
    if tokens & KEDI_IPUCLARI or "kedi" in normalized:
        return "kedi"
    if tokens & KOPEK_IPUCLARI or "kopek" in normalized or "kopeg" in normalized:
        return "kopek"
    return "genel"


def token_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard benzerligi - tekrar eden kayitlari tespit etmek icin."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


if __name__ == "__main__":  # hizli elle test: python nlp_engine.py
    ornekler = [
        "Kedim 2 gundur surekli kusuyor ve hic mama yemiyor, cok halsiz.",
        "Kopegim kasiniyor, tuy dokuyor ve kulagini kasiyor.",
        "Atesi yok ama burun akintisi var ve hapsiriyor.",
    ]
    for o in ornekler:
        print(f"{o}\n  -> {tokenize(o)}  [tur={detect_tur(o)}]\n")
